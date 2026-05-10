import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import dash_leaflet.express as dlx
import requests
import sqlite3
import uuid
from pathlib import Path
import sys
import json

import os
from dotenv import load_dotenv

load_dotenv()


DEFAULT_CLOUD_MODEL = os.getenv("GEMMA_MODEL_NAME_cloud", "gemma-4-31b-it")
GEMMA4_MODEL_NAME = os.getenv("GEMMA4_MODEL_NAME","gemma4:e2b")

MOCK_USER_POSITION = (39.4697, -0.3774)

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.utils.logger import setup_logger
logger = setup_logger('dash_app')

translations_path = Path(__file__).parent / "TRANSLATIONS.json"

try:
    with open(translations_path, "r", encoding="utf-8") as f:
        TRANSLATIONS = json.load(f)
    logger.info("Traducciones cargadas correctamente.")
except Exception as e:
    logger.error(f"Error cargando TRANSLATION.json: {e}")
    # Diccionario de respaldo (fallback) por si falla la carga
    TRANSLATIONS = {"es": {"title": "RefugeeConnect AI", "subtitle": "Error al cargar traducciones"}}

DB_PATH = project_root / "common" / "data" / "refugeeconnect.db"
API_BASE = os.getenv("API_URL", "http://localhost:8000")
SESSION_ID = str(uuid.uuid4())

CATEGORY_COLORS_LOCAL = {
    "Legal":       "#E74C3C",
    "Salud":       "#27AE60",
    "Alojamiento": "#2980B9",
    "Comida":      "#F39C12",
    "Empleo":      "#8E44AD",
}

CATEGORY_ICONS = {
    "Legal":       "fa-scale-balanced",
    "Salud":       "fa-kit-medical",
    "Alojamiento": "fa-house",
    "Comida":      "fa-utensils",
    "Empleo":      "fa-briefcase",
}

CATEGORY_LABELS_LOCAL = {
    "Legal" : "Legal/Legal/قانوني/Légal",
    "Salud" : "Salud/Health/صحة/Santé",
    "Alojamiento" : "Alojamiento/Accommodation/الإقامة/Logement",
    "Comida" : "Comida/Food/طعام/Nourriture",
    "Empleo" : "Empleo/Employment/وظيفة/Emploi",
}

ALL_CATEGORIES = list(CATEGORY_COLORS_LOCAL.keys())

#funciones auxiliares
def fetch_map_resources(city: str = "Valencia", category: str | None = None) -> list[dict]:
    """Llama al endpoint /map/resources y devuelve la lista de recursos."""
    try:
        params = {"city": city}
        if category:
            params["category"] = category
        resp = requests.get(f"{API_BASE}/map/resources", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json().get("resources", [])
    except Exception as e:
        logger.warning(f"Error al obtener recursos del mapa: {e}")
        return []
    
def fetch_map_resources_local(city: str = "Valencia", category: str | None = None) -> list[dict]:
    """
    Lee los recursos del mapa DIRECTAMENTE de SQLite, sin pasar por la API.
    Devuelve lista vacía si la BD no existe o hay error (sin tumbar el dashboard).
    """
    if not DB_PATH.exists():
        logger.warning(f"BD no encontrada en {DB_PATH}, usando API como fallback")
        return fetch_map_resources(city=city, category=category)  #fallback a API
 
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
 
        category_filter = "AND s.category = ?" if category else ""
        params = [city]
        if category:
            params.append(category)
 
        query = f"""
            SELECT
                b.id+s.id as id, o.name AS organization, s.name AS service,
                s.category AS category, b.address, b.local_phone AS phone,
                b.latitude AS lat, b.longitude AS lon, bs.requirements
            FROM branches b
            JOIN organizations o ON b.organization_id = o.id
            JOIN branch_services bs ON b.id = bs.branch_id
            JOIN services s ON bs.service_id = s.id
            WHERE b.city = ?
              AND b.latitude IS NOT NULL
              AND b.longitude IS NOT NULL
              {category_filter}
            ORDER BY s.category, o.name
        """
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
 
        # Idiomas en una sola query adicional
        branch_ids = list({row["id"] for row in rows})
        languages_map: dict[int, list[str]] = {bid: [] for bid in branch_ids}
        if branch_ids:
            placeholders = ",".join("?" * len(branch_ids))
            lang_cursor = conn.cursor()
            lang_cursor.execute(
                f"SELECT branch_id, language_code FROM languages_served WHERE branch_id IN ({placeholders})",
                branch_ids
            )
            for lang_row in lang_cursor.fetchall():
                languages_map[lang_row["branch_id"]].append(lang_row["language_code"])
 
        conn.close()
 
        return [
            {
                "id":           row["id"],
                "organization": row["organization"],
                "service":      row["service"],
                "category":     row["category"],
                "address":      row["address"],
                "phone":        row["phone"],
                "lat":          row["lat"],
                "lon":          row["lon"],
                "languages":    languages_map.get(row["id"], []),
                "requirements": row["requirements"],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error leyendo mapa desde SQLite: {e}")
        return fetch_map_resources(city=city, category=category)  # fallback a API


def fetch_system_health() -> dict:
    """Llama a /health y devuelve el estado del sistema."""
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        return resp.json()
    except Exception:
        return {"status": "unavailable", "active_mode": "unknown", "local_models": []}
    
def check_gemma4_in_ollama(health: dict) -> dbc.Alert | None:
    """
    Devuelve un dbc.Alert de advertencia si Gemma 4 NO está en los modelos locales.
    Devuelve None si está presente o si Ollama no está activo (no hay nada que advertir).
    Es meramente informativo — no bloquea nada.
    """
    if not health.get("ollama_available", False):
        return None  # Ollama no está, la advertencia no aplica
 
    local_models = health.get("local_models", [])
    gemma4_base = GEMMA4_MODEL_NAME.split(":")[0]
 
    gemma4_present = any(gemma4_base in m or "gemma4" in m or "gemma-4" in m for m in local_models)
 
    if gemma4_present:
        return None
 
    return dbc.Alert(
        [
            html.I(className="fa-solid fa-triangle-exclamation me-2"),
            html.Strong("Gemma 4 no detectada en Ollama./لم يتم اكتشاف الجوهرة 4 في أولاما./Gemma 4 non détectée dans Ollama."),
            html.Br(),
            html.Small(
                "Para instalar: ollama pull gemma4:latest/لتثبيت: ollama pull gemma4:latest/Pour installer : ollama pull gemma4:latest",
                className="text-muted"
            ),
        ],
        color="warning",
        dismissable=True,
        is_open=True,
        style={"fontSize": "0.85em", "marginBottom": "8px"},
        id="gemma4-warning-alert",
    )


def build_marker(resource: dict) -> dl.CircleMarker:
    """CircleMarker coloreado por categoría, con popup completo."""
    color = CATEGORY_COLORS_LOCAL.get(resource["category"], "#555555")
    languages_str = ", ".join(resource.get("languages", [])) or "No especificado"
    phone_str = resource.get("phone") or "No disponible"
    requirements_str = resource.get("requirements") or "Sin requisitos específicos"
 
    popup_content = html.Div([
        html.H6(resource["organization"],
                style={"color": color, "fontWeight": "700", "marginBottom": "6px"}),
        html.P([html.B("Servicio: "), resource["service"]], style={"margin": "2px 0"}),
        html.P([html.B("Dirección: "), resource["address"]], style={"margin": "2px 0"}),
        html.P([html.B("Teléfono: "), phone_str], style={"margin": "2px 0"}),
        html.P([html.B("Idiomas: "), languages_str], style={"margin": "2px 0"}),
        html.P([html.B("Requisitos: "), requirements_str],
               style={"margin": "2px 0", "fontSize": "0.85em", "color": "#666"}),
    ], style={"fontSize": "0.9em", "minWidth": "200px"})
 
    return dl.CircleMarker(
        center=[resource["lat"], resource["lon"]],
        radius=10,
        color=color,
        fillColor=color,
        fillOpacity=0.85,
        weight=2,
        children=[
            dl.Tooltip(resource["organization"], sticky=True),
            dl.Popup(popup_content, maxWidth=280),
        ],
       id={"type": "map-marker", "index": f"{resource['id']}-{resource['lat']}-{resource['lon']}"},
    )

def build_user_marker() -> dl.CircleMarker:
    """Marcador que representa la posición simulada del usuario."""
    lat, lon = MOCK_USER_POSITION

    return dl.Marker(
        position=[lat, lon],
        children=[
              dl.Tooltip("📍 Tu ubicación (simulada)", sticky=True),
              dl.Popup(
                  html.Div([
                      html.B("📍 Tu posición actual (simulada)"),
                      html.Br(),
                      html.Small(f"Lat: {lat}  |  Lon: {lon}",
                                 style={"color": "#666"}),
                  ], style={"fontSize": "0.9em"})
              ),
        ],
        id="user-position-marker",
    )


def make_bubble(text: str, role: str) -> dbc.Card:
    """Crea un mensaje de chat con estilo de burbuja"""
    is_user = role == "user"
    return dbc.Card(
        dbc.CardBody(text, style={"padding": "8px 14px", "fontSize": "0.9em", "whiteSpace": "pre-wrap"}),
        color="primary" if is_user else "light",
        inverse=is_user,
        style={
            "maxWidth": "82%",
            "alignSelf": "flex-end" if is_user else "flex-start",
            "marginBottom": "8px",
            "borderRadius": "16px" if is_user else "16px",
            "border": "none",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
        },
    )

#carga inicial de datos
initial_resources = fetch_map_resources_local()
initial_health = fetch_system_health()

#App

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.FLATLY,
        dbc.icons.FONT_AWESOME,
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Mono&display=swap",
    ],
    serve_locally=True,
    suppress_callback_exceptions=True,
    title="RefugeeConnect AI",
)
server = app.server

#leyenda del mapa
legend = dbc.Card([
    dbc.CardBody([
        html.P("Categorías", className="fw-bold mb-2", style={"fontSize": "0.8em", "textTransform": "uppercase", "letterSpacing": "0.08em"}),
        *[
            html.Div([
                html.Span("●", style={"color": color, "fontSize": "1.2em", "marginRight": "6px"}),
                html.Span(CATEGORY_LABELS_LOCAL[cat], style={"fontSize": "0.85em"}),
            ], className="mb-1")
            for cat, color in CATEGORY_COLORS_LOCAL.items()
        ]
    ])
], style={"position": "absolute", "bottom": "30px", "right": "10px", "zIndex": "1000",
          "minWidth": "130px", "boxShadow": "0 2px 8px rgba(0,0,0,0.15)", "fontSize": "0.9em"})

#mapa
map_component = html.Div([
    dl.Map(
        id="map-refugee",
        center=[39.4697, -0.3774],
        zoom=13,
        children=[
            dl.TileLayer(
                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                attribution='&copy; <a href="https://carto.com/">CARTO</a>',
                maxZoom=19,
            ),
            dl.LayerGroup(
                id="marker-layer",
                children=[],
            ),
        ],
        style={"width": "100%", "height": "72vh", "borderRadius": "12px"},
    ),
    legend,
], style={"position": "relative"})

#filtros del mapa
filter_panel = dbc.Card([
    dbc.CardBody([
        html.P(id="head-filter",children = "Filtrar por categoría", className="fw-bold mb-2",
               style={"fontSize": "0.8em", "textTransform": "uppercase", "letterSpacing": "0.08em"}),
        dbc.ButtonGroup(
            [
                dbc.Button(
                    [html.I(className=f"fa-solid {CATEGORY_ICONS[cat]} me-1"), CATEGORY_LABELS_LOCAL[cat]],
                    id={"type": "filter-btn", "index": cat},
                    color="light",
                    size="sm",
                    style={"borderLeft": f"3px solid {CATEGORY_COLORS_LOCAL[cat]}"},
                    className="mb-1",
                )
                for cat in ALL_CATEGORIES
            ] + [
                dbc.Button("Todos/All/الجميع/Tous", id="filter-btn-all", color="secondary", size="sm", className="mb-1")
            ],
            vertical=True,
            style={"width": "100%"},
        ),
        html.Hr(style={"margin": "10px 0"}),
        html.P(id="resource-count", className="text-muted mb-0",
               style={"fontSize": "0.8em"}),
    ])
], style={"height": "100%"})


#Chat
chat_panel = dbc.Card([
    dbc.CardHeader([
        html.I(className="fa-solid fa-robot me-2"),
        html.Span(id="IA_title",children="Asistente IA para Refugiados"),
        html.Span(" · Cargando...", id="active-model-display", style={"fontSize": "0.8em", "color": "#aaa", "marginLeft": "4px"}),
        dcc.Loading(
            html.Div(id="loading-indicator", style={"display": "inline"}),
            type="circle",
            style={"marginLeft": "8px"},
        ),
        html.P(id="local_model_display", children="Modelo Local", className="fw-bold mb-1 mt-2", style={"fontSize": "0.75em"}),
        dcc.Dropdown(
            id="local-model-dropdown",
            # Los cargaremos dinámicamente
            options=[{"label": m, "value": m} for m in initial_health.get("local_models", [])],
            value=initial_health.get("local_models", [None])[0] if initial_health.get("local_models") else [""],
            style={"fontSize": "0.8em", "color": "#333"}
        ),
        html.P(id="cloud-model-display",children= "Modelo Cloud", className="fw-bold mb-1 mt-2", style={"fontSize": "0.75em"}),
        dcc.Dropdown(
            id="cloud-model-dropdown",
            # Los cargaremos dinámicamente
            options=[DEFAULT_CLOUD_MODEL],
            value=DEFAULT_CLOUD_MODEL,
            style={"fontSize": "0.8em", "color": "#333"}
        ),
    ], style={"fontFamily": "'IBM Plex Sans', sans-serif", "fontWeight": "600"}),
    dbc.Checklist(
        options=[{"label": "Usar LLM Local (Ollama)", "value": 1}],
        value=[1] if initial_health.get("active_mode") == "local" else [],
        id="llm-switch",
        switch=True,
        style={"fontSize": "0.8em", "marginTop": "10px"}
    ),
    dbc.CardBody([
        html.Div(
            id="chat-history",
            style={
                "height": "48vh",
                "overflowY": "auto",
                "display": "flex",
                "flexDirection": "column",
                "padding": "4px",
            },
            children=[
                make_bubble(
                    "Hola/Hello/مرحبا/Bonjour 👋",
                    "bot"
                )
            ]
        ),
        html.Div(
            id="chat-status-bar",
            children = "Puedo ayudarte ¿Qué necesitas?/I can help you. What do you need?/يمكنني مساعدتك. ماذا تحتاج؟/Je peux vous aider. De quoi avez-vous besoin?",
            style={"minHeight": "24px", "padding": "2px 4px"},
            
        ),
        html.Hr(style={"margin": "8px 0"}),
        dbc.InputGroup([
            dbc.Input(
                id="user-input",
                placeholder="Escribe en tu idioma ...",
                type="text",
                style={"fontFamily": "'IBM Plex Sans', sans-serif"},
            ),
            dbc.Button(
                html.I(className="fa-solid fa-paper-plane"),
                id="send-btn",
                color="primary",
                n_clicks=0,
            ),
        ]),
        html.P(
            id="input-placeholder2",
            children = "Responde en árabe, francés, inglés, español y otros idiomas.",
            className="text-muted mt-1 mb-0",
            style={"fontSize": "0.75em"},
        ),
    ]),
], style={"height": "72vh", "fontFamily": "'IBM Plex Sans', sans-serif"})


#layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H4(
                    id="title",
                    children=[html.I(className="fa-solid fa-earth-europe me-2"), "RefugeeConnect AI"],
                    className="mb-0",
                    style={"fontFamily": "'IBM Plex Sans', sans-serif", "fontWeight": "700"},
                ),
                html.Span(id="status-badge"),
            ], className="d-flex align-items-center"),
            html.P(
                id="subtitle",
                children="Asistencia humanitaria geolocalizada · Valencia, España",
                className="text-muted mb-0",
                style={"fontSize": "0.85em", "fontFamily": "'IBM Plex Sans', sans-serif"},
            ),
        ], width=8),
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button(
                    [html.I(className="fa-solid fa-rotate me-1"), "Actualizar mapa"],
                    id="refresh-map-btn",
                    color="outline-secondary",
                    size="sm",
                ),
                dbc.Button(
                    [html.I(className="fa-solid fa-heart-pulse me-1"), "Estado sistema"],
                    id="health-btn",
                    color="outline-secondary",
                    size="sm",
                ),
            ], className="float-end"),
        ], width=4),
        dbc.Col([
            dbc.Select(
                id="language-selector",
                options=[
                    {"label": "ES Español", "value": "es"},
                    {"label": "EN English", "value": "en"},
                    {"label": "AR العربية", "value": "ar"},
                    {"label": "FR Français", "value": "fr"},
                ],
                value="es",
                size="sm",
                style={"width": "140px", "marginLeft": "10px"}
            )
        ], width=4)
    ], className="mt-3 mb-3 pb-2 border-bottom"),
    html.Div(id="gemma4-warning-container"),
    #cuerpo principal
    dbc.Row([
        # Columna izquierda: filtros + chat
        dbc.Col([
            dbc.Row([
                dbc.Col(filter_panel, width=12),
            ], className="mb-2", style={"maxHeight": "25vh"}),
            dbc.Row([
                dbc.Col(chat_panel, width=12),
            ]),
        ], width=4),

        # Columna derecha: mapa
        dbc.Col(map_component, width=8),
    ]),

    # modal de estado del sistema
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Estado del sistema")),
        dbc.ModalBody(id="health-modal-body"),
    ], id="health-modal", is_open=False),
    html.Div([
    dbc.Toast(
        "Configuración actualizada correctamente",
        id="config-toast",
        header="Sistema",
        is_open=False,
        dismissable=True,
        duration=3000,
        icon="success",
        style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
    )
    ], id="toast-container"),

    # Stores
    dcc.Store(id="session-store", data=SESSION_ID),
    dcc.Store(id="active-category-store", data=None),  # None = todas

], fluid=True, style={"fontFamily": "'IBM Plex Sans', sans-serif"})

#callbacks

@app.callback(
    Output("marker-layer", "children"),
    Output("resource-count", "children"),
    Output("active-category-store", "data"),
    Output("filter-btn-all", "color"),
    Output({"type": "filter-btn", "index": dash.ALL}, "color"),
    Input({"type": "filter-btn", "index": dash.ALL}, "n_clicks"),
    Input("filter-btn-all", "n_clicks"),
    Input("refresh-map-btn", "n_clicks"),
    State("active-category-store", "data"),
    prevent_initial_call=False,
)
def update_map_markers(category_clicks, all_clicks, refresh_clicks, active_category):
    """Actualiza los marcadores del mapa según la categoría seleccionada."""
    ctx = dash.callback_context
    new_category = active_category

    if ctx.triggered:
        trigger_id = ctx.triggered[0]["prop_id"]
        if "filter-btn-all" in trigger_id:
            new_category = None
        elif "filter-btn" in trigger_id:
            import json
            try:
                # Extraemos el ID del botón presionado
                id_dict = json.loads(trigger_id.split(".")[0])
                new_category = id_dict.get("index")
            except Exception:
                new_category = None

    
    resources = fetch_map_resources_local(category=new_category)
    markers = [build_user_marker()] + [build_marker(r) for r in resources]

    count_text = (
        f"{len(resources)} sedes encontradas"
        + (f" · {new_category}" if new_category else " · Todas las categorías")
    )

    all_btn_color = "secondary" if new_category is None else "light"

    category_btn_colors = [
        "secondary" if cat == new_category else "light" 
        for cat in ALL_CATEGORIES
    ]
    return markers, count_text, new_category, all_btn_color, category_btn_colors


@app.callback(
    Output("chat-history", "children"),
    Output("user-input", "value"),
    Input("send-btn", "n_clicks"),
    Input("user-input", "n_submit"),
    State("user-input", "value"),
    State("chat-history", "children"),
    State("session-store", "data"),
    running=[
        (Output("send-btn", "disabled"), True, False),
        (Output("user-input", "disabled"), True, False),
        (Output("chat-status-bar", "children"),
            # Mientras corre → spinner visible
            dbc.Spinner(
                html.Span(" El asistente está pensando...",
                          style={"fontSize": "0.82em", "color": "#888", "verticalAlign": "middle"}),
                size="sm", color="primary", type="border",
                spinner_style={"marginRight": "6px", "verticalAlign": "middle"},
            ),
            "",
        ),
    ],
    allow_duplicate=True,
    prevent_initial_call=True,
)
def handle_chat(n_clicks, n_submit, user_text, chat_history, session_id):
    """Envía el mensaje al orquestador y actualiza el historial del chat."""
    if not user_text or not user_text.strip():
        return no_update, no_update, no_update

    chat_history = chat_history or []
    if not isinstance(chat_history, list):
        if isinstance(chat_history, str):
            chat_history = [chat_history]
        else:
            chat_history = []
    
    try:
        lat, lon = MOCK_USER_POSITION

        resp = requests.post(
            f"{API_BASE}/query",
            json={"message": user_text, 
                  "session_id": session_id, 
                  "user_id": "anonymous_user",
                  "user_position": [lat,lon],
                  },
            timeout=180,
        )
        resp.raise_for_status()
        bot_text = resp.json().get("response", "Sin respuesta del asistente.")
    except requests.Timeout:
        logger.warning("El asistente tardó demasiado en responder.")
        bot_text = "⏱ El asistente tardó demasiado en responder. Inténtalo de nuevo."
    except requests.ConnectionError:
        logger.warning("No se puede conectar con el servidor.")
        bot_text = "🔌 No se puede conectar con el servidor. ¿Está corriendo la API?"
    except Exception as e:
        logger.warning(f"Error inesperado: {str(e)}")
        bot_text = f"❌ Error inesperado: {str(e)}"

    new_history = [make_bubble(bot_text, "bot"), make_bubble(user_text, "user")] + chat_history

    return new_history, ""


@app.callback(
    Output("health-modal", "is_open"),
    Output("health-modal-body", "children"),
    Output("local-model-dropdown","options"),
    Input("health-btn", "n_clicks"),
    State("health-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_health_modal(n_clicks, is_open_modal):
    """Abre/cierra el modal de estado del sistema y muestra el health check. Además actualiza el dropdown de modelos locales disponibles."""
    if not n_clicks:
        return False, no_update

    health = fetch_system_health()

    status = health.get("status", "unavailable")

    local_models = health.get('local_models', [])
    options=[]
    if local_models:
        for model in local_models:
            options.append({"label": f"Ollama: {model}", "value": f"ollama:{model}"})

    color_map = {"healthy": "success", "degraded": "warning", "unavailable": "danger"}

    body = dbc.Table([
        html.Tbody([
            html.Tr([html.Td("Estado"), html.Td(dbc.Badge(status, color=color_map.get(status, "secondary")))]),
            html.Tr([html.Td("Modo activo"), html.Td(health.get("active_mode", "?"))]),
            html.Tr([html.Td("Ollama disponible"), html.Td("✅" if health.get("ollama_available") else "❌")]),
            html.Tr([html.Td("Host Ollama"), html.Td(health.get("ollama_host", "-"))]),
            html.Tr([html.Td("Modelos locales"), html.Td(", ".join(health.get("local_models", [])) or "—")]),
            html.Tr([html.Td("Modelo cloud"), html.Td(DEFAULT_CLOUD_MODEL)]),
            html.Tr([html.Td("Google API Key"), html.Td("✅ Configurada" if health.get("google_api_key_set") else "❌ No configurada")]),
            html.Tr([html.Td("AgentManager"), html.Td("✅ Listo" if health.get("agent_manager_ready") else "❌ No inicializado")]),
        ])
    ], bordered=True, hover=True, size="sm")

    return not is_open_modal, body, options

@app.callback(
    Output("active-model-display", "children"),
    Output("status-badge", "children"),
    Input("health-btn", "n_clicks"),
    Input("session-store", "data")
)
def update_status_indicators(n_clicks, session_id):
    """Actualiza el texto del modelo activo y el badge de estado cada vez que se consulta el health check 
    o cambia la sesión (por si se reinicia el backend)."""
    health = fetch_system_health()

    if health is None or health.get("status")=="unavailable":
        badge = dbc.Badge(
            "API OFFLINE",
            color="danger",
            className="ms-2",
            style={"fontSize": "0.6em"}
        )
        return " · API no disponible", badge

    mode = health.get("active_mode", "").upper()

    if mode == "LOCAL":
        badge_color = "success"
        model_text = f" · Ollama ({health.get('local_models', ['?'])[0]})"
    elif mode == "CLOUD":
        badge_color = "info"
        model_text = " · Google Cloud (Gemma 4)"
    else:
        badge_color = "warning"
        model_text = " · Modo desconocido"

    badge = dbc.Badge(mode, color=badge_color, className="ms-2", style={"fontSize": "0.6em"})
    return model_text, badge

@app.callback(
    [
        Output("gemma4-warning-container", "children"),
        Output("llm-switch", "value"),
        Output("config-toast", "is_open"),
    ],
    [
        Input("llm-switch", "value"),
        Input("local-model-dropdown", "value")
    ],
    prevent_initial_call=True
)
def toggle_backend_mode(switch_value, selected_local_model):
    """Permite cambiar entre backend local (Ollama) y cloud (Google Gemma 4) 
    y muestra advertencias si Ollama no está disponible o no tiene Gemma 4."""
    use_local = len(switch_value) > 0
    
    health = fetch_system_health()
    alert = check_gemma4_in_ollama(health)

    if use_local and not (health.get("ollama_available", False) and (selected_local_model is None or selected_local_model!= [""])):
        warning_msg = dbc.Alert(
            "⚠️ Please check Ollama is running and select a Gemma 4 model/يرجى التحقق من أن Ollama يعمل واختر نموذج Gemma 4/Veuillez vérifier qu'Ollama fonctionne et sélectionner un modèle Gemma 4",
            color="warning",
            dismissable=True
        )
        return warning_msg, [], True

    payload = {
        "use_local": use_local,
        "model_name_cloud": DEFAULT_CLOUD_MODEL,
        "model_name_local": selected_local_model,
    }
    
    try:
        resp = requests.post(f"{API_BASE}/config/toggle", json=payload, timeout=15)
        
        if resp.status_code == 200:
            logger.info(f"Backend toggled to {'Local' if use_local else 'Cloud'}")
            if alert is not None and use_local:
                return alert, switch_value, True
            else:
                return None, switch_value, True
        
        elif resp.status_code == 503:
            error_detail = resp.json().get("detail", "Local backend unreachable.")
            error_alert = dbc.Alert(
                f"❌ Connection Error: {error_detail}",
                color="danger",
                dismissable=True
            )
            return error_alert, [], True # Revertimos switch y mostramos error

    except Exception as e:
        logger.error(f"Critical connection error: {e}")
        error_alert = dbc.Alert(
            "🚀 API Server is offline",
            color="danger"
        )
        return error_alert, [], True

    return no_update, no_update, no_update

@app.callback(
    [
        Output("title", "children"),
        Output("subtitle", "children"),
        Output("refresh-map-btn", "children"),
        Output("health-btn", "children"),
        Output("head-filter","children"),
        Output("IA_title", "children"),
        Output("local_model_display", "children"),
        Output("cloud-model-display", "children"),
        Output("llm-switch", "options"),
        Output("user-input", "placeholder"),
        Output("input-placeholder2", "children"),
    ],
    [Input("language-selector", "value")],
    allow_duplicate=True,
    prevent_initial_call=True
)
def update_language(lang):
    """Actualiza todos los textos configurados como tal de la interfaz según el idioma seleccionado."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS["es"])
    
    # mantenemos los formatos
    title = [html.I(className="fa-solid fa-earth-europe me-2"), t["title"]]
    refresh_map_btn = [html.I(className="fa-solid fa-rotate me-1"), t["refresh-map-btn"]]
    health_btn = [html.I(className="fa-solid fa-heart-pulse me-1"), t["health-btn"]]
    new_options = [{"label": t["llm_switch_label"], "value": 1}]
    
    return [title, t["subtitle"], refresh_map_btn, health_btn,t["head-filter"],t["IA_title"],
            t["local_model_display"],t["cloud-model-display"],new_options,
            t["input_placeholder"],t["input_placeholder2"]]


@app.callback(
    Output("chat-history", "style"),
    Input("language-selector", "value"),
    State("chat-history", "style")
)
def adjust_chat_direction(lang, current_style):
    """Ajusta la dirección del texto en el historial del chat según el idioma seleccionado (RTL para árabe)."""
    new_style = current_style.copy()
    if lang == "ar":
        new_style["direction"] = "rtl"
        new_style["textAlign"] = "right"
    else:
        new_style["direction"] = "ltr"
        new_style["textAlign"] = "left"
    return new_style

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8601, debug=True)