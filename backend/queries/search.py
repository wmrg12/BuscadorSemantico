from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS

from services.ontology_service import grafo as graph_local
from services.ontology_service import grafo_dbpedia as graph_dbpedia
from services.ontology_service import buscar_deporte_dbpedia


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


def _traducir_etiqueta(etiqueta: str, idioma: str) -> str:
    """Traduce etiquetas de español a inglés si es necesario."""
    if idioma == "en":
        return TRADUCCIONES_VALORES.get(etiqueta, etiqueta)
    return etiqueta


def _traducir_propiedad(propiedad: str, idioma: str) -> str:
    """Traduce nombres de propiedades RDF de español a inglés si es necesario."""
    if idioma == "en":
        return TRADUCCIONES_PROPIEDADES.get(propiedad, propiedad)
    return propiedad


def _traducir_valor(valor: str, idioma: str) -> str:
    """Traduce valores/categorías de español a inglés si es necesario."""
    if idioma == "en":
        return TRADUCCIONES_VALORES.get(valor, valor)
    return valor


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


def _texto_busqueda_recurso(grafo: Graph, recurso, idioma: str = "es", multiidioma: bool = False) -> str:
    textos = [str(recurso), _uri_a_etiqueta(str(recurso))]
    
    # Si multiidioma=True, incluir literales en TODOS los idiomas
    if multiidioma:
        for propiedad in PROPIEDADES_ETIQUETA:
            for etiqueta in grafo.objects(recurso, propiedad):
                if isinstance(etiqueta, Literal):
                    textos.append(str(etiqueta))
    else:
        textos.extend(_literales_idioma(grafo, recurso, idioma))
    
    textos.append(_obtener_nombre_principal(grafo, recurso, idioma))

    for tipo in grafo.objects(recurso, RDF.type):
        if tipo in {OWL.NamedIndividual}:
            continue
        textos.append(str(tipo))
        textos.append(_uri_a_etiqueta(str(tipo)))
        if multiidioma:
            for propiedad in PROPIEDADES_ETIQUETA:
                for etiqueta in grafo.objects(tipo, propiedad):
                    if isinstance(etiqueta, Literal):
                        textos.append(str(etiqueta))
        else:
            textos.extend(_literales_idioma(grafo, tipo, idioma))

        for superclase in grafo.transitive_objects(tipo, RDFS.subClassOf):
            textos.append(str(superclase))
            textos.append(_uri_a_etiqueta(str(superclase)))
            if multiidioma:
                for propiedad in PROPIEDADES_ETIQUETA:
                    for etiqueta in grafo.objects(superclase, propiedad):
                        if isinstance(etiqueta, Literal):
                            textos.append(str(etiqueta))
            else:
                textos.extend(_literales_idioma(grafo, superclase, idioma))

    for propiedad, valor in grafo.predicate_objects(recurso):
        if multiidioma:
            for prop_etiqueta in PROPIEDADES_ETIQUETA:
                for etiqueta in grafo.objects(propiedad, prop_etiqueta):
                    if isinstance(etiqueta, Literal):
                        textos.append(str(etiqueta))
        else:
            textos.extend(_literales_idioma(grafo, propiedad, idioma))
        textos.append(_uri_a_etiqueta(str(propiedad)))

        if isinstance(valor, Literal):
            textos.append(str(valor))
        elif isinstance(valor, URIRef):
            textos.append(str(valor))
            textos.append(_uri_a_etiqueta(str(valor)))
            if multiidioma:
                for propiedad in PROPIEDADES_ETIQUETA:
                    for etiqueta in grafo.objects(valor, propiedad):
                        if isinstance(etiqueta, Literal):
                            textos.append(str(etiqueta))
            else:
                textos.extend(_literales_idioma(grafo, valor, idioma))
            textos.append(_obtener_nombre_principal(grafo, valor, idioma))

    return _normalizar_texto(" ".join(textos))


def _coincide_busqueda(texto_completo: str, tokens: list[str], consulta_norm: str) -> int:
    score = 0
    
    # Búsqueda exacta (máxima puntuación)
    if consulta_norm and consulta_norm in texto_completo:
        score = 100
    
    # Todos los tokens presentes
    if all(tok in texto_completo for tok in tokens):
        score = max(score, 80)
    
    # Búsqueda aproximada: al menos el 70% de similitud en tokens
    # Tolerancia para errores de ortografía
    if score == 0 and tokens:
        tokens_en_texto = sum(1 for tok in tokens if tok in texto_completo)
        if len(tokens) > 0:
            similitud = tokens_en_texto / len(tokens)
            if similitud >= 0.5:  # Al menos 50% de los tokens coinciden
                score = int(similitud * 70)  # Score entre 35 y 70
    
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

        # Primero intentar buscar en el idioma solicitado
        texto_completo = _texto_busqueda_recurso(grafo, s, idioma, multiidioma=False)
        score = _coincide_busqueda(texto_completo, tokens, consulta_norm)
        
        # Si no encuentra en el idioma solicitado, buscar en todos los idiomas
        if score == 0:
            texto_completo = _texto_busqueda_recurso(grafo, s, idioma, multiidioma=True)
            score = _coincide_busqueda(texto_completo, tokens, consulta_norm)
        
        if score == 0:
            continue

        uri_str = str(s)
        label = _obtener_nombre_principal(grafo, s, idioma)
        label_traducido = _traducir_etiqueta(label, idioma)

        tipo = _tipo_dominio(grafo, s)
        tipo_etiqueta = _tipo_etiqueta(grafo, tipo, idioma)
        tipo_etiqueta_traducido = _traducir_etiqueta(tipo_etiqueta, idioma)

        resultados.append(
            {
                "uri": uri_str,
                "label": label_traducido,
                "tipo": tipo_etiqueta_traducido,
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
    tipo_padre_traducido = _traducir_etiqueta(tipo_padre, idioma)
    resultados = []

    for subclase in grafo.subjects(RDFS.subClassOf, deporte):
        if not isinstance(subclase, URIRef):
            continue

        label = _obtener_etiqueta_en_grafo(grafo, subclase, idioma) or _uri_a_etiqueta(
            str(subclase)
        )
        label_traducido = _traducir_etiqueta(label, idioma)
        
        resultados.append(
            {
                "uri": str(subclase),
                "label": label_traducido,
                "tipo": tipo_padre_traducido,
                "lang": idioma,
                "fuente": fuente,
                "score": 100,
            }
        )

    resultados.sort(key=lambda x: x["label"].lower())
    return resultados


def busqueda_local(palabra_clave: str, idioma: str = "es") -> list[dict]:
    if _es_consulta_deporte_generica(palabra_clave):
        return _buscar_tipos_deporte(graph_local, idioma=idioma, fuente="local")

    # Primero intenta búsqueda relacional contextual
    resultados_compuestos = busqueda_compuesta_relacional(
        graph_local,
        palabra_clave,
        idioma=idioma,
        fuente="local",
    )

    # También busca coincidencias directas en el grafo
    resultados_directos = _buscar_en_grafo(
        graph_local, palabra_clave, idioma=idioma, fuente="local"
    )

    # Combina resultados: primero los contextuales, luego los directos
    uris_vistas = set()
    resultados_finales = []
    
    # Agregar resultados contextuales primero
    for res in resultados_compuestos:
        uri = res.get("uri")
        if uri not in uris_vistas:
            resultados_finales.append(res)
            uris_vistas.add(uri)
    
    # Luego agregar resultados directos que no sean duplicados
    for res in resultados_directos:
        uri = res.get("uri")
        if uri not in uris_vistas:
            resultados_finales.append(res)
            uris_vistas.add(uri)

    # Ordenar por score y etiqueta
    resultados_finales.sort(key=lambda x: (-x["score"], x["label"].lower()))
    return resultados_finales[:30]


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

    return {
        "keyword": palabra_clave,
        "lang": idioma,
        "local": local_final,
        "dbpedia": dbpedia_final,
        "total": len(local_final) + len(dbpedia_final),
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
    "atletismo": {"Atletismo"},
    "voleibol": {"Voleibol"},
    "natación": {"Natacion"},
    "tenis": {"Tenis"},
    "piscina": {"Piscina"},
    "alberca": {"Piscina"},
    "estadio": {"Estadio"},
    "cancha": {"Cancha"},
    "pista": {"Pista"},
    "instalacion": {"Instalacion"},
    "instalaciones": {"Instalacion"},
    "liga": {"Liga"},
    "torneo": {"Torneo"},
    "campeonato": {"Campeonato"},
    "competencia": {"Competencia"},
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
    "football": {"Futbol"},
    "soccer": {"Futbol"},
    "athletics": {"Atletismo"},
    "track": {"Atletismo"},
    "field": {"Atletismo"},
    "volleyball": {"Voleibol"},
    "swimming": {"Natacion"},
    "swim": {"Natacion"},
    "pool": {"Piscina"},
    "swimming pool": {"Piscina"},
    "tennis": {"Tenis"},
    "stadium": {"Estadio"},
    "court": {"Cancha"},
    "facility": {"Instalacion"},
    "facilities": {"Instalacion"},
    "league": {"Liga"},
    "tournament": {"Torneo"},
    "championship": {"Campeonato"},
    "competition": {"Competencia"},
}

# Diccionario de traducciones de propiedades RDF: español -> inglés
TRADUCCIONES_PROPIEDADES = {
    # Español -> Inglés
    # Detalles de deportes
    "nombreDeporte": "Sport Name",
    "descripcionDeporte": "Sport Description",
    "tipoDeporte": "Sport Type",
    "deporte": "Sport",
    # Detalles de atletas
    "nombreAtleta": "Athlete Name",
    "apellidoAtleta": "Athlete Last Name",
    "nombre": "Name",
    "apellido": "Last Name",
    "nacionalidad": "Nationality",
    "edad": "Age",
    "altura": "Height",
    "peso": "Weight",
    "fechaNacimiento": "Date of Birth",
    "lugarNacimiento": "Place of Birth",
    # Detalles de eventos
    "nombreEvento": "Event Name",
    "descripcionEvento": "Event Description",
    "fechaEvento": "Event Date",
    "lugarEvento": "Event Location",
    "tipoEvento": "Event Type",
    "evento": "Event",
    # Detalles de equipos
    "nombreEquipo": "Team Name",
    "descripcionEquipo": "Team Description",
    "temporadaEquipo": "Team Season",
    "equipo": "Team",
    # Detalles de lugares/instalaciones
    "nombreLugar": "Place Name",
    "descripcionLugar": "Place Description",
    "capacidad": "Capacity",
    "ciudad": "City",
    "pais": "Country",
    "locacion": "Location",
    "ubicacion": "Location",
    "direccion": "Address",
    # Propiedades de la ontología local
    "correspondeA": "Corresponds To",
    "seRealizaEn": "Takes Place At",
    "tieneModalidad": "Has Modality",
    "tieneParticipante": "Has Participant",
    "numeroParticipantes": "Number of Participants",
    "reglamentoBase": "Base Rules",
    "rol": "Role",
    "horaEvento": "Event Time",
    # Relaciones y participación
    "participantes": "Participants",
    "atletas": "Athletes",
    "equipos": "Teams",
    "árbitros": "Referees",
    "eventos": "Events",
    "miembros": "Members",
    "compite_en": "Competes In",
    "arbitrado_por": "Judged By",
    # Resultados y puntuaciones
    "resultado": "Result",
    "puntuacion": "Score",
    "goles": "Goals",
    "puntos": "Points",
    "tiempo": "Time",
    # Clasificación y ranking
    "clasificacion": "Classification",
    "ranking": "Ranking",
    "posicion": "Position",
    "puesto": "Rank",
    "victorias": "Wins",
    "derrotas": "Losses",
    "empates": "Draws",
    # Competición
    "competencia": "Competition",
    "competicion": "Competition",
    "torneo": "Tournament",
    "campeonato": "Championship",
    "liga": "League",
    "ronda": "Round",
    "fase": "Phase",
    "jornada": "Matchday",
    "temporada": "Season",
    # Atributos específicos de atletismo
    "distancia": "Distance",
    "tiempo_record": "Record Time",
    "velocidad": "Speed",
    "altitud": "Altitude",
    # Atributos generales
    "categoria": "Category",
    "modalidad": "Modality",
    "tipoModalidad": "Modality Type",
    "numero": "Number",
    "dorsal": "Jersey Number",
    "participante": "Participant",
    "nombreParticipante": "Participant Name",
}

# Diccionario de traducciones de valores/categorías: español -> inglés
TRADUCCIONES_VALORES = {
    # Tipos de eventos
    "Eliminatoria": "Elimination",
    "Final": "Final",
    "Semifinal": "Semifinal",
    "Cuartos": "Quarterfinal",
    "Octavos": "Round of 16",
    # Estados/Resultados
    "Completado": "Completed",
    "Pendiente": "Pending",
    "Cancelado": "Canceled",
    "Aplazado": "Postponed",
    # Posiciones
    "Delantero": "Forward",
    "Portero": "Goalkeeper",
    "Centrocampista": "Midfielder",
    "Defensa": "Defender",
    "Lateral": "Fullback",
    "Central": "Center Back",
    "Base": "Point Guard",
    "Alero": "Wing",
    "Ala-Pívot": "Power Forward",
    "Pívot": "Center",
    "Libero": "Libero",
    # Roles de participantes
    "Árbitro": "Referee",
    "Juez": "Judge",
    "Árbitro Asistente": "Assistant Referee",
    "Árbitro de Línea": "Line Judge",
    "Árbitro de Silla": "Chair Umpire",
    "Árbitro de Red": "Net Judge",
    # Categorías/Niveles
    "Profesional": "Professional",
    "Amateur": "Amateur",
    "Juvenil": "Youth",
    "Infantil": "Children",
    "Senior": "Senior",
    "Femenino": "Female",
    "Masculino": "Male",
    "Mixto": "Mixed",
    "Individual": "Individual",
    "Colectivo": "Team",
    "Parejas": "Pairs",
    "Relevo": "Relay",
    "Grupal": "Group",
    "Dobles": "Doubles",
    # Tipos de entidades
    "Atleta": "Athlete",
    "Arbitro": "Referee",
    "Equipo": "Team",
    "Participante": "Participant",
    "eventoDeportivo": "Sports Event",
    "Deporte": "Sport",
    "Lugar": "Place",
    "Modalidad": "Modality",
    "Liga": "League",
    "Torneo": "Tournament",
    "Competencia": "Competition",
    "Instalacion": "Facility",
    # Deportes
    "Futbol": "Football",
    "Atletismo": "Athletics",
    "Voleibol": "Volleyball",
    "Natacion": "Swimming",
    "Tenis": "Tennis",
    "Basquetbol": "Basketball",
    "Beisbol": "Baseball",
    "Ciclismo": "Cycling",
    "Boxeo": "Boxing",
    "Lucha": "Wrestling",
    "Esgrima": "Fencing",
    "Judo": "Judo",
    "Karate": "Karate",
    "Taekwondo": "Taekwondo",
    "Gimnasia": "Gymnastics",
    # Instalaciones/Lugares
    "Piscina": "Swimming Pool",
    "Estadio": "Stadium",
    "Cancha": "Court",
    "Pista": "Track",
    "Gimnasio": "Gymnasium",
    "Velódromo": "Velodrome",
    "Hipódromo": "Hippodrome",
    "Arena": "Arena",
    "Campo": "Field",
    # Fases de competición
    "Grupal": "Group Stage",
    "Liguilla": "Preliminary Stage",
    "Repechaje": "Repechage",
    "Directa": "Direct Elimination",
    "Preliminar": "Preliminary",
    "Regular": "Regular Season",
    "Playoff": "Playoff",
    # Géneros y Sexos
    "Femenino": "Female",
    "Masculino": "Male",
    "Basquetbol": "Basketball",
    "Beisbol": "Baseball",
    "Ciclismo": "Cycling",
    "Boxeo": "Boxing",
    "Lucha": "Wrestling",
    "Esgrima": "Fencing",
    "Judo": "Judo",
    "Karate": "Karate",
    "Taekwondo": "Taekwondo",
    "Gimnasia": "Gymnastics",
    "Natacion Sincronizada": "Synchronized Swimming",
    "Clavados": "Diving",
    "Esqui": "Skiing",
    "Patinaje": "Skating",
    "Alpinismo": "Mountaineering",
    "Escalada": "Climbing",
    "Paracaidismo": "Skydiving",
    "Parapente": "Paragliding",
    "Piscina": "Swimming Pool",
    "Estadio": "Stadium",
    "Cancha": "Court",
    "Pista": "Track",
    "Gimnasio": "Gymnasium",
    "Velódromo": "Velodrome",
    "Hipódromo": "Hippodrome",
    "Arena": "Arena",
    "Campo": "Field",
    "Polígono": "Polygon",
    "Temporada": "Season",
    "Liga": "League",
    "Campeonato": "Championship",
    "Torneo": "Tournament",
    "Partido": "Match",
    "Jornada": "Matchday",
    "Clasificación": "Classification",
    "Tabla": "Standings",
    "Ranking": "Ranking",
    "Prueba": "Test",
    "Competencia": "Competition",
    "Competición": "Competition",
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

        # Búsqueda exacta en TIPOS_CONSULTA
        if token_norm in TIPOS_CONSULTA:
            tipos_buscados.update(TIPOS_CONSULTA[token_norm])
        else:
            # Búsqueda aproximada: si el token contiene al menos 70% de las letras de una clave
            encontrado = False
            for clave, tipos in TIPOS_CONSULTA.items():
                # Tolerancia: si el token es similar al clave (primera 3+ caracteres iguales)
                if len(token_norm) >= 3 and len(clave) >= 3:
                    # Comparar prefijos y sufijos para tolerar errores
                    if (token_norm.startswith(clave[:3]) or clave.startswith(token_norm[:3])):
                        tipos_buscados.update(tipos)
                        encontrado = True
                        break
            
            if not encontrado:
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

    # Si no hay tipos ni términos, búsqueda inútil
    if not tipos_buscados and not terminos:
        return []

    resultados = []

    for recurso in set(grafo.subjects()):
        if not isinstance(recurso, URIRef):
            continue

        if _es_meta_clase(grafo, recurso):
            continue

        # Caso 1: Solo tipo sin términos adicionales
        # Ejemplo: "atletism" reconocido como tipo Deporte
        # Devuelve todo lo que sea de ese tipo
        if tipos_buscados and not terminos:
            if _cumple_tipo(grafo, recurso, tipos_buscados):
                label = _obtener_nombre_principal(grafo, recurso, idioma)
                label_traducido = _traducir_etiqueta(label, idioma)

                tipo = _tipo_dominio(grafo, recurso)
                tipo_final = _tipo_etiqueta(grafo, tipo, idioma)
                tipo_final_traducido = _traducir_etiqueta(tipo_final, idioma)

                resultados.append(
                    {
                        "uri": str(recurso),
                        "label": label_traducido,
                        "tipo": tipo_final_traducido,
                        "lang": idioma,
                        "fuente": fuente,
                        "score": 90,
                    }
                )
        # Caso 2: Tipo + términos
        # Ejemplo: "atleta futbol" -> Atletas (tipo) en contexto de futbol (término)
        elif tipos_buscados and terminos:
            if not _cumple_tipo(grafo, recurso, tipos_buscados):
                continue

            contexto = _contexto_relacional(grafo, recurso, idioma)

            if all(termino in contexto for termino in terminos):
                label = _obtener_nombre_principal(grafo, recurso, idioma)
                label_traducido = _traducir_etiqueta(label, idioma)

                tipo = _tipo_dominio(grafo, recurso)

                tipo_final = _tipo_etiqueta(grafo, tipo, idioma)
                tipo_final_traducido = _traducir_etiqueta(tipo_final, idioma)

                resultados.append(
                    {
                        "uri": str(recurso),
                        "label": label_traducido,
                        "tipo": tipo_final_traducido,
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
            t_label_traducida = _traducir_etiqueta(t_label, idioma)
            tipos.append({"uri": t_str, "label": t_label_traducida})

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
        p_etiqueta_traducida = _traducir_propiedad(p_etiqueta, idioma)

        if isinstance(o, Literal):
            valor_str = str(o)
            valor_traducido = _traducir_valor(valor_str, idioma)
            
            propiedades.append(
                {
                    "propiedad_uri": p_str,
                    "propiedad": p_etiqueta_traducida,
                    "valor": valor_traducido,
                    "es_iri": False,
                }
            )
        elif isinstance(o, URIRef):
            o_str = str(o)
            o_etiqueta = _obtener_etiqueta_en_grafo(
                grafo, o, idioma
            ) or _uri_a_etiqueta(o_str)
            o_etiqueta_traducida = _traducir_etiqueta(o_etiqueta, idioma)
            
            propiedades.append(
                {
                    "propiedad_uri": p_str,
                    "propiedad": p_etiqueta_traducida,
                    "valor": o_str,
                    "valor_label": o_etiqueta_traducida,
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
        s_etiqueta_traducida = _traducir_etiqueta(s_etiqueta, idioma)
        
        p_str = str(p)
        p_etiqueta = _obtener_etiqueta_en_grafo(grafo, p, idioma) or _uri_a_etiqueta(
            p_str
        )
        p_etiqueta_traducida = _traducir_propiedad(p_etiqueta, idioma)
        
        relaciones_entrantes.append(
            {
                "sujeto": s_str,
                "sujeto_label": s_etiqueta_traducida,
                "propiedad": p_etiqueta_traducida,
                "propiedad_uri": p_str,
            }
        )

    relaciones_entrantes.sort(key=lambda x: (x["propiedad"], x["sujeto_label"]))

    label_final = _obtener_etiqueta_en_grafo(grafo, uri_ref, idioma) or _uri_a_etiqueta(uri)
    label_final_traducido = _traducir_etiqueta(label_final, idioma)

    return {
        "uri": uri,
        "label": label_final_traducido,
        "tipos": tipos,
        "propiedades": propiedades,
        "relaciones_entrantes": relaciones_entrantes,
    }
