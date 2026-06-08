import xml.etree.ElementTree as ET
try:
    tree = ET.parse('backend/ontology/deportes.rdf')
    root = tree.getroot()
    namespaces = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'rdfs': 'http://www.w3.org/2000/01/rdf-schema#', 'skos': 'http://www.w3.org/2004/02/skos/core#', 'owl': 'http://www.w3.org/2002/07/owl#'}
    count = 0
    for ind in root.findall('owl:NamedIndividual', namespaces):
        labels = {}
        for label in ind.findall('rdfs:label', namespaces):
            lang = label.attrib.get('{http://www.w3.org/XML/1998/namespace}lang')
            if lang:
                labels[lang] = label.text
        
        if 'es' in labels and 'en' in labels and 'de' in labels:
            if labels['es'] == labels['en'] or labels['es'] == labels['de']:
                uri = ind.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                name = uri.split('#')[-1] if '#' in uri else uri.split('/')[-1]
                print(f'{name} -> {labels["es"]}')
                count += 1
    print(f'Total untranslated: {count}')
except Exception as e:
    print('Error:', e)
