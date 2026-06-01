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
    sparql.setReturnFormat("xml")  # RDF
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
            grafo_res = sparql.query().convert()

            DBO_SPORT = URIRef("http://dbpedia.org/ontology/Sport")
            DBO_ABSTRACT = URIRef("http://dbpedia.org/ontology/abstract")

            filas = []
            for s in grafo_res.subjects(RDF.type, DBO_SPORT):
                deporte = str(s)
                label = ""
                for l in grafo_res.objects(s, RDFS.label):
                    label = str(l)
                    break

                abstract = ""
                for a in grafo_res.objects(s, DBO_ABSTRACT):
                    abstract = str(a)
                    break

                filas.append(
                    {
                        "uri": deporte,
                        "label": label,
                        "abstract": abstract,
                        "tipo": "Deporte (DBpedia Online)",
                        "lang": idioma,
                        "fuente": "dbpedia_online",
                        "score": 100,
                    }
                )
            print(f"[DBpedia] {punto} -> {len(filas)} resultados (desde RDF)")
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
    # Búsqueda online
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

    CONSTRUCT {{
        ?deporte a dbo:Sport .
        ?deporte rdfs:label ?label .
        ?deporte dbo:abstract ?abstract .
    }} WHERE {{
        ?deporte a dbo:Sport .
        ?deporte rdfs:label ?label .
        FILTER(LANG(?label) = "{idioma}")
        {filtros_str}

        OPTIONAL {{
            ?deporte dbo:abstract ?abstract .
            FILTER(LANG(?abstract) = "{idioma}")
        }}
    }}
    LIMIT 10
    """
    return consultar_dbpedia(consulta, idioma)
