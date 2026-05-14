import os
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

NS_DEPORTE = Namespace("http://www.semanticweb.org/ontologies/deportes#")

grafo = Graph()
grafo.bind("deporte", NS_DEPORTE)

DIRECTORIO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTORIO_ONTOLOGIA = os.path.join(DIRECTORIO_BASE, "ontology")

FORMATOS_SOPORTADOS = {
    ".rdf": "xml",
    ".owl": "xml",
    ".ttl": "turtle",
    ".n3": "n3",
    ".nt": "nt",
    ".jsonld": "json-ld",
}

archivos_cargados = []

for nombre_archivo in os.listdir(DIRECTORIO_ONTOLOGIA):
    extension = os.path.splitext(nombre_archivo)[1].lower()
    if extension in FORMATOS_SOPORTADOS:
        ruta_archivo = os.path.join(DIRECTORIO_ONTOLOGIA, nombre_archivo)
        formato_rdf = FORMATOS_SOPORTADOS[extension]
        try:
            grafo.parse(ruta_archivo, format=formato_rdf)
            archivos_cargados.append(nombre_archivo)
            print(f"[OK] Cargado: {nombre_archivo} ({formato_rdf})")
        except Exception as error_carga:
            print(f"[ERROR] No se pudo cargar {nombre_archivo}: {error_carga}")

print(f"Total tripletas locales: {len(grafo)} | Archivos: {archivos_cargados}")


try:
    from SPARQLWrapper import SPARQLWrapper, JSON

    SPARQL_DISPONIBLE = True
except ImportError:
    SPARQL_DISPONIBLE = False
    print("[WARN] SPARQLWrapper no instalado. DBpedia deshabilitado.")

URL_DBPEDIA_ONLINE = "https://dbpedia.org/sparql"
URL_DBPEDIA_OFFLINE = "http://localhost:8890/sparql"


def _construir_sparql(endpoint: str, limite_tiempo: int = 8) -> "SPARQLWrapper":
    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(limite_tiempo)
    return sparql


def consultar_dbpedia(consulta_sparql: str, idioma: str = "es") -> list[dict]:
    if not SPARQL_DISPONIBLE:
        return []

    endpoints = [URL_DBPEDIA_OFFLINE, URL_DBPEDIA_ONLINE]

    for endpoint in endpoints:
        try:
            sparql = _construir_sparql(endpoint)
            sparql.setQuery(consulta_sparql)
            resultados = sparql.query().convert()
            bindings = resultados.get("results", {}).get("bindings", [])
            filas = []
            for enlace in bindings:
                fila = {k: v.get("value", "") for k, v in enlace.items()}
                filas.append(fila)
            print(f"[DBpedia] {endpoint} → {len(filas)} resultados")
            return filas
        except Exception as error_consulta:
            print(f"[DBpedia] Fallo {endpoint}: {error_consulta}")

    return []


def buscar_deporte_dbpedia(palabra_clave: str, idioma: str = "es") -> list[dict]:
    consulta = f"""
    PREFIX dbo:  <http://dbpedia.org/ontology/>
    PREFIX dbr:  <http://dbpedia.org/resource/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dct:  <http://purl.org/dc/terms/>

    SELECT DISTINCT ?deporte ?label ?abstract WHERE {{
        ?deporte a dbo:Sport .
        ?deporte rdfs:label ?label .
        OPTIONAL {{ ?deporte dbo:abstract ?abstract .
                   FILTER(LANG(?abstract) = "{idioma}") }}
        FILTER(LANG(?label) = "{idioma}")
        FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{palabra_clave}")))
    }}
    LIMIT 10
    """
    return consultar_dbpedia(consulta, idioma)
