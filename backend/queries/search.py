from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL

from services.ontology_service import grafo as graph_local
from services.ontology_service import grafo_dbpedia as graph_dbpedia
from services.ontology_service import buscar_deporte_dbpedia


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
    resultados_compuestos = busqueda_compuesta_relacional(
        graph_local,
        palabra_clave,
        idioma=idioma,
        fuente="local",
    )

    if resultados_compuestos:
        return resultados_compuestos
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


def _es_recurso_dbpedia(uri: str) -> bool:
    uri = uri.lower()
    return "dbpedia.org/resource" in uri


def busqueda_combinada(
    palabra_clave: str, idioma: str = "es", usar_dbpedia: bool = True
) -> dict:
    resultados_locales_brutos = busqueda_local(palabra_clave, idioma)

    if usar_dbpedia:
        resultados_dbpedia_brutos = busqueda_dbpedia_local(palabra_clave, idioma)
    else:
        resultados_dbpedia_brutos = []

    local_final = []
    dbpedia_final = []
    vistos = set()

    # Primero procesamos los resultados encontrados en la ontología local
    for item in resultados_locales_brutos:
        uri = item.get("uri", "")

        if uri in vistos:
            continue

        vistos.add(uri)

        # Si la URI pertenece a DBpedia, no debe mostrarse como Local
        if _es_recurso_dbpedia(uri):
            if usar_dbpedia:
                item["fuente"] = "dbpedia"
                if item.get("tipo") == "Recurso":
                    item["tipo"] = "Recurso DBpedia"
                dbpedia_final.append(item)
        else:
            item["fuente"] = "local"
            local_final.append(item)

    # Luego procesamos los resultados propios de DBpedia
    if usar_dbpedia:
        for item in resultados_dbpedia_brutos:
            uri = item.get("uri", "")

            if uri in vistos:
                continue

            vistos.add(uri)
            item["fuente"] = "dbpedia"

            if item.get("tipo") == "Recurso":
                item["tipo"] = "Recurso DBpedia"

            dbpedia_final.append(item)

    return {
        "keyword": palabra_clave,
        "lang": idioma,
        "local": local_final,
        "dbpedia": dbpedia_final,
        "total": len(local_final) + len(dbpedia_final),
    }

STOPWORDS_BUSQUEDA = {
    "de", "del", "la", "el", "los", "las", "en", "por", "para",
    "un", "una", "unos", "unas", "y", "a", "con"
}

TIPOS_CONSULTA = {
    "atleta": {"Atleta"},
    "atletas": {"Atleta"},

    "arbitro": {"Arbitro"},
    "arbitros": {"Arbitro"},
    "árbitro": {"Arbitro"},
    "árbitros": {"Arbitro"},

    "equipo": {"Equipo"},
    "equipos": {"Equipo"},

    "participante": {"Participante"},
    "participantes": {"Participante"},

    "evento": {"eventoDeportivo"},
    "eventos": {"eventoDeportivo"},

    "deporte": {"Deporte"},
    "deportes": {"Deporte"},

    "lugar": {"Lugar"},
    "lugares": {"Lugar"},

    "modalidad": {"Modalidad"},
    "modalidades": {"Modalidad"},
}


def _obtener_nombre_principal(grafo: Graph, recurso, idioma: str = "es") -> str:
    etiqueta = _obtener_etiqueta_en_grafo(grafo, recurso, idioma)
    if etiqueta:
        return etiqueta

    propiedades_nombre = {
        "nombreparticipante",
        "nombreevento",
        "nombredeporte",
        "nombrelugar",
        "tipomodalidad",
    }

    for p, o in grafo.predicate_objects(recurso):
        if isinstance(o, Literal):
            nombre_propiedad = _normalizar_texto(_uri_a_etiqueta(str(p)))
            if nombre_propiedad in propiedades_nombre:
                return str(o)

    return _uri_a_etiqueta(str(recurso))


def _cumple_tipo(grafo: Graph, recurso, tipos_buscados: set[str]) -> bool:
    tipos_normalizados = {
        _normalizar_texto(t) for t in tipos_buscados
    }

    for tipo in grafo.objects(recurso, RDF.type):
        nombre_tipo = _normalizar_texto(_uri_a_etiqueta(str(tipo)))

        if nombre_tipo in tipos_normalizados:
            return True

        # También revisa superclases:
        # Ejemplo: Atleta -> Participante
        for superclase in grafo.transitive_objects(tipo, RDFS.subClassOf):
            nombre_superclase = _normalizar_texto(_uri_a_etiqueta(str(superclase)))
            if nombre_superclase in tipos_normalizados:
                return True

    return False


def _texto_recurso(grafo: Graph, recurso, idioma: str = "es") -> str:
    textos = [
        str(recurso),
        _uri_a_etiqueta(str(recurso)),
        _obtener_nombre_principal(grafo, recurso, idioma),
    ]

    for tipo in grafo.objects(recurso, RDF.type):
        textos.append(str(tipo))
        textos.append(_uri_a_etiqueta(str(tipo)))

        for superclase in grafo.transitive_objects(tipo, RDFS.subClassOf):
            textos.append(str(superclase))
            textos.append(_uri_a_etiqueta(str(superclase)))

    for p, o in grafo.predicate_objects(recurso):
        textos.append(_uri_a_etiqueta(str(p)))

        if isinstance(o, Literal):
            textos.append(str(o))
        elif isinstance(o, URIRef):
            textos.append(str(o))
            textos.append(_uri_a_etiqueta(str(o)))
            textos.append(_obtener_nombre_principal(grafo, o, idioma))

    return _normalizar_texto(" ".join(textos))


def _contexto_relacional(grafo: Graph, recurso, idioma: str = "es") -> str:
    textos = []

    # Texto propio del recurso
    textos.append(_texto_recurso(grafo, recurso, idioma))

    # Relaciones salientes:
    # recurso -> otro recurso
    for p, o in grafo.predicate_objects(recurso):
        textos.append(_uri_a_etiqueta(str(p)))

        if isinstance(o, URIRef):
            textos.append(_texto_recurso(grafo, o, idioma))
        elif isinstance(o, Literal):
            textos.append(str(o))

    # Relaciones entrantes:
    # otro recurso -> recurso
    for sujeto, predicado in grafo.subject_predicates(recurso):
        textos.append(_uri_a_etiqueta(str(predicado)))
        textos.append(_texto_recurso(grafo, sujeto, idioma))

        # Si el sujeto es un evento, también incluimos todo lo relacionado al evento:
        # deporte, lugar, modalidad y participantes.
        for p_evento, o_evento in grafo.predicate_objects(sujeto):
            textos.append(_uri_a_etiqueta(str(p_evento)))

            if isinstance(o_evento, URIRef):
                textos.append(_texto_recurso(grafo, o_evento, idioma))
            elif isinstance(o_evento, Literal):
                textos.append(str(o_evento))

    return _normalizar_texto(" ".join(textos))


def _interpretar_consulta_compuesta(palabra_clave: str) -> tuple[set[str], list[str]]:
    tokens_originales = _tokenizar_consulta(palabra_clave)

    tipos_buscados = set()
    terminos = []

    for token in tokens_originales:
        token_norm = _normalizar_texto(token)

        if token_norm in STOPWORDS_BUSQUEDA:
            continue

        if token_norm in TIPOS_CONSULTA:
            tipos_buscados.update(TIPOS_CONSULTA[token_norm])
        else:
            terminos.append(token_norm)

    return tipos_buscados, terminos


def busqueda_compuesta_relacional(
    grafo: Graph,
    palabra_clave: str,
    idioma: str = "es",
    fuente: str = "local",
    limite: int = 30,
) -> list[dict]:
    tipos_buscados, terminos = _interpretar_consulta_compuesta(palabra_clave)

    # Si no hay tipo y solo hay una palabra, no es compuesta.
    # Ejemplo: "futbol" debe seguir usando búsqueda normal.
    if not tipos_buscados and len(terminos) <= 1:
        return []

    resultados = []

    for recurso in set(grafo.subjects()):
        if not isinstance(recurso, URIRef):
            continue

        if _es_meta_clase(grafo, recurso):
            continue

        # Si la consulta pide un tipo, filtramos por tipo.
        # Ejemplo: "atleta futbol" solo devuelve Atletas.
        if tipos_buscados and not _cumple_tipo(grafo, recurso, tipos_buscados):
            continue

        contexto = _contexto_relacional(grafo, recurso, idioma)

        # Todos los términos restantes deben aparecer en el contexto relacional.
        # Ejemplo: "participante ciclismo tour bolivia"
        # participante = tipo
        # ciclismo, tour, bolivia = contexto del evento/deporte/lugar
        if all(termino in contexto for termino in terminos):
            label = _obtener_nombre_principal(grafo, recurso, idioma)

            tipo = None
            for t in grafo.objects(recurso, RDF.type):
                if t != OWL.NamedIndividual and not _es_meta_clase(grafo, t):
                    tipo = str(t)
                    break

            tipo_final = _uri_a_etiqueta(tipo) if tipo else "Recurso"

            resultados.append(
                {
                    "uri": str(recurso),
                    "label": label,
                    "tipo": tipo_final,
                    "lang": idioma,
                    "fuente": fuente,
                    "score": 95,
                }
            )

    resultados.sort(key=lambda x: (-x["score"], x["label"].lower()))
    return resultados[:limite]

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