import os
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

DEPORTE_NS = Namespace("http://www.semanticweb.org/ontologies/deportes#")

# Grafo principal de la ontología local
grafo = Graph()
grafo.bind("deporte", DEPORTE_NS)

# Grafo para la ontología / RDF de DBpedia local
grafo_dbpedia = Graph()

DIRECTORIO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTORIO_ONTOLOGIA = os.path.join(DIRECTORIO_BASE, "ontology")

# Formatos soportados para cargar archivos RDF/OWL/Turtle
FORMATOS_SOPORTADOS = {
    ".rdf": "xml",
    ".owl": "xml",
    ".ttl": "turtle",
    ".nt": "nt",
    ".xml": "xml",
    ".jsonld": "json-ld",
}

archivos_cargados_locales = []
archivos_cargados_dbpedia = []

def _cargar_grafo_desde_archivo(grafo_objetivo: Graph, ruta_archivo: str, formato: str) -> bool:
    try:
        grafo_objetivo.parse(ruta_archivo, format=formato)
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo cargar {os.path.basename(ruta_archivo)}: {e}")
        return False


def _es_archivo_dbpedia(nombre_archivo: str) -> bool:
    nombre = nombre_archivo.lower()
    return "dbpedia" in nombre or "depedia" in nombre


# Cargar archivos ontológicos desde la carpeta ontology/
if os.path.isdir(DIRECTORIO_ONTOLOGIA):
    for nombre_archivo in os.listdir(DIRECTORIO_ONTOLOGIA):
        extension = os.path.splitext(nombre_archivo)[1].lower()

        if extension in FORMATOS_SOPORTADOS:
            ruta_archivo = os.path.join(DIRECTORIO_ONTOLOGIA, nombre_archivo)
            formato = FORMATOS_SOPORTADOS[extension]

            if _es_archivo_dbpedia(nombre_archivo):
                if _cargar_grafo_desde_archivo(grafo_dbpedia, ruta_archivo, formato):
                    archivos_cargados_dbpedia.append(nombre_archivo)
                    print(f"[OK] DBpedia cargado: {nombre_archivo} ({formato})")
            else:
                if _cargar_grafo_desde_archivo(grafo, ruta_archivo, formato):
                    archivos_cargados_locales.append(nombre_archivo)
                    print(f"[OK] Local cargado: {nombre_archivo} ({formato})")
else:
    print(f"[WARN] No existe el directorio de ontología: {DIRECTORIO_ONTOLOGIA}")

print(
    f"Total tripletas locales: {len(grafo)} | Archivos: {archivos_cargados_locales}"
)
print(
    f"Total tripletas DBpedia: {len(grafo_dbpedia)} | Archivos: {archivos_cargados_dbpedia}"
)


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


def _crear_regex_acentos(palabra: str) -> str:
    p = palabra.lower()
    p = p.replace("a", "[aáäAÁÄ]").replace("e", "[eéëEÉË]").replace("i", "[iíïIÍÏ]")
    p = p.replace("o", "[oóöOÓÖ]").replace("u", "[uúüUÚÜ]")
    return p


def _obtener_etiqueta_en_grafo(grafo_obj: Graph, uri_ref, idioma: str = "es") -> str | None:
    for etiqueta in grafo_obj.objects(uri_ref, RDFS.label):
        if isinstance(etiqueta, Literal) and etiqueta.language == idioma:
            return str(etiqueta)

    for etiqueta in grafo_obj.objects(uri_ref, RDFS.label):
        if isinstance(etiqueta, Literal) and not etiqueta.language:
            return str(etiqueta)

    return None


def _es_meta_clase(grafo_obj: Graph, s) -> bool:
    meta_classes = {
        OWL.Class,
        RDFS.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"),
    }

    for t in grafo_obj.objects(s, RDF.type):
        if t in meta_classes:
            return True
    return False


def _buscar_en_grafo(
    grafo_obj: Graph,
    palabra_clave: str,
    idioma: str = "es",
    fuente: str = "local",
    limite: int = 10,
) -> list[dict]:
    import re

    palabras = [p.strip() for p in palabra_clave.split() if p.strip()]
    if not palabras:
        return []

    # Búsqueda compuesta: todas las palabras deben aparecer
    patrones = []
    for pal in palabras:
        regex_str = _crear_regex_acentos(pal)
        patrones.append(re.compile(regex_str, re.IGNORECASE))

    consulta_norm = _normalizar_texto(palabra_clave)

    datos = []
    vistos = set()

    for s in set(grafo_obj.subjects()):
        if not isinstance(s, URIRef):
            continue

        if _es_meta_clase(grafo_obj, s):
            continue

        textos_sujeto = [str(s), _uri_a_etiqueta(str(s))]

        for t in grafo_obj.objects(s, RDF.type):
            textos_sujeto.append(str(t))
            textos_sujeto.append(_uri_a_etiqueta(str(t)))

        for p, o in grafo_obj.predicate_objects(s):
            if isinstance(o, Literal) or isinstance(o, URIRef):
                textos_sujeto.append(str(o))
                if isinstance(o, URIRef):
                    textos_sujeto.append(_uri_a_etiqueta(str(o)))

        texto_completo = _normalizar_texto(" ".join(textos_sujeto))

        # Deben aparecer todas las palabras de la consulta
        if not all(pat.search(texto_completo) for pat in patrones):
            continue

        # Score simple para priorizar coincidencias más exactas
        score = 80
        if consulta_norm and consulta_norm in texto_completo:
            score = 100

        uri_str = str(s)

        label = None
        for l in grafo_obj.objects(s, RDFS.label):
            if isinstance(l, Literal) and (l.language == idioma or not l.language):
                label = str(l)
                break

        if not label:
            label = _uri_a_etiqueta(uri_str)

        tipo = None
        for t in grafo_obj.objects(s, RDF.type):
            if t != OWL.NamedIndividual and not _es_meta_clase(grafo_obj, t):
                tipo = str(t)
                break

        tipo_final = _uri_a_etiqueta(tipo) if tipo else "Recurso"

        if uri_str not in vistos:
            vistos.add(uri_str)
            datos.append(
                {
                    "uri": uri_str,
                    "label": label,
                    "tipo": tipo_final,
                    "lang": idioma,
                    "fuente": fuente,
                    "score": score,
                }
            )

        if len(datos) >= limite:
            break

    datos.sort(key=lambda x: (-x["score"], x["label"].lower()))
    return datos[:limite]


def obtener_todos_los_sujetos(idioma: str = "es") -> list[dict]:
    datos = []
    vistos = set()

    for grafo_obj, fuente in [(grafo, "local"), (grafo_dbpedia, "dbpedia")]:
        for s in set(grafo_obj.subjects()):
            if not isinstance(s, URIRef):
                continue

            uri_str = str(s)
            if uri_str in vistos:
                continue
            vistos.add(uri_str)

            etiqueta = _obtener_etiqueta_en_grafo(grafo_obj, s, idioma) or _uri_a_etiqueta(uri_str)
            datos.append(
                {
                    "uri": uri_str,
                    "label": etiqueta,
                    "lang": idioma,
                    "fuente": fuente,
                }
            )

            if len(datos) >= 50:
                return datos

    return datos


def buscar_deporte_dbpedia(palabra_clave: str, idioma: str = "es") -> list[dict]:
    return _buscar_en_grafo(
        grafo_dbpedia,
        palabra_clave,
        idioma=idioma,
        fuente="dbpedia",
        limite=10,
    )