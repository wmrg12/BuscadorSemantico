from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL

from services.ontology_service import grafo as graph_local
from services.ontology_service import grafo_dbpedia as graph_dbpedia


IDIOMAS_SOPORTADOS = ["es", "en"]


def _uri_a_etiqueta(uri: str) -> str:
    nombre = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
    return nombre.replace("_", " ").strip()


def _normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for a, b in reemplazos.items():
        texto = texto.replace(a, b)
    return texto


def _tokenizar_consulta(palabra_clave: str) -> list[str]:
    palabra_clave = palabra_clave.strip()
    if not palabra_clave:
        return []
    return [p for p in palabra_clave.split() if p.strip()]


def _obtener_etiqueta_en_grafo(grafo: Graph, uri_ref, idioma: str = "es") -> str | None:
    for etiqueta in grafo.objects(uri_ref, RDFS.label):
        if isinstance(etiqueta, Literal):
            if etiqueta.language == idioma:
                return str(etiqueta)

    for etiqueta in grafo.objects(uri_ref, RDFS.label):
        if isinstance(etiqueta, Literal) and not etiqueta.language:
            return str(etiqueta)

    return None


def _grafo_para_uri(uri: str) -> Graph:
    uri_ref = URIRef(uri)

    if (uri_ref, None, None) in graph_local:
        return graph_local

    if (uri_ref, None, None) in graph_dbpedia:
        return graph_dbpedia

    return graph_local


def _es_meta_clase(grafo: Graph, s) -> bool:
    meta_classes = {
        OWL.Class,
        RDFS.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"),
    }

    for t in grafo.objects(s, RDF.type):
        if t in meta_classes:
            return True
    return False


def _buscar_en_grafo(
    grafo: Graph,
    palabra_clave: str,
    idioma: str = "es",
    fuente: str = "local",
    limite: int = 30,
) -> list[dict]:
    palabras = _tokenizar_consulta(palabra_clave)
    if not palabras:
        return []

    tokens = [_normalizar_texto(p) for p in palabras]
    consulta_norm = _normalizar_texto(palabra_clave)

    resultados = []

    for s in set(grafo.subjects()):
        if not isinstance(s, URIRef):
            continue

        if _es_meta_clase(grafo, s):
            continue

        textos = [str(s), _uri_a_etiqueta(str(s))]

        for t in grafo.objects(s, RDF.type):
            textos.append(str(t))
            textos.append(_uri_a_etiqueta(str(t)))

        for p, o in grafo.predicate_objects(s):
            if isinstance(o, Literal):
                textos.append(str(o))
            elif isinstance(o, URIRef):
                textos.append(str(o))
                textos.append(_uri_a_etiqueta(str(o)))

        texto_completo = _normalizar_texto(" ".join(textos))

        # 1) coincidencia exacta de frase
        score = 0
        if consulta_norm and consulta_norm in texto_completo:
            score = 100

        # 2) coincidencia de todos los términos
        if all(tok in texto_completo for tok in tokens):
            score = max(score, 80)
        else:
            continue

        uri_str = str(s)

        label = None
        for l in grafo.objects(s, RDFS.label):
            if isinstance(l, Literal) and (l.language == idioma or not l.language):
                label = str(l)
                break

        if not label:
            label = _uri_a_etiqueta(uri_str)

        tipo = None
        for t in grafo.objects(s, RDF.type):
            if t != OWL.NamedIndividual and not _es_meta_clase(grafo, t):
                tipo = str(t)
                break

        tipo_final = _uri_a_etiqueta(tipo) if tipo else "Recurso"

        resultados.append(
            {
                "uri": uri_str,
                "label": label,
                "tipo": tipo_final,
                "lang": idioma,
                "fuente": fuente,
                "score": score,
            }
        )

    resultados.sort(key=lambda x: (-x["score"], x["label"].lower()))
    return resultados[:limite]


def obtener_todos_los_sujetos(idioma: str = "es") -> list[dict]:
    datos = []
    vistos = set()

    for grafo, fuente in [(graph_local, "local"), (graph_dbpedia, "dbpedia")]:
        for s in set(grafo.subjects()):
            if not isinstance(s, URIRef):
                continue
            uri_str = str(s)
            if uri_str in vistos:
                continue
            vistos.add(uri_str)

            etiqueta = _obtener_etiqueta_en_grafo(grafo, s, idioma) or _uri_a_etiqueta(uri_str)
            datos.append({"uri": uri_str, "label": etiqueta, "lang": idioma, "fuente": fuente})

            if len(datos) >= 50:
                return datos

    return datos


def busqueda_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    return _buscar_en_grafo(graph_local, palabra_clave, idioma=idioma, fuente="local")


def busqueda_dbpedia_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    return _buscar_en_grafo(graph_dbpedia, palabra_clave, idioma=idioma, fuente="dbpedia")


def obtener_clases(idioma: str = "es") -> list[dict]:
    datos = []
    vistos = set()

    for grafo, fuente in [(graph_local, "local"), (graph_dbpedia, "dbpedia")]:
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

        resultados = grafo.query(consulta)
        for fila in resultados:
            uri_str = str(fila[0])
            if uri_str in vistos:
                continue
            vistos.add(uri_str)

            etiqueta = str(fila[1]) if fila[1] else _uri_a_etiqueta(uri_str)
            datos.append(
                {"uri": uri_str, "label": etiqueta, "lang": idioma, "fuente": fuente}
            )

    return datos


def obtener_individuos(uri_clase: str = None, idioma: str = "es") -> list[dict]:
    datos = []
    vistos = set()

    for grafo, fuente in [(graph_local, "local"), (graph_dbpedia, "dbpedia")]:
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

        resultados = grafo.query(consulta)
        for fila in resultados:
            uri_str = str(fila[0])
            if uri_str in vistos:
                continue
            vistos.add(uri_str)

            etiqueta = str(fila[1]) if fila[1] else _uri_a_etiqueta(uri_str)
            datos.append(
                {
                    "uri": uri_str,
                    "label": etiqueta,
                    "lang": idioma,
                    "fuente": fuente,
                }
            )

    return datos[:50]


def busqueda_combinada(
    palabra_clave: str, idioma: str = "es", usar_dbpedia: bool = True
) -> dict:
    local = busqueda_local(palabra_clave, idioma)
    dbpedia = busqueda_dbpedia_local(palabra_clave, idioma) if usar_dbpedia else []

    # Evitar duplicados por URI
    vistos = set()
    local_unico = []
    dbpedia_unico = []

    for item in local:
        if item["uri"] not in vistos:
            vistos.add(item["uri"])
            local_unico.append(item)

    for item in dbpedia:
        if item["uri"] not in vistos:
            vistos.add(item["uri"])
            dbpedia_unico.append(item)

    return {
        "keyword": palabra_clave,
        "lang": idioma,
        "local": local_unico,
        "dbpedia": dbpedia_unico,
        "total": len(local_unico) + len(dbpedia_unico),
    }


def obtener_detalles_recurso(uri: str, idioma: str = "es") -> dict:
    grafo = _grafo_para_uri(uri)
    uri_ref = URIRef(uri)

    tipos = []
    for t in grafo.objects(uri_ref, RDF.type):
        if t != OWL.NamedIndividual:
            t_str = str(t)
            t_label = _obtener_etiqueta_en_grafo(grafo, t, idioma) or _uri_a_etiqueta(t_str)
            tipos.append({"uri": t_str, "label": t_label})

    propiedades = []
    for p, o in grafo.predicate_objects(uri_ref):
        if p == RDF.type and o == OWL.NamedIndividual:
            continue

        p_str = str(p)
        if any(x in p_str for x in ["#type", "ontology#", "rdf-schema#"]) and p != RDF.type:
            continue

        p_etiqueta = _obtener_etiqueta_en_grafo(grafo, p, idioma) or _uri_a_etiqueta(p_str)

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
            o_etiqueta = _obtener_etiqueta_en_grafo(grafo, o, idioma) or _uri_a_etiqueta(o_str)
            propiedades.append(
                {
                    "propiedad_uri": p_str,
                    "propiedad": p_etiqueta,
                    "valor": o_str,
                    "valor_label": o_etiqueta,
                    "es_iri": True,
                }
            )

    propiedades.sort(key=lambda x: x["propiedad"])

    relaciones_entrantes = []
    for s, p in grafo.subject_predicates(uri_ref):
        s_str = str(s)
        s_etiqueta = _obtener_etiqueta_en_grafo(grafo, s, idioma) or _uri_a_etiqueta(s_str)
        p_str = str(p)
        p_etiqueta = _obtener_etiqueta_en_grafo(grafo, p, idioma) or _uri_a_etiqueta(p_str)
        relaciones_entrantes.append(
            {
                "sujeto": s_str,
                "sujeto_label": s_etiqueta,
                "propiedad": p_etiqueta,
                "propiedad_uri": p_str,
            }
        )

    relaciones_entrantes.sort(key=lambda x: (x["propiedad"], x["sujeto_label"]))

    return {
        "uri": uri,
        "label": _obtener_etiqueta_en_grafo(grafo, uri_ref, idioma) or _uri_a_etiqueta(uri),
        "tipos": tipos,
        "propiedades": propiedades,
        "relaciones_entrantes": relaciones_entrantes,
    }