from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS

from services.ontology_service import grafo as graph_local
from services.ontology_service import grafo_dbpedia as graph_dbpedia
from services.ontology_service import buscar_deporte_dbpedia, _crear_regex_acentos


IDIOMAS_SOPORTADOS = ["es", "en"]
PROPIEDADES_ETIQUETA = (SKOS.prefLabel, RDFS.label, SKOS.altLabel)


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
    for propiedad in PROPIEDADES_ETIQUETA:
        for etiqueta in grafo.objects(uri_ref, propiedad):
            if isinstance(etiqueta, Literal) and etiqueta.language == idioma:
                return str(etiqueta)

    for propiedad in (SKOS.prefLabel, RDFS.label):
        for etiqueta in grafo.objects(uri_ref, propiedad):
            if isinstance(etiqueta, Literal) and not etiqueta.language:
                return str(etiqueta)

    return None


def _literales_idioma(grafo: Graph, uri_ref, idioma: str) -> list[str]:
    textos: list[str] = []
    for propiedad in PROPIEDADES_ETIQUETA:
        for etiqueta in grafo.objects(uri_ref, propiedad):
            if isinstance(etiqueta, Literal) and (
                etiqueta.language == idioma or not etiqueta.language
            ):
                textos.append(str(etiqueta))
    return textos


def _tipo_etiqueta(grafo: Graph, tipo_uri: str | None, idioma: str = "es") -> str:
    if not tipo_uri:
        return "Recurso"
    return _obtener_etiqueta_en_grafo(grafo, URIRef(tipo_uri), idioma) or _uri_a_etiqueta(
        tipo_uri
    )


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


def _tipo_dominio(grafo: Graph, recurso) -> str | None:
    tipos_ignorar = {
        OWL.NamedIndividual,
        OWL.Class,
        RDFS.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
    }

    for tipo in grafo.objects(recurso, RDF.type):
        if tipo in tipos_ignorar:
            continue
        return str(tipo)
    return None


def _texto_busqueda_recurso(grafo: Graph, recurso, idioma: str = "es") -> str:
    textos = [str(recurso), _uri_a_etiqueta(str(recurso))]
    textos.extend(_literales_idioma(grafo, recurso, idioma))
    textos.append(_obtener_nombre_principal(grafo, recurso, idioma))

    for tipo in grafo.objects(recurso, RDF.type):
        if tipo in {OWL.NamedIndividual}:
            continue
        textos.append(str(tipo))
        textos.append(_uri_a_etiqueta(str(tipo)))
        textos.extend(_literales_idioma(grafo, tipo, idioma))

        for superclase in grafo.transitive_objects(tipo, RDFS.subClassOf):
            textos.append(str(superclase))
            textos.append(_uri_a_etiqueta(str(superclase)))
            textos.extend(_literales_idioma(grafo, superclase, idioma))

    for propiedad, valor in grafo.predicate_objects(recurso):
        textos.extend(_literales_idioma(grafo, propiedad, idioma))
        textos.append(_uri_a_etiqueta(str(propiedad)))

        if isinstance(valor, Literal):
            if not valor.language or valor.language == idioma:
                textos.append(str(valor))
        elif isinstance(valor, URIRef):
            textos.append(str(valor))
            textos.append(_uri_a_etiqueta(str(valor)))
            textos.extend(_literales_idioma(grafo, valor, idioma))
            textos.append(_obtener_nombre_principal(grafo, valor, idioma))

    return _normalizar_texto(" ".join(textos))


def _coincide_busqueda(texto_completo: str, tokens: list[str], consulta_norm: str) -> int:
    score = 0
    if consulta_norm and consulta_norm in texto_completo:
        score = 100
    if all(tok in texto_completo for tok in tokens):
        score = max(score, 80)
    return score


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

        texto_completo = _texto_busqueda_recurso(grafo, s, idioma)
        score = _coincide_busqueda(texto_completo, tokens, consulta_norm)
        if score == 0:
            continue

        uri_str = str(s)
        label = _obtener_nombre_principal(grafo, s, idioma)

        tipo = _tipo_dominio(grafo, s)

        resultados.append(
            {
                "uri": uri_str,
                "label": label,
                "tipo": _tipo_etiqueta(grafo, tipo, idioma),
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

            etiqueta = _obtener_etiqueta_en_grafo(grafo, s, idioma) or _uri_a_etiqueta(
                uri_str
            )
            datos.append(
                {"uri": uri_str, "label": etiqueta, "lang": idioma, "fuente": fuente}
            )

            if len(datos) >= 50:
                return datos

    return datos


DEPORTE_NS = "http://www.semanticweb.org/hp/ontologies/2026/2/WebSemantica/Deporte"
TERMINOS_DEPORTE_GENERICO = {"deporte", "deportes", "sport", "sports"}


def _es_consulta_deporte_generica(palabra_clave: str) -> bool:
    tokens = [_normalizar_texto(t) for t in _tokenizar_consulta(palabra_clave)]
    return len(tokens) == 1 and tokens[0] in TERMINOS_DEPORTE_GENERICO


def _buscar_tipos_deporte(
    grafo: Graph,
    idioma: str = "es",
    fuente: str = "local",
) -> list[dict]:
    """Lista las subclases directas de Deporte (Atletismo, Futbol, etc.)."""
    deporte = URIRef(DEPORTE_NS)
    tipo_padre = _obtener_etiqueta_en_grafo(grafo, deporte, idioma) or "Deporte"
    resultados = []

    for subclase in grafo.subjects(RDFS.subClassOf, deporte):
        if not isinstance(subclase, URIRef):
            continue

        label = _obtener_etiqueta_en_grafo(grafo, subclase, idioma) or _uri_a_etiqueta(
            str(subclase)
        )
        resultados.append(
            {
                "uri": str(subclase),
                "label": label,
                "tipo": tipo_padre,
                "lang": idioma,
                "fuente": fuente,
                "score": 100,
            }
        )

    resultados.sort(key=lambda x: x["label"].lower())
    return resultados


def obtener_info_ontologia(idioma: str = "es") -> dict:
    consulta = """
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?ontologia ?comentario WHERE {
        ?ontologia a owl:Ontology .
        ?ontologia rdfs:comment ?comentario .
    }
    """
    resultados = graph_local.query(consulta)
    comentarios = {}
    uri_ontologia = "http://www.semanticweb.org/hp/ontologies/2026/2/WebSemantica"
    
    for fila in resultados:
        uri_ontologia = str(fila[0])
        comentario_lit = fila[1]
        lang = comentario_lit.language or "es"
        comentarios[lang] = str(comentario_lit)
    
    if not comentarios:
        comentarios = {
            "es": "Esta es una ontologia sobre deportes",
            "en": "This is an ontology about sports"
        }
        
    return {
        "uri": uri_ontologia,
        "descripcion": comentarios.get(idioma, comentarios.get("es", "")),
        "comentarios": comentarios,
        "idiomas_soportados": ["es", "en"],
        "niveles_representacion": {
            "informacion": {
                "titulo": "Nivel 1: Información",
                "detalle": "La ontología declara explícitamente sus metadatos e idiomas soportados en la cabecera owl:Ontology con rdfs:comment en español e inglés."
            },
            "realizacion": {
                "titulo": "Nivel 2: Realización",
                "detalle": "Los datos (instancias, clases y propiedades) contienen etiquetas físicas con tags de idioma @es y @en en el archivo RDF/OWL."
            },
            "modelizacion": {
                "titulo": "Nivel 3: Modelización",
                "detalle": "El buscador realiza consultas SPARQL y filtra dinámicamente los recursos por idioma usando la función FILTER(LANG(?label) = 'idioma')."
            }
        }
    }


def obtener_query_sparql_busqueda(palabra_clave: str, idioma: str = "es") -> str:
    palabra_clave_norm = _normalizar_texto(palabra_clave)
    regex_pal = _crear_regex_acentos(palabra_clave_norm)
    
    return f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?recurso ?label ?tipo WHERE {{
    ?recurso rdf:type ?tipo_uri .
    FILTER(isIRI(?recurso))
    
    # Excluir meta-clases y propiedades del esquema
    FILTER(?tipo_uri != owl:Class && ?tipo_uri != rdfs:Class && ?tipo_uri != owl:ObjectProperty && ?tipo_uri != owl:DatatypeProperty)
    
    # Obtener etiquetas preferidas o normales en el idioma actual o sin idioma
    OPTIONAL {{
        ?recurso rdfs:label ?label_rdfs .
        FILTER(LANG(?label_rdfs) = "{idioma}")
    }}
    OPTIONAL {{
        ?recurso skos:prefLabel ?label_skos .
        FILTER(LANG(?label_skos) = "{idioma}")
    }}
    OPTIONAL {{
        ?recurso rdfs:label ?label_rdfs_any .
        FILTER(LANG(?label_rdfs_any) = "")
    }}
    
    # Enlazar la mejor etiqueta disponible
    BIND(COALESCE(?label_rdfs, ?label_skos, ?label_rdfs_any) AS ?label)
    
    # Obtener el tipo legible
    OPTIONAL {{
        ?tipo_uri rdfs:label ?tipo_label .
        FILTER(LANG(?tipo_label) = "{idioma}")
    }}
    BIND(COALESCE(?tipo_label) AS ?tipo)
    
    # Búsqueda relacional/literal con Regex (Modelización)
    FILTER(
        REGEX(STR(?recurso), "{regex_pal}", "i") ||
        (BOUND(?label) && REGEX(STR(?label), "{regex_pal}", "i")) ||
        EXISTS {{
            ?recurso ?p ?valor .
            FILTER(isLiteral(?valor) && REGEX(STR(?valor), "{regex_pal}", "i"))
        }}
    )
    
    # Modelización: Filtrado por idioma estricto en el buscador
    FILTER(!BOUND(?label) || LANG(?label) = "" || LANG(?label) = "{idioma}")
}}
LIMIT 30"""


def busqueda_local_sparql(palabra_clave: str, idioma: str = "es") -> list[dict]:
    consulta = obtener_query_sparql_busqueda(palabra_clave, idioma)
    try:
        resultados = graph_local.query(consulta)
        datos = []
        for fila in resultados:
            uri_str = str(fila[0])
            label = str(fila[1]) if fila[1] else _uri_a_etiqueta(uri_str)
            
            if fila[2]:
                tipo = str(fila[2])
            else:
                tipo_uri = _tipo_dominio(graph_local, fila[0])
                tipo = _tipo_etiqueta(graph_local, tipo_uri, idioma)
                
            datos.append({
                "uri": uri_str,
                "label": label,
                "tipo": tipo,
                "lang": idioma,
                "fuente": "local",
                "score": 100
            })
        return datos
    except Exception as e:
        print(f"[SPARQL Error] {e}")
        return []


def busqueda_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    if _es_consulta_deporte_generica(palabra_clave):
        return _buscar_tipos_deporte(graph_local, idioma=idioma, fuente="local")

    resultados_sparql = busqueda_local_sparql(palabra_clave, idioma)
    if resultados_sparql:
        return resultados_sparql

    resultados_compuestos = busqueda_compuesta_relacional(
        graph_local,
        palabra_clave,
        idioma=idioma,
        fuente="local",
    )

    if resultados_compuestos:
        return resultados_compuestos

    resultados = _buscar_en_grafo(
        graph_local, palabra_clave, idioma=idioma, fuente="local"
    )
    resultados.sort(key=lambda x: (-x["score"], x["label"].lower()))
    return resultados[:30]


def busqueda_dbpedia_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    resultados = []
    uris_vistas = set()

    # Cuando no es español, priorizar la búsqueda live de DBpedia
    # (los archivos offline solo contienen datos en español)
    if idioma != "es":
        resultados_online = buscar_deporte_dbpedia(palabra_clave, idioma=idioma)
        for res_online in resultados_online:
            resultados.append(res_online)
            uris_vistas.add(res_online["uri"])

        # Buscar también en los archivos offline para complementar
        resultados_offline = _buscar_en_grafo(
            graph_dbpedia, palabra_clave, idioma=idioma, fuente="dbpedia"
        )
        for res in resultados_offline:
            if res["uri"] not in uris_vistas:
                resultados.append(res)
                uris_vistas.add(res["uri"])
    else:
        # Para español: primero buscar offline, luego complementar con live
        resultados_offline = _buscar_en_grafo(
            graph_dbpedia, palabra_clave, idioma=idioma, fuente="dbpedia"
        )
        resultados.extend(resultados_offline)
        uris_vistas = {res["uri"] for res in resultados_offline}

        if len(resultados) < 10:
            resultados_online = buscar_deporte_dbpedia(palabra_clave, idioma=idioma)
            for res_online in resultados_online:
                if res_online["uri"] not in uris_vistas:
                    resultados.append(res_online)
                    uris_vistas.add(res_online["uri"])

    return resultados


def obtener_clases(idioma: str = "es") -> list[dict]:
    datos = []
    vistos = set()

    for grafo, fuente in [(graph_local, "local"), (graph_dbpedia, "dbpedia")]:
        consulta = """
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?clase WHERE {
            { ?clase a owl:Class . }
            UNION
            { ?clase a rdfs:Class . }
            FILTER(isIRI(?clase))
        }
        """

        resultados = grafo.query(consulta)
        for fila in resultados:
            uri_str = str(fila[0])
            if uri_str in vistos:
                continue
            vistos.add(uri_str)

            etiqueta = _obtener_etiqueta_en_grafo(grafo, URIRef(uri_str), idioma)
            if not etiqueta:
                continue

            datos.append(
                {"uri": uri_str, "label": etiqueta, "lang": idioma, "fuente": fuente}
            )

    datos.sort(key=lambda x: x["label"].lower())
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

            etiqueta = _obtener_etiqueta_en_grafo(grafo, URIRef(uri_str), idioma) or _uri_a_etiqueta(
                uri_str
            )
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

    # Obtener la consulta SPARQL generada para mostrarla en la Consola del buscador
    sparql_query_str = obtener_query_sparql_busqueda(palabra_clave, idioma)

    return {
        "keyword": palabra_clave,
        "lang": idioma,
        "local": local_final,
        "dbpedia": dbpedia_final,
        "total": len(local_final) + len(dbpedia_final),
        "sparql_query": sparql_query_str,
    }


STOPWORDS_BUSQUEDA = {
    # Español
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "en",
    "por",
    "para",
    "un",
    "una",
    "unos",
    "unas",
    "y",
    "a",
    "con",
    # English
    "the",
    "of",
    "in",
    "and",
    "for",
    "to",
    "a",
    "an",
    "on",
    "at",
    "by",
    "with",
    "from",
    "is",
    "are",
    "was",
    "were",
}

TIPOS_CONSULTA = {
    # Español
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
    "futbol": {"Futbol"},
    "fútbol": {"Futbol"},
    "football": {"Futbol"},
    "soccer": {"Futbol"},
    # English
    "athlete": {"Atleta"},
    "athletes": {"Atleta"},
    "referee": {"Arbitro"},
    "referees": {"Arbitro"},
    "team": {"Equipo"},
    "teams": {"Equipo"},
    "player": {"Atleta"},
    "players": {"Atleta"},
    "participant": {"Participante"},
    "participants": {"Participante"},
    "event": {"eventoDeportivo"},
    "events": {"eventoDeportivo"},
    "sport": {"Deporte"},
    "sports": {"Deporte"},
    "place": {"Lugar"},
    "places": {"Lugar"},
    "venue": {"Lugar"},
    "venues": {"Lugar"},
    "modality": {"Modalidad"},
    "modalities": {"Modalidad"},
}


def _obtener_nombre_principal(grafo: Graph, recurso, idioma: str = "es") -> str:
    etiqueta = _obtener_etiqueta_en_grafo(grafo, recurso, idioma)
    if etiqueta:
        return etiqueta

    props: dict[str, str] = {}
    for p, o in grafo.predicate_objects(recurso):
        if isinstance(o, Literal):
            key = _normalizar_texto(_uri_a_etiqueta(str(p)))
            props[key] = str(o)

    if props.get("nombreevento"):
        return props["nombreevento"]
    if props.get("nombreparticipante"):
        return props["nombreparticipante"]
    if props.get("nombrelugar"):
        return props["nombrelugar"]
    if props.get("tipomodalidad"):
        return props["tipomodalidad"]
    if props.get("descripciondeporte"):
        return props["descripciondeporte"]

    uri_label = _uri_a_etiqueta(str(recurso))
    nombre_deporte = props.get("nombredeporte")

    if nombre_deporte:
        if _normalizar_texto(uri_label) != _normalizar_texto(nombre_deporte):
            return uri_label
        return nombre_deporte

    return uri_label


def _cumple_tipo(grafo: Graph, recurso, tipos_buscados: set[str]) -> bool:
    tipos_normalizados = {_normalizar_texto(t) for t in tipos_buscados}

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


_CACHE_TEXTO_RECURSO = {}
_CACHE_CONTEXTO_RELACIONAL = {}


def _texto_recurso(grafo: Graph, recurso, idioma: str = "es") -> str:
    cache_key = (id(grafo), str(recurso), idioma)
    if cache_key in _CACHE_TEXTO_RECURSO:
        return _CACHE_TEXTO_RECURSO[cache_key]

    resultado = _texto_busqueda_recurso(grafo, recurso, idioma)
    _CACHE_TEXTO_RECURSO[cache_key] = resultado
    return resultado


def _contexto_relacional(grafo: Graph, recurso, idioma: str = "es") -> str:
    cache_key = (id(grafo), str(recurso), idioma)
    if cache_key in _CACHE_CONTEXTO_RELACIONAL:
        return _CACHE_CONTEXTO_RELACIONAL[cache_key]

    textos = []

    # Texto propio del recurso
    textos.append(_texto_recurso(grafo, recurso, idioma))

    # recurso -> otro recurso
    for p, o in grafo.predicate_objects(recurso):
        textos.append(_uri_a_etiqueta(str(p)))

        if isinstance(o, URIRef):
            textos.append(_texto_recurso(grafo, o, idioma))
        elif isinstance(o, Literal):
            textos.append(str(o))
    # otro recurso -> recurso
    for sujeto, predicado in grafo.subject_predicates(recurso):
        textos.append(_uri_a_etiqueta(str(predicado)))
        textos.append(_texto_recurso(grafo, sujeto, idioma))

        for p_evento, o_evento in grafo.predicate_objects(sujeto):
            textos.append(_uri_a_etiqueta(str(p_evento)))

            if isinstance(o_evento, URIRef):
                textos.append(_texto_recurso(grafo, o_evento, idioma))
            elif isinstance(o_evento, Literal):
                textos.append(str(o_evento))

    resultado = _normalizar_texto(" ".join(textos))
    _CACHE_CONTEXTO_RELACIONAL[cache_key] = resultado
    return resultado


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

    # Solo palabra suelta o tipo sin contexto adicional -> búsqueda normal.
    if not tipos_buscados and len(terminos) <= 1:
        return []
    if tipos_buscados and not terminos:
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

            tipo = _tipo_dominio(grafo, recurso)

            tipo_final = _tipo_etiqueta(grafo, tipo, idioma)

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
            t_label = _obtener_etiqueta_en_grafo(grafo, t, idioma) or _uri_a_etiqueta(
                t_str
            )
            tipos.append({"uri": t_str, "label": t_label})

    propiedades = []
    for p, o in grafo.predicate_objects(uri_ref):
        if p == RDF.type and o == OWL.NamedIndividual:
            continue

        p_str = str(p)
        if (
            any(x in p_str for x in ["#type", "ontology#", "rdf-schema#"])
            and p != RDF.type
        ):
            continue

        p_etiqueta = _obtener_etiqueta_en_grafo(grafo, p, idioma) or _uri_a_etiqueta(
            p_str
        )

        if isinstance(o, Literal):
            propiedades.append(
                {
                    "propiedad_uri": p_str,
                    "propiedad": p_etiqueta,
                    "valor": str(o),
                    "es_iri": False,
                    "lang": o.language if o.language else None
                }
            )
        elif isinstance(o, URIRef):
            o_str = str(o)
            o_etiqueta = _obtener_etiqueta_en_grafo(
                grafo, o, idioma
            ) or _uri_a_etiqueta(o_str)
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
        s_etiqueta = _obtener_etiqueta_en_grafo(grafo, s, idioma) or _uri_a_etiqueta(
            s_str
        )
        p_str = str(p)
        p_etiqueta = _obtener_etiqueta_en_grafo(grafo, p, idioma) or _uri_a_etiqueta(
            p_str
        )
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
        "label": _obtener_etiqueta_en_grafo(grafo, uri_ref, idioma)
        or _uri_a_etiqueta(uri),
        "tipos": tipos,
        "propiedades": propiedades,
        "relaciones_entrantes": relaciones_entrantes,
    }
