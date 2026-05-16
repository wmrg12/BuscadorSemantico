# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.


## Backend — Instalacion

### 1. Crear entorno virtual (recomendado)

```bash
cd backend
python -m venv venv
```

Activar el entorno:

```bash
# Windows
venv\Scripts\activate

```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### Contenido de `requirements.txt`

```
flask
flask-cors
rdflib
SPARQLWrapper
```

```bash
cd backend
python app.py
```

El servidor corre en: `http://127.0.0.1:5000`

---

## Frontend — Instalación

### 1. Instalar dependencias

```bash
cd frontend
npm install
```

### 2. Ejecutar en desarrollo

```bash
npm run dev
```

El frontend corre en: `http://localhost:5173`


## Levantar el proyecto completo

Abre **dos terminales**:

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate      
python app.py
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Luego abre el navegador en `http://localhost:5173`

---

### `SPARQLWrapper` no encontrado
```bash
pip install SPARQLWrapper
```
