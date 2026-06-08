import re

def procesar_ontologia():
    print("Iniciando traducción de la ontología...")
    with open('backend/ontology/deportes.rdf', 'r', encoding='utf-8') as f:
        contenido = f.read()

    etiquetas = ['rdfs:label', 'skos:prefLabel', 'descripcionDeporte']
    
    traducciones_hechas = 0

    for tag in etiquetas:
        # Busca 3 etiquetas consecutivas (es, en, de) con el MISMO contenido
        pattern = rf'<{tag} xml:lang="es">(.*?)</{tag}>\s*<{tag} xml:lang="en">\1</{tag}>\s*<{tag} xml:lang="de">\1</{tag}>'
        
        def replacer(match):
            nonlocal traducciones_hechas
            texto = match.group(1)
            texto_en = texto
            texto_de = texto
            modificado = False
            
            if texto.startswith("Cancha "):
                nombre = texto[7:]
                texto_en = f"Sport field {nombre}"
                texto_de = f"Sportplatz {nombre}"
                modificado = True
            elif texto.startswith("Club "):
                nombre = texto[5:]
                texto_en = f"Club {nombre}"
                texto_de = f"Klub {nombre}"
                modificado = True
            elif texto.startswith("Campeonato "):
                nombre = texto[11:]
                texto_en = f"{nombre} Championship"
                texto_de = f"{nombre} Meisterschaft"
                modificado = True
            elif texto.startswith("Torneo "):
                nombre = texto[7:]
                texto_en = f"{nombre} Tournament"
                texto_de = f"{nombre} Turnier"
                modificado = True
            elif texto.startswith("Liga "):
                nombre = texto[5:]
                texto_en = f"{nombre} League"
                texto_de = f"{nombre} Liga"
                modificado = True
            elif texto.startswith("Asociacion "):
                nombre = texto[11:]
                texto_en = f"{nombre} Association"
                texto_de = f"{nombre} Verband"
                modificado = True

            if modificado:
                traducciones_hechas += 1
                print(f"Traducido: {texto} -> EN: {texto_en} | DE: {texto_de}")
            
            # Mantenemos la indentación original aproximada (8 espacios)
            return f'<{tag} xml:lang="es">{texto}</{tag}>\n        <{tag} xml:lang="en">{texto_en}</{tag}>\n        <{tag} xml:lang="de">{texto_de}</{tag}>'
            
        contenido = re.sub(pattern, replacer, contenido)

    with open('backend/ontology/deportes_traducido.rdf', 'w', encoding='utf-8') as f:
        f.write(contenido)
    
    print(f"\n¡Listo! Se realizaron {traducciones_hechas} traducciones.")
    print("Archivo 'deportes_traducido.rdf' generado con éxito en backend/ontology/")

if __name__ == '__main__':
    procesar_ontologia()
