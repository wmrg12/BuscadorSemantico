import axios from "axios";

const API = axios.create({
    baseURL: "http://127.0.0.1:5000",
});

// Busqueda semantica combinada (local + DBpedia)
export const buscarConsulta = (palabraClave, idioma = "es", dbpedia = true) =>
    API.get("/search/query", { params: { q: palabraClave, lang: idioma, dbpedia } });

// Todas las clases OWL/RDFS
export const obtenerClases = (idioma = "es") =>
    API.get("/search/classes", { params: { lang: idioma } });

// Individuos (todos, o por clase)
export const obtenerIndividuos = (claseUri = null, idioma = "es") =>
    API.get("/search/individuals", { params: { clase: claseUri, lang: idioma } });

// Idiomas disponibles
export const obtenerIdiomas = () => API.get("/search/langs");

// Obtener detalles completos de un recurso individual de la ontología
export const obtenerDetallesRecurso = (uri, idioma = "es") =>
    API.get("/search/details", { params: { uri, lang: idioma } });

export default API;