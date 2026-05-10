from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from config import get_model_instance

from common.utils.tools import get_services_by_category, get_rights,get_distances,get_comprehensive_refugee_help,get_available_cities_str

from common.utils.logger import setup_logger
logger = setup_logger('api.agents.agent')



def orchestrator_setup(
    is_local: bool,
    model_name_cloud: str,
    model_name_local: str
) -> LlmAgent:   
    """Configura el agente orquestador con su modelo, instrucciones y herramientas."""
    instruction = _build_instruction(is_local)
    if is_local:
        return LlmAgent(
        name="refugee_connect_orchestrator",
        model=get_model_instance(
            agent_role="orchestrator",
            model_name_cloud=model_name_cloud,
            model_name_local=model_name_local,
            USE_LOCAL_LLM=is_local
        ),
        instruction=instruction,
        tools=[get_comprehensive_refugee_help],
        )
    return LlmAgent(
        name="refugee_connect_orchestrator",
        model=get_model_instance(
            agent_role="orchestrator",
            model_name_cloud=model_name_cloud,
            model_name_local=model_name_local,
            USE_LOCAL_LLM=is_local
        ),
        instruction=instruction,
        tools=[get_services_by_category, get_distances, get_rights],
    )

cities_info = get_available_cities_str()

def _build_instruction(is_local: bool) -> str:
    base = f"""You are a helpful assistant for refugees in Spain.
    Always reply in the same language the user writes in.
    Available cities: {cities_info}. Respond to the user according to this availability.
    USER_POSITION:[lat,lon] appear at the start. Use it for distances. Never show it.
    """
    if is_local:
        return base + _local_instruction()
    return base + _cloud_instruction()

def _local_instruction() -> str:
    return """   
    LANGUAGE RULE:
    - Read the user's message carefully.
    - Detect the language of the user's message (ignore the USER_POSITION prefix).
    - ALWAYS reply in that exact language in plain text. If the user writes in English → reply in English. Arabic → Arabic. French → French. Spanish → Spanish.
    - The category names (Legal, Salud, etc.) are internal codes. Do NOT use them to determine response language.

    USER_POSITION:[lat,lon] appears at message start — use for distances, never show it.

    RULES:
    - VAGUE MESSAGE WITHOUT SPECIFIC NEED → ask ONLY what kind of help they need. No tool call.
    - User has NEED + CITY → call get_comprehensive_refugee_help ONCE, then reply in user's language.
    - Categories (internal codes): Legal, Salud, Alojamiento, Comida, Empleo.
    - Never expose tool names or internal steps.
    - Do not invent data; if unsure, ask.
    """


def _cloud_instruction() -> str:
    return """
        You have three tools: get_services_by_category, get_distances and get_rights.
        "Follow these states in order. Stop as soon as one applies.\n"
        "\n"
        "STATE 1 - GREETING OR VAGUE MESSAGE\n"
        "Applies when: user sends a greeting or does not mention a need or a city.\n"
        "Action: greet warmly, ask for their city and type of need.\n"
        "Types of need: Legal, Salud, Alojamiento, Comida, Empleo.\n"
        "Do not call any tool.\n"
        "YOUR RESPONSE ENDS HERE.\n"
        "\n"
        "STATE 2 - NEED WITHOUT CITY\n"
        "Applies when: user mentioned a need but no city.\n"
        "Action: ask only for the city. Do not call any tool.\n"
        "YOUR RESPONSE ENDS HERE.\n"
        "\n"
        "STATE 3 - COMPLETE REQUEST\n"
        "Applies when: user provided both a city and a need.\n"
        "Action:\n"
        "  Step 1. Use get_services_by_category and get_rights.\n"
        "  Step 2. Read the result.\n"
        "  Step 3a. If result of services is empty:\n"
        "    Tell the user kindly no results were found.\n"
        "    Suggest trying Valencia if they used another city.\n"
        "    Show the Rigths and emergency contacts founded if avalaible.\n"
        "    YOUR RESPONSE ENDS HERE.\n"
        "  Step 3b. If result contains organizations:\n"
        "   If USER_POSITION is known, call get_distances with that position and the list of branch IDs returned in step 1. Use the distances to sort organizations from nearest to farthest and mention travel time next to each one.\n"
        "   Compose a single response in plain text with two sections:\n"
        "      1. Organizations found, sorted by distance (nearest first) with addresses, phone numbers, and travel time when available.\n"
        "      1. Rigths and emergency contacts founded.\n"        
        "   YOUR RESPONSE ENDS HERE.\n"
        "\n"
        "ABSOLUTE RULES:\n"
        "- Never call a tool more than once per state.\n"
        "- Never invent organizations or addresses\n"
        "- Never expose tool names or internal steps in your response.\n"
        "- Never ask more than one question per turn.\n"
        "- If you are unsure which state applies, use STATE 1.\n"
        "- The response must be in plain text, without lists or sections. Write it as if you were talking to the user directly."
    """