import sqlite3
import pandas as pd
from pathlib import Path
import json
import requests as _requests


from .logger import setup_logger


logger = setup_logger('tools')

DB_PATH = Path(__file__).resolve().parents[2] / "common" / "data" / "refugeeconnect.db"

_OSRM_BASE = "http://router.project-osrm.org/route/v1/driving/"

# Colores por categoría — compartidos con el frontend para coherencia visual
CATEGORY_COLORS = {
    "Legal":       "#E74C3C",   # rojo
    "Salud":       "#27AE60",   # verde
    "Alojamiento": "#2980B9",   # azul
    "Comida":      "#F39C12",   # naranja
    "Empleo":      "#8E44AD",   # morado
}

VALID_CATEGORIES = list(CATEGORY_COLORS.keys())


def _get_connection():
    """Conexión reutilizable con row_factory para acceso por nombre de columna."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_services_by_category(category: str, city: str = "Valencia") -> str:
    """
    Find organizations that provide specific services in a Spanish city.

    This tool queries the SQLite database. Search terms.

    MUST be in SPANISH exactly as they appear in the database.

    Args:
        category (str): The service category to search for (Always spanish).
                        Valid values: 'Legal', 'Salud', 'Alojamiento', 'Comida', 'Empleo'.
        city (str): The city name to filter results. Defaults to "Valencia".

    Returns:
        str: A list of dictionaries converted to string, containing organization details, 
                    services, requirements, and contact info. Returns a 
                    list with an 'error' or 'info' key if no data is found 
                    or an exception occurs.
    """
    if category not in VALID_CATEGORIES:
        logger.error(f"Categoría '{category}' no válida.")
        return json.dumps([{
            "error": f"Invalid category '{category}'. Supported: {', '.join(VALID_CATEGORIES)}"
        }], ensure_ascii=False)

    try:
        conn = _get_connection()
        query = """
            SELECT
                b.id            AS id,
                o.name          AS organizacion,
                s.name          AS servicio,
                s.category      AS categoria,
                b.address       AS direccion,
                b.local_phone   AS telefono,
                bs.requirements AS requisitos,
                bs.notes        AS notas
            FROM branches b
            JOIN organizations o ON b.organization_id = o.id
            JOIN branch_services bs ON b.id = bs.branch_id
            JOIN services s ON bs.service_id = s.id
            WHERE s.category = ? AND b.city = ?
            ORDER BY o.name
        """
        df = pd.read_sql_query(query, conn, params=(category, city))
        conn.close()

        bloque_datos = f"--- DATABASE RESULTS FOR {category.upper()} IN {city.upper()} ---\n"

        if df.empty:
            logger.warning(f"No se encontraron recursos de '{category}' en {city}.")
            bloque_datos += f"No local services found in {city} for this category {category}.\n"
            return bloque_datos
        lines = []

        for _, row in df.iterrows():
            id_val = row.get("id", "N/A")
            org = row.get("organizacion", "N/A")
            servicio = row.get("servicio", "N/A")
            direccion = row.get("direccion", "N/A")
            telefono = row.get("telefono", "N/A")
            requisitos = row.get("requisitos", "N/A")
            notas = row.get("notas", "")

            lines.append(f"id: {id_val}|Organization: {org} | Service: {servicio} | Address: {direccion} | Telephone: {telefono} | Requirements: {requisitos} | Notas: {notas}")
        
        # 3. Obtener los derechos legales/sociales
        rights_raw = get_rights(category=category)
        rights_dict = json.loads(rights_raw)

        
        bloque_datos += "\n".join(lines)
        
        derechos = "\n".join([f"- {d}" for d in rights_dict.get("derechos_fundamentales", [])])
        emergencias = "\n".join([f"- {e}" for e in rights_dict.get("contactos_emergencia", [])])

        # Añadir Derechos y Alertas
        bloque_datos += f"\n--- LEGAL RIGHTS & ALERTS (IMPORTANT) ---\n{derechos}\n"
        bloque_datos += f"\n--- EMERGENCY CONTACTS ---\n{emergencias}\n"
        
        return bloque_datos

    except Exception as e:
        logger.error(f"Error consultando la base de datos: {e}")
        return f"error: Error consultando la base de datos: {str(e)}"


def get_rights(category: str) -> str:
    """
    Returns rights, legal warnings and emergency contacts for refugees in Spain,
    filtered by service category.
    
    Args:
        category: Service category. Must be one of: Legal, Salud, Alojamiento, Comida, Empleo.
    
    Returns:
        A dict converted to a string with keys  and relevant rights and emergency contacts.
    """
    RIGHTS_SNIPPETS = {
    "Legal": [
        "Tienes derecho a solicitar asilo aunque hayas entrado de forma irregular. La forma de entrada no afecta tu derecho a protección.",
        "Tienes 30 días hábiles desde tu llegada para formalizar la solicitud de asilo en una comisaría o Oficina de Asilo.",
        "Durante el proceso recibirás una tarjeta roja provisional. Esa tarjeta te protege de la expulsión mientras se resuelve tu caso.",
        "Tienes derecho a un intérprete gratuito en todas las entrevistas con la administración. Puedes pedirlo siempre.",
        "La asistencia jurídica gratuita es tu derecho en cualquier procedimiento que pueda derivar en expulsión. No tienes que pagarla.",
        "ALERTA: Si alguien te cobra dinero para tramitar tu solicitud de asilo, es una estafa. La solicitud es completamente gratuita.",
        "ALERTA: Desconfía de 'gestores' o 'abogados' que no puedan mostrarte su número de colegiación. Verifica en el Colegio de Abogados local.",
        "Puedes denunciar irregularidades de la administración en el Defensor del Pueblo: 900 101 025 (gratuito).",
    ],

    "Salud": [
        "Tienes derecho a atención de urgencias en cualquier hospital público de España, sin importar tu situación documental y sin coste.",
        "Los menores de edad tienen derecho a atención sanitaria completa, no solo urgencias, independientemente de su situación o la de sus padres.",
        "Las mujeres embarazadas tienen derecho a atención durante el embarazo, parto y postparto aunque estén en situación irregular.",
        "Para acceder a atención primaria (médico de cabecera) necesitas estar empadronada/o. El padrón es gratuito y es tu derecho.",
        "Puedes pedir intérprete en centros de salud públicos. Si no lo ofrecen, tienes derecho a solicitarlo formalmente.",
        "ALERTA: Ningún centro de salud público puede pedirte dinero por adelantado en una urgencia. Si ocurre, es ilegal.",
        "ALERTA: Desconfía de clínicas que ofrecen 'regularización a cambio de tratamiento' o similares. No existe ese vínculo legal.",
        "Salud mental: Cruz Roja y ACNUR ofrecen apoyo psicológico gratuito para solicitantes de asilo. No tienes que atravesar esto solo/a.",
    ],

    "Alojamiento": [
        "El empadronamiento (padrón municipal) es tu derecho aunque no seas propietario ni tengas contrato. El ayuntamiento no puede negártelo.",
        "Para empadronarte sin domicilio fijo, muchos ayuntamientos aceptan la dirección de una asociación o albergue. Pregunta en el ayuntamiento.",
        "Todo arrendamiento debe tener contrato escrito. Sin contrato no tienes protección legal si el arrendador te echa o no te devuelve la fianza.",
        "La fianza legal es de una mensualidad para vivienda habitual. Si te piden más de dos meses, puede ser abusivo.",
        "ALERTA: Nadie puede quitarte las llaves o sacarte del piso sin orden judicial, aunque no tengas contrato. Eso se llama allanamiento.",
        "ALERTA: Desconfía de pisos que se anuncian muy baratos y piden transferencia antes de verlos. Es una estafa muy común contra recién llegados.",
        "ALERTA: Si comparten piso muchas personas en condiciones muy precarias, puede ser una situación de explotación. Puedes denunciar de forma anónima llamando al 112.",
        "Cruz Roja, Cáritas y ACNUR tienen programas de alojamiento de emergencia. No tienes que estar en situación regular para acceder.",
    ],

    "Comida": [
        "Tienes derecho a acceder a bancos de alimentos y comedores sociales sin importar tu situación documental.",
        "Con el padrón municipal puedes acceder a ayudas de emergencia del ayuntamiento, incluyendo tarjetas de alimentación en muchos municipios.",
        "Cruz Roja y Cáritas ofrecen ayuda alimentaria sin exigir documentación. Solo necesitas presentarte.",
        "Si tienes hijos en edad escolar, tienen derecho a comedor escolar con beca. Pregunta en el colegio o en los servicios sociales municipales.",
        "ALERTA: Ninguna organización legítima te pedirá dinero, favores o información personal sensible a cambio de alimentos.",
        "ALERTA: Desconfía de grupos en redes sociales que ofrecen ayuda alimentaria a cambio de trabajo no remunerado o en condiciones poco claras.",
        "Los servicios sociales municipales son gratuitos y confidenciales. Pueden orientarte sobre todos los recursos disponibles en tu ciudad.",
    ],

    "Empleo": [
        "Como solicitante de asilo, tienes autorización para trabajar a los 6 meses de haber presentado la solicitud, mientras se resuelve tu caso.",
        "Todo trabajo debe tener contrato escrito y alta en la Seguridad Social. Sin alta, no tienes cobertura si sufres un accidente laboral.",
        "El salario mínimo interprofesional (SMI) aplica a todos los trabajadores en España, sin excepción de nacionalidad o situación migratoria.",
        "Tienes derecho a los mismos descansos, vacaciones y condiciones que cualquier otro trabajador. La ley laboral no distingue por origen.",
        "ALERTA: Nadie puede retenerte el pasaporte, tarjeta roja ni ningún documento personal. Es ilegal y puede ser un indicador de trata.",
        "ALERTA: Si te ofrecen trabajo sin contrato prometiendo 'arreglarte los papeles después', es casi siempre falso y te deja en situación de vulnerabilidad.",
        "ALERTA: Los 'contratos de formación' sin remuneración ofrecidos por particulares no son legales. Todo trabajo remunerado requiere contrato laboral.",
        "Si no te pagan o sufres condiciones abusivas, puedes reclamar en el SMAC (Servicio de Mediación Arbitraje y Conciliación) de forma gratuita.",
        "UGT, CCOO y muchos sindicatos locales ofrecen asesoría laboral gratuita para migrantes y refugiados.",
    ],

    "_emergencia": [
        "EMERGENCIAS: 112 (gratuito, intérprete disponible, funciona sin tarjeta SIM)",
        "VIOLENCIA DE GÉNERO: 016 (gratuito, no aparece en la factura del teléfono)",
        "DEFENSOR DEL PUEBLO: 900 101 025 (gratuito, quejas contra la administración)",
        "ACNUR ESPAÑA: +34 91 556 3614",
        "CRUZ ROJA: 900 22 11 22 (gratuito)",
        "CÁRITAS: consulta delegación local en caritas.es",
    ],
    }
    rights = RIGHTS_SNIPPETS.get(category, [])
    
    emergency = RIGHTS_SNIPPETS.get("_emergencia", [])

    #bajamos a 2 puntos clave para que el orquestador no se sature con tanta información
    data_response = {
        "categoria_consultada": category,
        "derechos_fundamentales": rights[:2] if rights else [], 
        "contactos_emergencia": emergency 
    }
    
    return json.dumps(data_response, ensure_ascii=False)



def get_map_resources(city: str = "Valencia", category: str | None = None) -> list[dict]:
    """
    Consulta TODAS las sedes con coordenadas para pintar el mapa del dashboard.
    A diferencia de get_services_by_category, incluye lat/lon y agrega idiomas.
    
    Usado por: endpoint /map/resources de la API (NO por agentes ADK).
    
    Args:
        city:     Ciudad a consultar.
        category: Si se pasa, filtra por categoría. Si es None, devuelve todo.
    
    Returns:
        Lista de dicts con: id, organization, service, category, address,
        phone, lat, lon, languages, requirements.
    """
    try:
        conn = _get_connection()

        category_filter = "AND s.category = :category" if category else ""

        query = f"""
            SELECT
                b.id            AS id,
                o.name          AS organization,
                s.name          AS service,
                s.category      AS category,
                b.address       AS address,
                b.local_phone   AS phone,
                b.latitude      AS lat,
                b.longitude     AS lon,
                bs.requirements AS requirements
            FROM branches b
            JOIN organizations o ON b.organization_id = o.id
            JOIN branch_services bs ON b.id = bs.branch_id
            JOIN services s ON bs.service_id = s.id
            WHERE b.city = :city
              AND b.latitude IS NOT NULL
              AND b.longitude IS NOT NULL
              {category_filter}
            ORDER BY s.category, o.name
        """

        params = {"city": city}
        if category:
            params["category"] = category

        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # agrupar idiomas por branch id para evitar N+1 queries
        branch_ids = list({row["id"] for row in rows})
        languages_map: dict[int, list[str]] = {bid: [] for bid in branch_ids}

        if branch_ids:
            placeholders = ",".join("?" * len(branch_ids))
            lang_query = f"""
                SELECT branch_id, language_code
                FROM languages_served
                WHERE branch_id IN ({placeholders})
            """
            lang_cursor = conn.cursor()
            lang_cursor.execute(lang_query, branch_ids)
            for lang_row in lang_cursor.fetchall():
                languages_map[lang_row["branch_id"]].append(lang_row["language_code"])

        conn.close()

        resources = []
        for row in rows:
            resources.append({
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
            })

        return resources

    except Exception as e:
        logger.error(f"[tools] Error en get_map_resources: {e}")
        return []
    
def get_distances(user_position: tuple, branch_ids: list[int]) -> str:
    """
    Calculate the distance and driving time between the user's location 
    and each indicated branch, using OSRM (OpenStreetMap routing).

    Args:
        user_position: Tuple (latitude, longitude) of the user.
        branch_ids: List of branch IDs to query.

    Returns:
        JSON string with a list of objects: 
        [{"branch_id": int, "distance_km": float, "duration_min": float}, ...] 
        or an error message if something fails.
    """

    if not user_position or len(user_position) < 2:
        return "ERROR: user_position inválida."
    if not branch_ids:
        return "ERROR: No se proporcionaron IDs de sucursales."

    lat_orig, lon_orig = float(user_position[0]), float(user_position[1])

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        placeholders = ", ".join(["?"] * len(branch_ids))
        rows = conn.execute(
            f"SELECT id, latitude AS lat, longitude AS lon FROM branches WHERE id IN ({placeholders})",
            branch_ids,
        ).fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Error consultando la base de datos para distancias: {e}")
        return f"ERROR al consultar BD: {e}"

    if not rows:
        logger.warning("No se encontraron sucursales con esos IDs.")
        return "ERROR: No se encontraron sucursales con esos IDs."

    # --- Calcular rutas con OSRM ---
    results = []
    for row in rows:
        bid, lat_dst, lon_dst = int(row["id"]), float(row["lat"]), float(row["lon"])
        coords = f"{lon_orig},{lat_orig};{lon_dst},{lat_dst}"
        try:
            resp = _requests.get(
                f"{_OSRM_BASE}{coords}",
                params={"overview": "false"},   #sin geometría → respuesta ligera
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == "Ok":
                route = data["routes"][0]
                results.append({
                    "branch_id":    bid,
                    "distance_km": round(route["distance"] / 1000, 2),
                    "duration_min": round(route["duration"] / 60, 1),
                })
            else:
                results.append({"branch_id": bid, "error": data.get("code", "OSRM error")})
        except Exception as e:
            logger.error(f"Error consultando OSRM para sucursal {bid}: {e}")
            results.append({"branch_id": bid, "error": str(e)})

    logger.info(f"Distancias calculadas para {len(results)} sucursales.")
    return json.dumps(results, ensure_ascii=False)

def get_comprehensive_refugee_help(category: str, city: str, lat: float, lon: float, language_answer: str) -> str:
    """
    Gets all the necessary information for a refugee: services, distances (if there is a location) and rights.
    Use this tool ONLY ONCE when the user indicates their need and their city.

    Args:
        category (str): REQUIRED. MUST BE EXACTLY ONE OF: "Legal", "Salud", "Alojamiento", "Comida", "Empleo".
        city (str): REQUIRED. The city name (default "Valencia").
        lat (float): REQUIRED latitude.
        lon (float): REQUIRED longitude.
        language_answer (str): Detected language from the user input in english (without abreviations).
    """

    if category not in VALID_CATEGORIES:
        logger.error(f"Categoría '{category}' no válida.")
        return json.dumps([{
            "error": f"Invalid category '{category}'. Supported: {', '.join(VALID_CATEGORIES)}"
        }], ensure_ascii=False)

    try:
        conn = _get_connection()
        query = """
            SELECT            
                b.id            AS id,
                o.name          AS organizacion,
                s.name          AS servicio,
                s.category      AS categoria,
                b.address       AS direccion,
                b.local_phone   AS telefono,
                bs.requirements AS requisitos,
                bs.notes        AS notas
            FROM branches b
            JOIN organizations o ON b.organization_id = o.id
            JOIN branch_services bs ON b.id = bs.branch_id
            JOIN services s ON bs.service_id = s.id
            WHERE s.category = ? AND b.city = ?
            ORDER BY o.name
            LIMIT 2
        """
        df = pd.read_sql_query(query, conn, params=(category, city))
        conn.close()
        
        rights_raw = get_rights(category=category)
        rights_dict = json.loads(rights_raw)
        
        derechos = "\n".join([f"- {d}" for d in rights_dict.get("derechos_fundamentales", [])])
        emergencias = "\n".join([f"- {e}" for e in rights_dict.get("contactos_emergencia", [])])

        # Construcción del cuerpo de datos
        bloque_datos = f"--- DATABASE RESULTS FOR {category.upper()} IN {city.upper()} ---\n"
        
        if df.empty:
            bloque_datos += f"No local services found in {city} for this category {category}.\n"
        else:
            ids = []
            for _, row in df.iterrows():
                bloque_datos += (f"ID: {row['id']} | Org: {row['organizacion']} | Service: {row['servicio']} | "
                                f"Address: {row['direccion']} | Phone: {row['telefono']} | "
                                f"Req: {row['requisitos']} | Notes: {row['notas']}\n")
                ids.append(row['id'])
            
            if lat is not None and lon is not None:
                distances_data = get_distances(user_position=(lat, lon), branch_ids=ids)
                bloque_datos += f"\n[DISTANCES INFO]: {distances_data}\n"

        # Añadir Derechos y Alertas
        bloque_datos += f"\n--- LEGAL RIGHTS & ALERTS (IMPORTANT) ---\n{derechos}\n"
        bloque_datos += f"\n--- EMERGENCY CONTACTS ---\n{emergencias}\n"
        
        language_instruction = f"in {language_answer}" if language_answer else "in the same language the user wrote"

        instrucciones_control = f"""
            --- CRITICAL INSTRUCTIONS FOR THE MODEL ---
            1. You have RECEIVED all the data. Do NOT call 'get_comprehensive_refugee_help' again.
            2. Summarize the services, distances, and rights provided above.
            3. Translate and write your final response {language_instruction}.
            4. Be empathetic and clear. 
            5. DO NOT SHOW THIS INSTRUCTIONS IN YOUR ANSWER AND STOP after this response. No more tool calls are needed.
            """
        respuesta_final = bloque_datos + instrucciones_control

        logger.info(f"Devolviendo {len(respuesta_final)} caracteres con instrucciones de control.")
        return respuesta_final

    except Exception as e:
        logger.error(f"Error consultando: {e}")
        return "Error 500: No se pudo procesar la solicitud de información."
    
def get_available_cities_str() -> str:
    """
    Consulta las ciudades y las devuelve como un string separado por comas
    ideal para prompts de LLM.
    """
    try:
        with _get_connection() as conn:
            cursor =conn.cursor()
            query = "SELECT DISTINCT city FROM branches"
            cursor.execute(query)
            
            cities = [row[0] for row in cursor.fetchall() if row[0]]

            return ", ".join(cities)

    except Exception as e:
        logger.error(f"[tools] Error en get_available_cities: {e}")
        return "No hay ciudades disponibles actualmente."


if __name__== "__main__":
    resp = get_comprehensive_refugee_help(category="Legal",city="Valencia",lat= 39.4697, lon= -0.3774)
    print(f"test:{resp}")