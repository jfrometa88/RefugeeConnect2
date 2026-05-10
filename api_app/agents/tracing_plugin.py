from common.utils.logger import setup_logger
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.plugins.base_plugin import BasePlugin

class MinimalTracingPlugin(BasePlugin):
    """
    Tracing plugin mínimo para agentes y solicitudes LLM en el Orchestrator.
    Proporciona trazabilidad básica de invocaciones de agentes y solicitudes LLM.
    """

    def __init__(self) -> None:
        super().__init__(name="minimal_tracing_plugin")
        self.agent_count = 0
        self.llm_count = 0
        self.logger = setup_logger("minimal_tracing")

    async def before_agent_run(
        self, agent: BaseAgent, context: CallbackContext
    ) -> None:
        """
        Se activa antes de que un agente ejecute su lógica. Proporciona trazabilidad de invocaciones de agentes.
        """
        self.agent_count += 1
        
        session_id = context.metadata.get('session_id', 'unknown') if context.metadata else 'unknown'
        
        self.logger.info(
            f"🔍 [TRACE] Agent '{agent.name}' started | "
            f"Invocations: {self.agent_count} | Session: {session_id}"
        )

    async def before_llm_run(
        self, llm_request: LlmRequest, context: CallbackContext
    ) -> None:
        """
        Se dispara antes de que se ejecute una solicitud LLM. Proporciona trazabilidad de solicitudes LLM.
        """
        self.llm_count += 1
        model_name = getattr(llm_request, 'model', 'Gemma-4')
        
        last_msg = ""
        if llm_request.messages:
            last_msg = llm_request.messages[-1].content[:50] + "..."
            
        self.logger.info(
            f"🧠 [TRACE] LLM Request #{self.llm_count} | "
            f"Model: {model_name} | Prompt: {last_msg}"
        )

    def get_stats(self) -> dict:
        """Devuelve estadísticas básicas sobre las invocaciones de agentes y solicitudes LLM."""
        return {
            "agent_invocations": self.agent_count,
            "llm_requests": self.llm_count,
            "status": "active"
        }

# Para usar en la API
tracing_plugin = MinimalTracingPlugin()