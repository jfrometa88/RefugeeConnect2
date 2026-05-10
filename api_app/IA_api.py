import sys
from httpcore import request
import httpx
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from collections import deque

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from dataclasses import dataclass, field

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.utils.logger import setup_logger

from agents.agent_manager import RefugeeAgentManager
from agents.tracing_plugin import tracing_plugin
from config import check_backend_availability

logger = setup_logger('api.refugee_api')

import os
from dotenv import load_dotenv
load_dotenv()

USE_LOCAL_LLM: bool = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GEMMA_MODEL_NAME_local=os.getenv("GEMMA_MODEL_NAME_local", "qwen2.5-coder:3b")
GEMMA_MODEL_NAME_cloud=os.getenv("GEMMA_MODEL_NAME_cloud", "gemma-4-31b-it")

@dataclass
class RuntimeConfig:
    use_local_llm: bool = USE_LOCAL_LLM  # valor inicial desde .env

runtime_config = RuntimeConfig()


# Inicializando
agent_manager: Optional[RefugeeAgentManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el AgentManager una sola vez al arrancar el servidor."""
    global agent_manager
    logger.info("Inicializando RefugeeAgentManager...")
    try:
        agent_manager = RefugeeAgentManager(
            model_name_cloud=GEMMA_MODEL_NAME_cloud,
            model_name_local=GEMMA_MODEL_NAME_local,
            is_local=USE_LOCAL_LLM,
            session_id="anonymous_user"
        )
        logger.info("AgentManager listo.")
    except Exception as e:
        logger.error(f"Error al inicializar AgentManager: {e}", exc_info=True)
        # no relanzamos
    yield
    logger.info("Apagando RefugeeConnect API.")

app = FastAPI(
    title="RefugeeConnect AI API",
    description="Backend multi-agente para refugiados y migrantes en España",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8050"],  #solo el dashboard Dash
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

#modelos de datos
class AgentQuery(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    user_id: str = Field(default="anonymous_user")
    user_position: Optional[list[float]] = None

class AgentResponse(BaseModel):
    response: str
    status: str
    session_id: str

class OllamaModel(BaseModel):
    name: str
    size_gb: float
    modified: str

class SystemHealth(BaseModel):
    status: str                    
    ollama_available: bool
    ollama_host: str
    local_models: list[str]
    google_api_key_set: bool
    agent_manager_ready: bool
    active_mode: str

class SystemConfig(BaseModel):
    use_local: bool
    model_name_cloud: Optional[str] = None
    model_name_local: Optional[str] = None

class MapResource(BaseModel):
    id: int
    organization: str
    service: str
    category: str
    address: str
    phone: Optional[str]
    lat: float
    lon: float
    languages: list[str]
    requirements: Optional[str]
 
class MapResourcesResponse(BaseModel):
    resources: list[MapResource]
    total: int
    city: str
    categories_found: list[str]


async def check_ollama() -> dict:
    """
    Equivalente programático de `ollama list en shell script`.
    Llama al endpoint REST de Ollama para listar modelos instalados.
    Retorna dict con available:bool y models:list[str].
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"available": True, "models": models}
    except httpx.ConnectError:
        logger.warning(f"Ollama no disponible en {OLLAMA_HOST}")
        return {"available": False, "models": []}
    except Exception as e:
        logger.warning(f"Error consultando Ollama: {e}")
        return {"available": False, "models": []}

async def check_model_in_ollama(model_name: str) -> bool:
    """Verifica si un modelo concreto está instalado en Ollama.
    Pensado para Gemma 4"""
    result = await check_ollama()
    if not result["available"]:
        return False
    base = model_name.split(":")[0]
    return any(base in m for m in result["models"])

# Endpoints
@app.get("/")
async def root():
    return {
        "status": "active",
        "project": "RefugeeConnect AI",
        "competition": "Gemma 4 Good Hackathon",
        "mode": "local" if USE_LOCAL_LLM else "cloud",
    }

@app.get("/health", response_model=SystemHealth)
async def health_check():
    """
    Chequeo real del sistema: Ollama, modelos, API key, AgentManager.
    El dashboard Dash puede llamar esto para saber qué está disponible.
    """
    ollama_info = await check_ollama()
    google_key_set = bool(os.getenv("GEMINI_API_KEY"))
    manager_ready = agent_manager is not None
    use_local = runtime_config.use_local_llm

    if use_local and not ollama_info["available"]:
        status = "unavailable"
    elif use_local and GEMMA_MODEL_NAME_local not in " ".join(ollama_info["models"]):
        status = "unavailable for gemma-4"
    elif not use_local and not google_key_set:
        status = "unavailable"
    else:
        status = "healthy"

    return SystemHealth(
        status=status,
        ollama_available=ollama_info["available"],
        ollama_host=OLLAMA_HOST,
        local_models=ollama_info["models"],
        google_api_key_set=google_key_set,
        agent_manager_ready=manager_ready,
        active_mode="local" if use_local else "cloud",
    )

@app.get("/models/local")
async def list_local_models():
    """
    Lista los modelos disponibles en Ollama.
    El dashboard usa esto para mostrar un selector de modelo.
    """
    result = await check_ollama()
    if not result["available"]:
        logger.warning(f"Ollama model no disponible en {OLLAMA_HOST}")
        raise HTTPException(
            status_code=503,
            detail=f"Ollama no disponible en {OLLAMA_HOST}. "
                   "Verifica que esté corriendo con: ollama serve"
        )
    return {
        "ollama_host": OLLAMA_HOST,
        "models": result["models"],
        "count": len(result["models"]),
    }

@app.post("/query", response_model=AgentResponse)
async def query_agent(query: AgentQuery):
    """Punto de entrada principal para las consultas del dashboard."""
    if agent_manager is None:
        logger.error("El sistema de agentes no está inicializado. Consulta /health para más detalles.")
        raise HTTPException(
            status_code=503,
            detail="El sistema de agentes no está inicializado. Consulta /health para más detalles."
        )
    #advertencia si modo local pero Ollama no disponible
    if USE_LOCAL_LLM:
        ollama_info = await check_ollama()
        if not ollama_info["available"]:
            logger.warning(f"Ollama no disponible en {OLLAMA_HOST}")
            raise HTTPException(
                status_code=503,
                detail="Modo local activo pero Ollama no está disponible. "
                       "Ejecuta 'ollama serve' antes de hacer consultas."
            )

    try:
        logger.info(f"Consulta [user={query.user_id}, session={query.session_id}]: {query.message[:80]}")

        if query.user_position and len(query.user_position) == 2:
            lat, lon = query.user_position
            message = f"USER_POSITION:[lat:{lat},long:{lon}] {query.message}"
        else:
            message = query.message

        response = await agent_manager.query_orchestrator(
            user_message=message,
            user_id=query.user_id,
            session_id=query.session_id,
        )

        session_id_usado = query.session_id or f"session_{query.user_id}"

        respuesta_agente = AgentResponse(
            response=response,
            status="success",
            session_id=session_id_usado,
        )

        return respuesta_agente

    except Exception as e:
        logger.error(f"Error procesando consulta [user={query.user_id}]: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error interno del sistema de agentes."
        )

@app.get("/trajectory")
async def get_trace():
    """Trazas de razonamiento del llm — útil para auditoría."""
    return tracing_plugin.get_stats()

@app.get("/logs")
async def get_logs(lineas: Optional[int] = 50):
    """Últimas N líneas del log — para depuración via web"""
    log_path = Path("common") / "data" / "logs" / "logs.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Archivo de log no encontrado.")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            contenido = "".join(deque(f, maxlen=lineas))
        return Response(content=contenido, media_type="text/plain")
    except Exception as e:
        logger.error(f"Error al leer el log: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/config/toggle")
async def toggle_model_mode(config: SystemConfig):
    """Maneja el cambio de uso local a cloud y los modelos asociados"""
    global agent_manager
    
    #validar disponibilidad antes de nada
    is_available = check_backend_availability(is_local=config.use_local)
    
    if not is_available:
        mode_str = "Ollama (Local)" if config.use_local else "Google Cloud"
        raise HTTPException(
            status_code=503, 
            detail=f"El backend de {mode_str} no está disponible. Revisa la conexión."
        )

    try:
        agent_manager.update_provider(
            is_local=config.use_local,
            model_name_cloud=config.model_name_cloud,
            model_name_local=config.model_name_local
        )
        logger.info(f"Actualización exitosa a modo local: {str(config.use_local)} y modelo local {config.model_name_local} y cloud {config.model_name_cloud}")
        runtime_config.use_local_llm = config.use_local
        return {"status": "success", "mode_agent": "local" if config.use_local else "cloud", "mode_orc": "local" if config.use_local else "cloud"}
    except Exception as e:
        logger.error(f"Error crítico en el cambio de configuración de agentes: {e}")
        raise HTTPException(status_code=500, detail="Error al reconfigurar agentes.")
    
@app.get("/map/resources", response_model=MapResourcesResponse)
async def get_map_resources(
    city: str = "Valencia",
    category: Optional[str] = None,
):
    """
    Endpoint directo a BD para el mapa del dashboard.
    NO pasa por los agentes LLM — es una consulta directa a SQLite.
    """
    try:
        from common.utils.tools import get_map_resources as _get_map_resources
        resources = _get_map_resources(city=city, category=category)
        categories_found = sorted({r["category"] for r in resources})
 
        return MapResourcesResponse(
            resources=[MapResource(**r) for r in resources],
            total=len(resources),
            city=city,
            categories_found=categories_found,
        )
    except Exception as e:
        logger.error(f"Error en /map/resources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al consultar recursos del mapa.")

if __name__ == "__main__":
    uvicorn.run(
        "IA_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )