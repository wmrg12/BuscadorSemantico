import os
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

DEPORTE_NS = Namespace("http://www.semanticweb.org/ontologies/deportes#")

# Grafo local (ontología propia) y grafo DBpedia offline (archivos bdpedia_*)
grafo = Graph()
grafo_dbpedia = Graph()
grafo.bind("deporte", DEPORTE_NS)

DIRECTORIO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTORIO_ONTOLOGIA = os.path.join(DIRECTORIO_BASE, "ontology")

FORMATOS_SOPORTADOS = {
    ".rdf": "xml",
    ".owl": "xml",
    ".ttl": "turtle",
}

archivos_local = []
archivos_dbpedia = []


def _es_archivo_dbpedia(nombre_archivo: str) -> bool:
    return nombre_archivo.lower().startswith("bdpedia_")


for nombre_archivo in os.listdir(DIRECTORIO_ONTOLOGIA):
    extension = os.path.splitext(nombre_archivo)[1].lower()
    if extension not in FORMATOS_SOPORTADOS:
        continue

    ruta_archivo = os.path.join(DIRECTORIO_ONTOLOGIA, nombre_archivo)
    formato = FORMATOS_SOPORTADOS[extension]
    destino = grafo_dbpedia if _es_archivo_dbpedia(nombre_archivo) else grafo

    try:
        destino.parse(ruta_archivo, format=formato)
        if _es_archivo_dbpedia(nombre_archivo):
            archivos_dbpedia.append(nombre_archivo)
        else:
            archivos_local.append(nombre_archivo)
        print(f"[OK] Cargado: {nombre_archivo} ({formato})")
    except Exception as e:
        print(f"[ERROR] No se pudo cargar {nombre_archivo}: {e}")

print(
    f"Ontologia local: {len(grafo)} tripletas ({archivos_local}) | "
    f"DBpedia offline: {len(grafo_dbpedia)} tripletas ({archivos_dbpedia})"
)


# DBpedia
import logging

try:
    from SPARQLWrapper import SPARQLWrapper, JSON

    SPARQL_DISPONIBLE = True
except ImportError:
    SPARQL_DISPONIBLE = False
    print("[WARN] SPARQLWrapper no instalado. DBpedia deshabilitado.")

URL_DBPEDIA_EN_LINEA = "https://dbpedia.org/sparql"

# Configurar logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
logger.addHandler(handler)


def _construir_envoltorio_dbpedia(
    punto_acceso: str, tiempo_espera: int = 20
) -> "SPARQLWrapper":
    sparql = SPARQLWrapper(punto_acceso)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(tiempo_espera)
    return sparql


def consultar_dbpedia(consulta_sparql: str, idioma: str = "es") -> list[dict]:
    if not SPARQL_DISPONIBLE:
        logger.warning("SPARQLWrapper no disponible. No se puede consultar DBpedia.")
        return []

    puntos_acceso = [URL_DBPEDIA_EN_LINEA]

    for punto in puntos_acceso:
        try:
            logger.info(f"Consultando DBpedia en {punto}...")
            logger.debug(f"Consulta SPARQL: {consulta_sparql[:200]}...")
            
            sparql = _construir_envoltorio_dbpedia(punto)
            sparql.setQuery(consulta_sparql)
            resultados_json = sparql.query().convert()

            filas = []
            if "results" in resultados_json and "bindings" in resultados_json["results"]:
                for binding in resultados_json["results"]["bindings"]:
                    uri = binding.get("deporte", {}).get("value", "")
                    label = binding.get("label", {}).get("value", "")
                    abstract = binding.get("abstract", {}).get("value", "")
                    label_lang = binding.get("labelLang", {}).get("value", idioma)
                    abstract_lang = binding.get("abstractLang", {}).get("value", idioma)
                    
                    if uri and label:
                        filas.append(
                            {
                                "uri": uri,
                                "label": label,
                                "abstract": abstract,
                                "tipo": "Deporte (DBpedia Online)",
                                "lang": label_lang,
                                "fuente": "dbpedia_online",
                                "score": 100,
                            }
                        )
            
            logger.info(f"DBpedia {punto} -> {len(filas)} resultados encontrados")
            return filas
        except Exception as e:
            logger.error(f"Error consultando DBpedia {punto}: {type(e).__name__}: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    return []


def _crear_regex_acentos(palabra: str) -> str:
    p = palabra.lower()
    p = p.replace("a", "[aáäAÁÄ]").replace("e", "[eéëEÉË]").replace("i", "[iíïIÍÏ]")
    p = p.replace("o", "[oóöOÓÖ]").replace("u", "[uúüUÚÜ]")
    return p


def buscar_deporte_dbpedia(palabra_clave: str, idioma: str = "es") -> list[dict]:
    # Búsqueda online con SELECT para mejor compatibilidad
    palabras = [p.strip() for p in palabra_clave.split() if p.strip()]
    if not palabras:
        return []

    filtros_regex = []
    for pal in palabras:
        regex_pal = _crear_regex_acentos(pal)
        filtros_regex.append(f'FILTER(REGEX(STR(?label), "{regex_pal}", "i"))')

    filtros_str = "\n        ".join(filtros_regex)

    # Intentar primero con el idioma solicitado, luego con alternativas
    idiomas_a_intentar = [idioma]
    if idioma != "en":
        idiomas_a_intentar.append("en")
    if idioma != "es":
        idiomas_a_intentar.append("es")
    
    for idioma_intento in idiomas_a_intentar:
        consulta = f"""
    PREFIX dbo:  <http://dbpedia.org/ontology/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?deporte ?label ?labelLang ?abstract ?abstractLang
    WHERE {{
        ?deporte a dbo:Sport .
        ?deporte rdfs:label ?label .
        FILTER(LANG(?label) = "{idioma_intento}")
        BIND(LANG(?label) AS ?labelLang)
        {filtros_str}

        OPTIONAL {{
            ?deporte dbo:abstract ?abstract .
            BIND(LANG(?abstract) AS ?abstractLang)
            FILTER(LANG(?abstract) = "{idioma_intento}")
        }}
    }}
    LIMIT 15
    """
        resultados = consultar_dbpedia(consulta, idioma_intento)
        if resultados:
            return resultados
    
    return []
