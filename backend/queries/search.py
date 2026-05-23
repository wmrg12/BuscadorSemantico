from rdflib.namespace import RDF, RDFS, OWL
from rdflib import Literal
from services.ontology_service import grafo as graph, buscar_deporte_dbpedia as search_dbpedia_sport

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


def _crear_regex_acentos(palabra: str) -> str:
    p = palabra.lower()
    p = p.replace("a", "[aáäAÁÄ]").replace("e", "[eéëEÉË]").replace("i", "[iíïIÍÏ]")
    p = p.replace("o", "[oóöOÓÖ]").replace("u", "[uúüUÚÜ]")
    return p


def busqueda_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    import re
    from rdflib import URIRef, Literal
    from rdflib.namespace import RDF, RDFS, OWL

    # Separar la frase en palabras individuales
    palabras = [
        p.strip().replace('"', '\\"') for p in palabra_clave.split() if p.strip()
    ]
    if not palabras:
        return []

    # Precompilar patrones de regex para cada palabra
    patrones = []
    for pal in palabras:
        regex_str = _crear_regex_acentos(pal)
        patrones.append(re.compile(regex_str, re.IGNORECASE))

    meta_classes = {
        OWL.Class,
        RDFS.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"),
    }

    datos = []
    vistos = set()

    # Iterar sobre todos los sujetos en el grafo
    for s in set(graph.subjects()):
        if not isinstance(s, URIRef):
            continue

        # Excluir meta clases
        es_meta = False
        for t in graph.objects(s, RDF.type):
            if t in meta_classes:
                es_meta = True
                break
        if es_meta:
            continue

        # Recopilar todos los textos asociados a este sujeto para la búsqueda
        textos_sujeto = [str(s)]

        # Tipos
        for t in graph.objects(s, RDF.type):
            textos_sujeto.append(str(t))

        # Etiquetas y otras propiedades
        for p, o in graph.predicate_objects(s):
            if isinstance(o, Literal) or isinstance(o, URIRef):
                textos_sujeto.append(str(o))

        texto_completo = " ".join(textos_sujeto)

        # Verificar si TODOS los patrones coinciden con el texto del sujeto
        if all(pat.search(texto_completo) for pat in patrones):
            uri_str = str(s)

            # Obtener etiqueta principal
            label = None
            for l in graph.objects(s, RDFS.label):
                if isinstance(l, Literal) and (l.language == idioma or not l.language):
                    label = str(l)
                    break

            # Obtener tipo principal
            tipo = None
            for t in graph.objects(s, RDF.type):
                if t != OWL.NamedIndividual and t not in meta_classes:
                    tipo = str(t)
                    break

            etiqueta = label if label else _uri_a_etiqueta(uri_str)
            tipo_final = _uri_a_etiqueta(tipo) if tipo else "Recurso"

            if uri_str not in vistos:
                vistos.add(uri_str)
                datos.append(
                    {
                        "uri": uri_str,
                        "label": etiqueta,
                        "tipo": tipo_final,
                        "lang": idioma,
                        "fuente": "local",
                    }
                )

                if len(datos) >= 30:
                    break

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

    # Obtener el tipo/clase principal
    tipos = []
    for t in graph.objects(uri_ref, RDF.type):
        if t != OWL.NamedIndividual:
            t_str = str(t)
            t_label = _obtener_etiqueta(t, idioma) or _uri_a_etiqueta(t_str)
            tipos.append({"uri": t_str, "label": t_label})

    # 2. Consultar propiedades salientes (?p ?o)
    propiedades = []
    for p, o in graph.predicate_objects(uri_ref):
        # Ignorar tipo NamedIndividual
        if p == RDF.type and o == OWL.NamedIndividual:
            continue

        p_str = str(p)
        if (
            any(x in p_str for x in ["#type", "ontology#", "rdf-schema#"])
            and p != RDF.type
        ):
            continue

        p_etiqueta = _obtener_etiqueta(p, idioma) or _uri_a_etiqueta(p_str)

        if isinstance(o, Literal):
            propiedades.append(
                {
                    "propiedad_uri": p_str,
                    "propiedad": p_etiqueta,
                    "valor": str(o),
                    "es_iri": False,
                }
            )
        elif isinstance(o, URIRef):
            o_str = str(o)
            o_etiqueta = _obtener_etiqueta(o, idioma) or _uri_a_etiqueta(o_str)
            propiedades.append(
                {
                    "propiedad_uri": p_str,
                    "propiedad": p_etiqueta,
                    "valor": o_str,
                    "valor_label": o_etiqueta,
                    "es_iri": True,
                }
            )

    # Ordenar propiedades alfanumericos
    propiedades.sort(key=lambda x: x["propiedad"])

    # Consultar relaciones entrantes
    relaciones_entrantes = []
    for s, p in graph.subject_predicates(uri_ref):
        s_str = str(s)
        s_etiqueta = _obtener_etiqueta(s, idioma) or _uri_a_etiqueta(s_str)
        p_str = str(p)
        p_etiqueta = _obtener_etiqueta(p, idioma) or _uri_a_etiqueta(p_str)
        relaciones_entrantes.append(
            {
                "sujeto": s_str,
                "sujeto_label": s_etiqueta,
                "propiedad": p_etiqueta,
                "propiedad_uri": p_str,
            }
        )

    relaciones_entrantes.sort(key=lambda x: (x["propiedad"], x["sujeto_label"]))

    # Retornar los detalles agrupados
    return {
        "uri": uri,
        "label": _obtener_etiqueta(uri_ref, idioma) or _uri_a_etiqueta(uri),
        "tipos": tipos,
        "propiedades": propiedades,
        "relaciones_entrantes": relaciones_entrantes,
    }
