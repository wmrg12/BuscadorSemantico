from rdflib.namespace import RDF, RDFS, OWL
from rdflib import Literal
from services.ontology_service import graph, search_dbpedia_sport

IDIOMAS_SOPORTADOS = ["es", "en"]


def _uri_a_etiqueta(uri: str) -> str:
    nombre = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
    return nombre.replace("_", " ").strip()


def _obtener_etiqueta(uri_ref, idioma: str = "es") -> str | None:
    for etiqueta in graph.objects(uri_ref, RDFS.label):
        if isinstance(etiqueta, Literal):
            if etiqueta.language == idioma:
                return str(etiqueta)
    for etiqueta in graph.objects(uri_ref, RDFS.label):
        if isinstance(etiqueta, Literal) and not etiqueta.language:
            return str(etiqueta)
    return None


def obtener_todos_los_sujetos(idioma: str = "es") -> list[dict]:
    consulta = """
    SELECT DISTINCT ?s
    WHERE {
        ?s ?p ?o .
        FILTER(isIRI(?s))
    }
    LIMIT 50
    """
    resultados = graph.query(consulta)
    datos = []
    for fila in resultados:
        uri_ref = fila[0]
        uri_str = str(uri_ref)
        etiqueta = _obtener_etiqueta(uri_ref, idioma) or _uri_a_etiqueta(uri_str)
        datos.append({"uri": uri_str, "label": etiqueta, "lang": idioma})
    return datos


def busqueda_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    consulta = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?entidad ?label ?tipo WHERE {{
        ?entidad ?p ?o .
        FILTER(isIRI(?entidad))
        OPTIONAL {{ ?entidad rdfs:label ?label . }}
        OPTIONAL {{ ?entidad a ?tipo . }}
        FILTER(
            CONTAINS(LCASE(STR(?entidad)), LCASE("{palabra_clave}"))
            || (BOUND(?label) && CONTAINS(LCASE(STR(?label)), LCASE("{palabra_clave}")))
        )
        FILTER(!BOUND(?label) || LANG(?label) = "" || LANG(?label) = "{idioma}")
    }}
    LIMIT 30
    """
    resultados = graph.query(consulta)
    datos = []
    vistos = set()
    for fila in resultados:
        uri_str = str(fila[0])
        etiqueta = str(fila[1]) if fila[1] else _uri_a_etiqueta(uri_str)
        tipo_raw = str(fila[2]) if fila[2] else "Recurso"
        tipo = _uri_a_etiqueta(tipo_raw)
        if uri_str not in vistos:
            vistos.add(uri_str)
            datos.append(
                {
                    "uri": uri_str,
                    "label": etiqueta,
                    "tipo": tipo,
                    "lang": idioma,
                    "fuente": "local",
                }
            )
    return datos


def obtener_clases(idioma: str = "es") -> list[dict]:
    consulta = """
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?clase ?label WHERE {
        { ?clase a owl:Class . }
        UNION
        { ?clase a rdfs:Class . }
        FILTER(isIRI(?clase))
        OPTIONAL { ?clase rdfs:label ?label . }
    }
    """
    resultados = graph.query(consulta)
    datos = []
    for fila in resultados:
        uri_str = str(fila[0])
        etiqueta = str(fila[1]) if fila[1] else _uri_a_etiqueta(uri_str)
        datos.append({"uri": uri_str, "label": etiqueta, "lang": idioma})
    return datos


def obtener_individuos(uri_clase: str = None, idioma: str = "es") -> list[dict]:
    if uri_clase:
        consulta = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?ind ?label WHERE {{
            ?ind a <{uri_clase}> .
            FILTER(isIRI(?ind))
            OPTIONAL {{ ?ind rdfs:label ?label . }}
        }}
        LIMIT 50
        """
    else:
        consulta = """
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?ind ?label WHERE {
            ?ind a owl:NamedIndividual .
            OPTIONAL { ?ind rdfs:label ?label . }
        }
        LIMIT 50
        """
    resultados = graph.query(consulta)
    datos = []
    for fila in resultados:
        uri_str = str(fila[0])
        etiqueta = str(fila[1]) if fila[1] else _uri_a_etiqueta(uri_str)
        datos.append(
            {"uri": uri_str, "label": etiqueta, "lang": idioma, "fuente": "local"}
        )
    return datos


def busqueda_combinada(
    palabra_clave: str, idioma: str = "es", usar_dbpedia: bool = True
) -> dict:
    local = busqueda_local(palabra_clave, idioma)
    dbpedia = search_dbpedia_sport(palabra_clave, idioma) if usar_dbpedia else []

    dbpedia_norm = []
    for item in dbpedia:
        dbpedia_norm.append(
            {
                "uri": item.get("deporte", ""),
                "label": item.get("label", ""),
                "abstract": item.get("abstract", ""),
                "tipo": "Deporte (DBpedia)",
                "lang": idioma,
                "fuente": "dbpedia",
            }
        )

    return {
        "keyword": palabra_clave,
        "lang": idioma,
        "local": local,
        "dbpedia": dbpedia_norm,
        "total": len(local) + len(dbpedia_norm),
    }
