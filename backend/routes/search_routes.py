from flask import Blueprint, jsonify, request
from queries.search import (
    obtener_todos_los_sujetos,
    busqueda_combinada,
    obtener_clases,
    obtener_individuos,
    obtener_detalles_recurso,
)

busqueda_bp = Blueprint("busqueda", __name__)

# Mensajes de error multiidioma
MENSAJES_ERROR = {
    "es": {
        "uri_requerido": "Parámetro 'uri' requerido",
        "q_requerido": "Parámetro 'q' (búsqueda) requerido",
        "uri_no_encontrado": "Recurso no encontrado",
        "clase_invalida": "Clase URI inválida",
    },
    "en": {
        "uri_requerido": "Parameter 'uri' required",
        "q_requerido": "Parameter 'q' (search query) required",
        "uri_no_encontrado": "Resource not found",
        "clase_invalida": "Invalid class URI",
    },
}


def _obtener_mensaje_error(clave: str, idioma: str = "es") -> str:
    """Obtiene mensaje de error en el idioma solicitado."""
    return MENSAJES_ERROR.get(idioma, MENSAJES_ERROR["es"]).get(clave, clave)


# GET /search/details?uri=URI&lang=es
@busqueda_bp.route("/search/details")
def busqueda_detalles():
    uri = request.args.get("uri", "").strip()
    idioma = request.args.get("lang", "es")

    if not uri:
        return jsonify({"error": _obtener_mensaje_error("uri_requerido", idioma)}), 400

    detalles = obtener_detalles_recurso(uri, idioma=idioma)
    return jsonify(detalles)


# GET /search
@busqueda_bp.route("/search")
def busqueda():
    idioma = request.args.get("lang", "es")
    datos = obtener_todos_los_sujetos(idioma=idioma)
    return jsonify(datos)


# GET /search/query?q=futbol&lang=es&dbpedia=true
@busqueda_bp.route("/search/query")
def busqueda_consulta():
    palabra_clave = request.args.get("q", "").strip()
    idioma = request.args.get("lang", "es")
    usar_dbpedia = request.args.get("dbpedia", "true").lower() != "false"

    if not palabra_clave:
        return jsonify({"error": _obtener_mensaje_error("q_requerido", idioma)}), 400

    resultados = busqueda_combinada(
        palabra_clave, idioma=idioma, usar_dbpedia=usar_dbpedia
    )
    return jsonify(resultados)


# GET /search/classes?lang=es
@busqueda_bp.route("/search/classes")
def busqueda_clases():
    idioma = request.args.get("lang", "es")
    datos = obtener_clases(idioma=idioma)
    return jsonify(datos)


# GET /search/individuals?clase=URI&lang=es
@busqueda_bp.route("/search/individuals")
def busqueda_individuos():
    clase = request.args.get("clase", None)
    idioma = request.args.get("lang", "es")
    datos = obtener_individuos(uri_clase=clase, idioma=idioma)
    return jsonify(datos)


# GET /search/langs
@busqueda_bp.route("/search/langs")
def busqueda_idiomas():
    return jsonify(
        {
            "supported": ["es", "en"],
            "labels": {
                "es": "Español",
                "en": "English",
            },
        }
    )
