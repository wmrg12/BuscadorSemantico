from flask import Blueprint, jsonify, request
from queries.search import (
    obtener_todos_los_sujetos,
    busqueda_combinada,
    obtener_clases,
    obtener_individuos,
)

busqueda_bp = Blueprint("busqueda", __name__)


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
        return jsonify({"error": "Parametro 'q' requerido"}), 400

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
