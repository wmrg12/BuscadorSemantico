import os
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

DEPORTE_NS = Namespace("http://www.semanticweb.org/ontologies/deportes#")

# Grafo principal
grafo = Graph()
grafo.bind("deporte", DEPORTE_NS)

DIRECTORIO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTORIO_ONTOLOGIA = os.path.join(DIRECTORIO_BASE, "ontology")

# Cargar archivos ontologicos
FORMATOS_SOPORTADOS = {
    ".rdf": "xml",
    ".owl": "xml",
    ".ttl": "turtle",
}

archivos_cargados = []

for nombre_archivo in os.listdir(DIRECTORIO_ONTOLOGIA):
    extension = os.path.splitext(nombre_archivo)[1].lower()
    if extension in FORMATOS_SOPORTADOS:
        ruta_archivo = os.path.join(DIRECTORIO_ONTOLOGIA, nombre_archivo)
        formato = FORMATOS_SOPORTADOS[extension]
        try:
            grafo.parse(ruta_archivo, format=formato)
            archivos_cargados.append(nombre_archivo)
            print(f"[OK] Cargado: {nombre_archivo} ({formato})")
        except Exception as e:
            print(f"[ERROR] No se pudo cargar {nombre_archivo}: {e}")

print(f"Total tripletas locales: {len(grafo)} | Archivos: {archivos_cargados}")


# DBpedia
try:
    from SPARQLWrapper import SPARQLWrapper, JSON

    SPARQL_DISPONIBLE = True
except ImportError:
    SPARQL_DISPONIBLE = False
    print("[WARN] SPARQLWrapper no instalado. DBpedia deshabilitado.")

URL_DBPEDIA_EN_LINEA = "https://dbpedia.org/sparql"


def _construir_envoltorio_dbpedia(
    punto_acceso: str, tiempo_espera: int = 8
) -> "SPARQLWrapper":
    sparql = SPARQLWrapper(punto_acceso)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(tiempo_espera)
    return sparql


def consultar_dbpedia(consulta_sparql: str, idioma: str = "es") -> list[dict]:
    if not SPARQL_DISPONIBLE:
        return []

    puntos_acceso = [URL_DBPEDIA_EN_LINEA]

    for punto in puntos_acceso:
        try:
            sparql = _construir_envoltorio_dbpedia(punto)
            sparql.setQuery(consulta_sparql)
            resultados = sparql.query().convert()
            vinculaciones = resultados.get("results", {}).get("bindings", [])
            filas = []
            for b in vinculaciones:
                fila = {k: v.get("value", "") for k, v in b.items()}
                filas.append(fila)
            print(f"[DBpedia] {punto} → {len(filas)} resultados")
            return filas
        except Exception as e:
            print(f"[DBpedia] Fallo {punto}: {e}")

    return []


def _crear_regex_acentos(palabra: str) -> str:
    p = palabra.lower()
    p = p.replace("a", "[aáäAÁÄ]").replace("e", "[eéëEÉË]").replace("i", "[iíïIÍÏ]")
    p = p.replace("o", "[oóöOÓÖ]").replace("u", "[uúüUÚÜ]")
    return p


def buscar_deporte_dbpedia(palabra_clave: str, idioma: str = "es") -> list[dict]:
    # Separar en palabras para búsqueda compuesta
    palabras = [p.strip() for p in palabra_clave.split() if p.strip()]
    if not palabras:
        return []

    filtros_regex = []
    for pal in palabras:
        regex_pal = _crear_regex_acentos(pal)
        filtros_regex.append(f'FILTER(REGEX(STR(?label), "{regex_pal}", "i"))')

    filtros_str = "\n        ".join(filtros_regex)

    consulta = f"""
    PREFIX dbo:  <http://dbpedia.org/ontology/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?deporte ?label WHERE {{
        ?deporte a dbo:Sport .
        ?deporte rdfs:label ?label .
        FILTER(LANG(?label) = "{idioma}")
        {filtros_str}
    }}
    LIMIT 10
    """
    return consultar_dbpedia(consulta, idioma)
