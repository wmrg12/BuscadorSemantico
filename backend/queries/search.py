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
    # Separar la frase en palabras individuales (ignorando espacios vacíos)
    palabras = [
        p.strip().lower().replace('"', '\\"')
        for p in palabra_clave.split()
        if p.strip()
    ]
    if not palabras:
        return []

    # Construir dinámicamente un FILTER por cada palabra
    filtros_palabras = []
    for i, pal in enumerate(palabras):
        filtros_palabras.append(f"""
        FILTER(
            CONTAINS(LCASE(STR(?entidad)), "{pal}")
            || (BOUND(?label) && CONTAINS(LCASE(STR(?label)), "{pal}"))
            || (BOUND(?tipoClase) && CONTAINS(LCASE(STR(?tipoClase)), "{pal}"))
            || EXISTS {{
                ?entidad ?prop_{i} ?valor_{i} .
                FILTER(isLiteral(?valor_{i}) && CONTAINS(LCASE(STR(?valor_{i})), "{pal}"))
            }}
        )
        """)

    filtros_sparql_str = "\n".join(filtros_palabras)

    consulta = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?entidad ?label ?tipo WHERE {{
        ?entidad ?p ?o .
        FILTER(isIRI(?entidad))
        
        # Excluir las clases y propiedades del esquema de los resultados de búsqueda
        FILTER NOT EXISTS {{
            ?entidad a ?tipoClaseObj .
            FILTER(
                ?tipoClaseObj = owl:Class 
                || ?tipoClaseObj = rdfs:Class 
                || ?tipoClaseObj = owl:ObjectProperty 
                || ?tipoClaseObj = owl:DatatypeProperty 
                || ?tipoClaseObj = owl:AnnotationProperty
                || ?tipoClaseObj = <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property>
            )
        }}
        
        OPTIONAL {{ ?entidad rdfs:label ?label . }}
        OPTIONAL {{ ?entidad a ?tipo . }}
        OPTIONAL {{
            ?entidad a/rdfs:subClassOf* ?tipoClase .
            FILTER(isIRI(?tipoClase))
        }}
        {filtros_sparql_str}
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


def obtener_detalles_recurso(uri: str, idioma: str = "es") -> dict:
    from rdflib import URIRef
    uri_ref = URIRef(uri)

    # 1. Obtener el tipo/clase principal (evitando NamedIndividual)
    tipos = []
    for t in graph.objects(uri_ref, RDF.type):
        if t != OWL.NamedIndividual:
            t_str = str(t)
            t_label = _obtener_etiqueta(t, idioma) or _uri_a_etiqueta(t_str)
            tipos.append({"uri": t_str, "label": t_label})

    # 2. Consultar propiedades salientes (?p ?o)
    propiedades = []
    for p, o in graph.predicate_objects(uri_ref):
        # Ignorar tipo NamedIndividual ya que es redundante para el usuario
        if p == RDF.type and o == OWL.NamedIndividual:
            continue

        p_str = str(p)
        # Omitir propiedades de metadatos del framework
        if any(x in p_str for x in ["#type", "ontology#", "rdf-schema#"]) and p != RDF.type:
            continue

        p_etiqueta = _obtener_etiqueta(p, idioma) or _uri_a_etiqueta(p_str)

        if isinstance(o, Literal):
            propiedades.append({
                "propiedad_uri": p_str,
                "propiedad": p_etiqueta,
                "valor": str(o),
                "es_iri": False
            })
        elif isinstance(o, URIRef):
            o_str = str(o)
            o_etiqueta = _obtener_etiqueta(o, idioma) or _uri_a_etiqueta(o_str)
            propiedades.append({
                "propiedad_uri": p_str,
                "propiedad": p_etiqueta,
                "valor": o_str,
                "valor_label": o_etiqueta,
                "es_iri": True
            })

    # Ordenar propiedades alfabéticamente por nombre de propiedad
    propiedades.sort(key=lambda x: x["propiedad"])

    # 3. Consultar relaciones entrantes (?sujeto ?predicado <uri>)
    relaciones_entrantes = []
    for s, p in graph.subject_predicates(uri_ref):
        s_str = str(s)
        s_etiqueta = _obtener_etiqueta(s, idioma) or _uri_a_etiqueta(s_str)
        p_str = str(p)
        p_etiqueta = _obtener_etiqueta(p, idioma) or _uri_a_etiqueta(p_str)
        relaciones_entrantes.append({
            "sujeto": s_str,
            "sujeto_label": s_etiqueta,
            "propiedad": p_etiqueta,
            "propiedad_uri": p_str
        })

    relaciones_entrantes.sort(key=lambda x: (x["propiedad"], x["sujeto_label"]))

    # 4. Retornar los detalles agrupados
    return {
        "uri": uri,
        "label": _obtener_etiqueta(uri_ref, idioma) or _uri_a_etiqueta(uri),
        "tipos": tipos,
        "propiedades": propiedades,
        "relaciones_entrantes": relaciones_entrantes
    }
