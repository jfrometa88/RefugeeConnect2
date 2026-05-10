from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from typing import Optional

from common.utils.logger import setup_logger
from agents.agent import orchestrator_setup
from agents.tracing_plugin import tracing_plugin

logger = setup_logger('api.agents.agent_manager')

class RefugeeAgentManager:
    """Manager para los agentes de RefugeeConnect AI con soporte de recarga dinámica"""
    
    def __init__(self,
                 model_name_cloud:str,
                 model_name_local:str,
                 is_local:bool,
                 session_id:str,
                 existing_session_service=None):
        self.session_id = session_id
        self.session_service = existing_session_service or InMemorySessionService()
        
        # guardamos el estado de configuración para futuras recargas
        self.config_state = {
            "model_name_cloud": model_name_cloud,
            "model_name_local": model_name_local,
            "is_local": is_local
        }
        # inicializamos el orquestador y el runner
        self.orchestrator = orchestrator_setup(is_local,model_name_cloud,model_name_local) 
        self.APP_NAME = "refugee_connect"
        
        
        self.runner = Runner(
            agent=self.orchestrator,
            app_name=self.APP_NAME, 
            session_service=self.session_service,
            plugins=[tracing_plugin]
        )
        
        self._initialized = True

    async def _get_or_create_session(self, user_id: str, session_id: str):
        """Obtiene o crea una sesión para el usuario."""
        # primero intentamos obtener la sesión existente
        session = await self.session_service.get_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
        # si no existe, la creamos
        if not session:
            session = await self.session_service.create_session(
                app_name=self.APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
        return session

    async def query_orchestrator(
        self,
        user_message: str,
        user_id: str,
        session_id: str | None = None
    ) -> str:
        """Envía la consulta al orquestador y retorna la respuesta final."""

        # si no se proporciona session_id, usamos un formato por defecto basado en user_id
        if session_id is None:
            session_id = f"session_{user_id}"

        try:
            query_content = (
                types.Content(role="user", parts=[types.Part(text=user_message)])
                if isinstance(user_message, str)
                else user_message
            )

            session = await self._get_or_create_session(user_id, session_id)

            final_response = ""

            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=query_content
            ):
                # Traza detallada de eventos para depuración y análisis
                autor = getattr(event, "author", "unknown")
                content = getattr(event, "content", None)
                
                if content and hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            f_call = part.function_call
                            logger.info(f"🚀 [TRAZA] {autor} SOLICITA herramienta: {f_call.name}")
                            logger.info(f"📥 [TRAZA] Argumentos enviados: {f_call.args}")
                        
                        if hasattr(part, "function_response") and part.function_response:
                            f_res = part.function_response                            
                            logger.info(f"✅ [TRAZA] {autor} RECIBIÓ respuesta de: {f_res.name}")
                            logger.info(f"📊 [TRAZA] Datos crudos: {f_res.response}")

                # captura de texto (opcional para ver el razonamiento)
                if not getattr(event, "partial", True) and autor != "unknown":
                    if content and hasattr(content, "parts") and len(content.parts) > 0:
                        text = getattr(content.parts[0], "text", None)
                        if text:
                            logger.info(f"💬 [TRAZA] Pensamiento/Respuesta de {autor}: {text[:100]}...")

                if event.is_final_response():
                    if event.content and event.content.parts:
                        # a veces se emiten varias partes: las primeras puede ser el razonamiento, la última es la respuesta necesaria para el usuario
                        valid_texts = []
                        
                        for part in event.content.parts:
                            if not hasattr(part, "text"):
                                continue
                            
                            text = part.text

                            if isinstance(text, dict):
                                continue
                            
                            if isinstance(text, str):
                                text = text.strip()
                                if text:
                                    valid_texts.append(text)

                        if valid_texts:
                            final_response = valid_texts[-1]

            return final_response or (
                "Lo siento, no he podido generar una respuesta. Por favor, intenta de nuevo./Sorry, something wrong happens, try again"
            )

        except Exception as e:
            logger.error(f"Error en query_orchestrator (user={user_id}): {e}", exc_info=True)
            return "He encontrado un error al procesar tu solicitud. Por favor, intenta de nuevo./Sorry, something wrong happens, try again"


    def update_provider(self, 
                        is_local: bool, 
                        model_name_cloud: Optional[str],
                        model_name_local: Optional[str]
                        ):
        """
        Realiza el cambio del motor de inferencia entre modelos locales o cloud y reconstruye el orquestador.
        """
        logger.info(f"🔄 Iniciando recarga de proveedor: Local={is_local}, Modelo cloud={model_name_cloud}, Modelo local={model_name_local}")
        
        try:
            new_orchestrator = orchestrator_setup(
                model_name_cloud=model_name_cloud if model_name_cloud else self.config_state["model_name_cloud"],
                model_name_local=model_name_local if model_name_local else self.config_state["model_name_local"],
                is_local=is_local
            )
            # actualizamos el orquestador en el manager
            self.orchestrator = new_orchestrator
            
            self.runner = Runner(
                agent=self.orchestrator, 
                app_name=self.APP_NAME, 
                session_service=self.session_service,
                plugins=[tracing_plugin]
            )
            # actualizamos el estado de configuración para futuras recargas
            self.config_state["is_local"] = is_local
            self.config_state["model_name_cloud"] = model_name_cloud
            self.config_state["model_name_local"] = model_name_local

            logger.info("✅ Runner y Orquestador actualizados correctamente.")
            return True

        except Exception as e:
            logger.error(f"❌ Error crítico al actualizar el proveedor: {e}", exc_info=True)
            raise e
