import os
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

DEPORTE_NS = Namespace("http://www.semanticweb.org/ontologies/deportes#")

# Grafo principal
graph = Graph()
graph.bind("deporte", DEPORTE_NS)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONTOLOGY_DIR = os.path.join(BASE_DIR, "ontology")

# Cargar archivos ontologicops
SUPPORTED_FORMATS = {
    ".rdf": "xml",
    ".owl": "xml",
    ".ttl": "turtle",
}

loaded_files = []

for filename in os.listdir(ONTOLOGY_DIR):
    ext = os.path.splitext(filename)[1].lower()
    if ext in SUPPORTED_FORMATS:
        filepath = os.path.join(ONTOLOGY_DIR, filename)
        fmt = SUPPORTED_FORMATS[ext]
        try:
            graph.parse(filepath, format=fmt)
            loaded_files.append(filename)
            print(f"[OK] Cargado: {filename} ({fmt})")
        except Exception as e:
            print(f"[ERROR] No se pudo cargar {filename}: {e}")

print(f"Total tripletas locales: {len(graph)} | Archivos: {loaded_files}")


# DBpedia
try:
    from SPARQLWrapper import SPARQLWrapper, JSON

    SPARQL_AVAILABLE = True
except ImportError:
    SPARQL_AVAILABLE = False
    print("[WARN] SPARQLWrapper no instalado. DBpedia deshabilitado.")

DBPEDIA_ONLINE_URL = "https://dbpedia.org/sparql"

def _build_dbpedia_wrapper(endpoint: str, timeout: int = 8) -> "SPARQLWrapper":
    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(timeout)
    return sparql


def query_dbpedia(sparql_query: str, lang: str = "es") -> list[dict]:
    if not SPARQL_AVAILABLE:
        return []

    try:
        sparql = _build_dbpedia_wrapper(DBPEDIA_ONLINE_URL)
        sparql.setQuery(sparql_query)
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])
        rows = []
        for b in bindings:
            row = {k: v.get("value", "") for k, v in b.items()}
            rows.append(row)
        print(f"[DBpedia] {DBPEDIA_ONLINE_URL} → {len(rows)} resultados")
        return rows
    except Exception as e:
        print(f"[DBpedia] Fallo {DBPEDIA_ONLINE_URL}: {e}")
        return []


def _crear_regex_acentos(palabra: str) -> str:
    p = palabra.lower()
    p = p.replace("a", "[aáäAÁÄ]").replace("e", "[eéëEÉË]").replace("i", "[iíïIÍÏ]")
    p = p.replace("o", "[oóöOÓÖ]").replace("u", "[uúüUÚÜ]")
    return p


def search_dbpedia_sport(keyword: str, lang: str = "es") -> list[dict]:
    # Separar en palabras para búsqueda compuesta
    palabras = [p.strip() for p in keyword.split() if p.strip()]
    if not palabras:
        return []

    filtros_regex = []
    for pal in palabras:
        regex_pal = _crear_regex_acentos(pal)
        filtros_regex.append(f'FILTER(REGEX(STR(?label), "{regex_pal}", "i"))')
        
    filtros_str = "\n        ".join(filtros_regex)

    query = f"""
    PREFIX dbo:  <http://dbpedia.org/ontology/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?deporte ?label WHERE {{
        ?deporte a dbo:Sport .
        ?deporte rdfs:label ?label .
        FILTER(LANG(?label) = "{lang}")
        {filtros_str}
    }}
    LIMIT 10
    """
    return query_dbpedia(query, lang)
