# Buscador Semantico

Este proyecto es una aplicacion web de busqueda semantica multilingue. Consiste en un backend desarrollado en Python (Flask) que consulta una ontologia local e interactua con DBpedia, y un frontend moderno desarrollado con React y Vite.

## Requisitos Previos

Antes de ejecutar el proyecto, asegurate de tener instalados:

- [Python](https://www.python.org/downloads/) (version 3.8 o superior recomendada)
- [Node.js](https://nodejs.org/) (incluye `npm`, version 16 o superior recomendada)

---

## Configuracion del Backend

El backend se encarga de procesar las consultas, analizar el lenguaje natural y hacer la busqueda semantica en la ontologia RDF.

### Librerias Utilizadas
- **Flask** & **Flask-CORS**: Para crear la API y permitir peticiones desde el frontend.
- **rdflib**: Para leer y manipular grafos y archivos `.rdf`.
- **SPARQLWrapper**: Para ejecutar consultas SPARQL externas (ej. DBpedia).
- **pyparsing**: Dependencia para el manejo de consultas y expresiones.

### Pasos para montar el Backend

1. Abre una terminal y dirigete a la carpeta `backend`:
   ```bash
   cd backend
   ```

2. (Opcional pero recomendado) Crea y activa un entorno virtual:
   - **En Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **En macOS/Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Instala las dependencias (puedes instalar todo de golpe con `pip install -r requirements.txt`, o una por una con estos comandos especificos):
   ```bash
   pip install flask
   pip install flask-cors
   pip install rdflib==6.3.2
   pip install pyparsing==2.4.7
   pip install SPARQLWrapper
   ```

4. Inicia el servidor:
   ```bash
   python app.py
   ```
   El backend estara disponible en `http://127.0.0.1:5000`.

---

## Configuracion del Frontend

El frontend es la interfaz grafica de la aplicacion web, desarrollada con React y la herramienta de construccion ultrarrapida Vite.

### Librerias Utilizadas
- **React** & **React-DOM**: Librerias principales para construir la interfaz.
- **Vite**: Entorno de desarrollo rapido.
- **Axios**: Cliente HTTP para realizar las peticiones a la API del backend.

### Pasos para montar el Frontend

1. Abre una **nueva** terminal (manteniendo el backend corriendo en la anterior) y dirigete a la carpeta `frontend`:
   ```bash
   cd frontend
   ```

2. Instala las dependencias de Node.js (se recomienda usar solo `npm install` para instalar todo automaticamente desde el `package.json`, pero si necesitas los comandos especificos son):
   ```bash
   npm install react react-dom axios
   npm install -D vite @vitejs/plugin-react eslint
   ```

3. Inicia el servidor de desarrollo:
   ```bash
   npm run dev
   ```

4. Abre tu navegador y dirigete a la URL que te proporciona Vite en la terminal (por lo general, es `http://localhost:5173`).

---

## Uso de la aplicacion

Asegurate de tener ambas terminales corriendo al mismo tiempo (una para el Backend con Python y otra para el Frontend con Node.js). Una vez en el navegador, podras introducir terminos de busqueda y el sistema te devolvera los resultados extraidos de la ontologia semantica.
