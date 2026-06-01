#!/usr/bin/env python3
"""
Script simple de validación sin dependencias externas:
Busca propiedades y valores en archivos RDF usando regex
"""
import os
import re
from collections import defaultdict

ONTOLOGY_DIR = "./ontology"

# Diccionarios de traducción (copiados del código)
TRADUCCIONES_PROPIEDADES = {
    "nombreDeporte", "descripcionDeporte", "tipoDeporte", "deporte",
    "nombreAtleta", "apellidoAtleta", "nombre", "apellido", "nacionalidad",
    "edad", "altura", "peso", "fechaNacimiento", "lugarNacimiento",
    "nombreEvento", "descripcionEvento", "fechaEvento", "lugarEvento",
    "tipoEvento", "evento", "nombreEquipo", "descripcionEquipo",
    "temporadaEquipo", "equipo", "nombreLugar", "descripcionLugar",
    "capacidad", "ciudad", "pais", "locacion", "ubicacion", "direccion",
    "correspondeA", "seRealizaEn", "tieneModalidad", "tieneParticipante",
    "numeroParticipantes", "reglamentoBase", "rol", "horaEvento",
    "participantes", "atletas", "equipos", "árbitros", "eventos",
    "miembros", "compite_en", "arbitrado_por", "resultado", "puntuacion",
    "goles", "puntos", "tiempo", "clasificacion", "ranking", "posicion",
    "puesto", "victorias", "derrotas", "empates", "competencia",
    "competicion", "torneo", "campeonato", "liga", "ronda", "fase",
    "jornada", "temporada", "distancia", "tiempo_record", "velocidad",
    "altitud", "categoria", "modalidad", "tipoModalidad", "numero",
    "dorsal", "participante", "nombreParticipante", "label", "comment"
}

propiedades_reales = set()
valores_literales = defaultdict(set)

print("=== ESCANEANDO PROPIEDADES EN ARCHIVOS RDF ===\n")

# Regex para encontrar propiedades en RDF
prop_regex = r'rdf:about="[^"]*?/([a-zA-Z_]+)"'

for archivo in os.listdir(ONTOLOGY_DIR):
    if not archivo.endswith(".rdf"):
        continue
    
    ruta = os.path.join(ONTOLOGY_DIR, archivo)
    print(f"Leyendo: {archivo}")
    
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
            # Encontrar todas las propiedades
            matches = re.findall(prop_regex, contenido)
            propiedades_reales.update(matches)
            
            # Buscar valores de texto en labels
            label_matches = re.findall(r'<rdfs:label[^>]*>([^<]+)</rdfs:label>', contenido)
            valores_literales["rdfs:label"].update(label_matches)
            
            # Buscar valores en comentarios
            comment_matches = re.findall(r'<rdfs:comment[^>]*>([^<]+)</rdfs:comment>', contenido)
            valores_literales["rdfs:comment"].update(comment_matches)
            
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n✓ Total propiedades encontradas: {len(propiedades_reales)}")
print(f"  - Traducidas: {len([p for p in propiedades_reales if p in TRADUCCIONES_PROPIEDADES])}")
print(f"  - SIN TRADUCIR: {len([p for p in propiedades_reales if p not in TRADUCCIONES_PROPIEDADES])}")

sin_traducir = sorted([p for p in propiedades_reales if p not in TRADUCCIONES_PROPIEDADES])
if sin_traducir:
    print("\n⚠️  PROPIEDADES SIN TRADUCIR:")
    for prop in sin_traducir:
        print(f"   \"{prop}\",")

print(f"\n📊 Ejemplos de valores únicos encontrados:")
for prop, vals in list(valores_literales.items())[:3]:
    print(f"\n{prop}: {len(vals)} únicos")
    ejemplos = sorted(list(vals))[:5]
    for val in ejemplos:
        if len(val) < 80:
            print(f"  - {val}")
