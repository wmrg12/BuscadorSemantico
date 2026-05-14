import { useState, useEffect, useRef } from "react";
import { buscarConsulta, obtenerClases, obtenerIdiomas } from "./services/api";
import "./App.css";

// Traducciones 
const TEXTOS_UI = {
  es: {
    title: "Buscador Semantico Deportivo",
    subtitle: "Ontologia RDF/OWL -  DBpedia -  Multilingue",
    placeholder: "Buscar deporte, atleta, evento...",
    btnSearch: "Buscar",
    tabLocal: "Ontologia Local",
    tabDbpedia: "DBpedia",
    noResults: "Sin resultados",
    loading: "Buscando...",
    labelSource: "Fuente",
    labelType: "Tipo",
    totalResults: "resultados",
    classes: "Clases",
    lang: "Idioma",
    abstract: "Descripción",
  },
  en: {
    title: "Sports Semantic Search",
    subtitle: "RDF/OWL Ontology - DBpedia - Multilingual",
    placeholder: "Search sport, athlete, event...",
    btnSearch: "Search",
    tabLocal: "Local Ontology",
    tabDbpedia: "DBpedia",
    noResults: "No results",
    loading: "Searching...",
    labelSource: "Source",
    labelType: "Type",
    totalResults: "results",
    classes: "Classes",
    lang: "Language",
    abstract: "Description",
  },
};

// Resultados
function TarjetaResultado({ elemento, textos }) {
  const [expandido, setExpandido] = useState(false);
  const esDbpedia = elemento.fuente === "dbpedia";

  return (
    <div className={`result-card ${esDbpedia ? "dbpedia" : "local"}`}>
      <div className="card-header">
        <span className="card-label">{elemento.label}</span>
        <span className={`badge ${esDbpedia ? "badge-dbpedia" : "badge-local"}`}>
          {esDbpedia ? "DBpedia" : "Local"}
        </span>
      </div>
      {elemento.tipo && (
        <div className="card-type">
          <span className="meta-key">{textos.labelType}:</span>
          <span className="meta-val">{elemento.tipo}</span>
        </div>
      )}
      {elemento.abstract && (
        <div className="card-abstract-wrap">
          <button
            className="toggle-abstract"
            onClick={() => setExpandido(!expandido)}
          >
            {expandido ? "Ver menos" : "Ver mas"} {textos.abstract}
          </button>
          {expandido && <p className="card-abstract">{elemento.abstract}</p>}
        </div>
      )}
      <div className="card-uri" title={elemento.uri}>
        {elemento.uri}
      </div>
    </div>
  );
}

//
export default function App() {
  const [idioma, setIdioma] = useState("es");
  const [idiomas, setIdiomas] = useState({ es: "Español", en: "English" });
  const [palabraClave, setPalabraClave] = useState("");
  const [resultados, setResultados] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [pestanaActiva, setPestanaActiva] = useState("local");
  const [clases, setClases] = useState([]);
  const [usarDbpedia, setUsarDbpedia] = useState(true);
  const entradaRef = useRef(null);

  const textos = TEXTOS_UI[idioma] || TEXTOS_UI.es;

  // Cargar idiomas y clases al inicio
  useEffect(() => {
    obtenerIdiomas()
      .then(respuesta => setIdiomas(respuesta.data.labels))
      .catch(() => { });
    entradaRef.current?.focus();
  }, []);

  useEffect(() => {
    obtenerClases(idioma)
      .then(respuesta => setClases(respuesta.data))
      .catch(() => { });
  }, [idioma]);

  const manejarBusqueda = async (evento) => {
    evento?.preventDefault();
    if (!palabraClave.trim()) return;
    setCargando(true);
    setResultados(null);
    try {
      const respuesta = await buscarConsulta(palabraClave, idioma, usarDbpedia);
      setResultados(respuesta.data);
      setPestanaActiva(respuesta.data.local?.length > 0 ? "local" : "dbpedia");
    } catch {
      setResultados({ local: [], dbpedia: [], total: 0, error: true });
    } finally {
      setCargando(false);
    }
  };

  const manejarTecla = (evento) => {
    if (evento.key === "Enter") manejarBusqueda();
  };

  const listaMostrar =
    resultados
      ? pestanaActiva === "local"
        ? resultados.local || []
        : resultados.dbpedia || []
      : [];

  return (
    <>
      <div className="app">
        {/*  Header  */}
        <header className="app-header">
          <h1 className="app-title">{textos.title}</h1>
          <p className="app-subtitle">{textos.subtitle}</p>
        </header>

        {/* Controles */}
        <div className="controls">
          {/* Selector idioma */}
          <div className="lang-selector">
            <span className="control-label">{textos.lang}</span>
            <div className="lang-pills">
              {Object.entries(idiomas).map(([codigo, nombre]) => (
                <button
                  key={codigo}
                  className={`lang-pill ${idioma === codigo ? "active" : ""}`}
                  onClick={() => setIdioma(codigo)}
                >
                  {codigo.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* DBpedia toggle */}
          <label className="toggle-wrap">
            <input
              type="checkbox"
              checked={usarDbpedia}
              onChange={evento => setUsarDbpedia(evento.target.checked)}
            />
            <span className="toggle-track">
              <span className="toggle-thumb" />
            </span>
            <span className="toggle-label">DBpedia</span>
          </label>
        </div>

        {/* Busqueda */}
        <div className="search-bar">
          <input
            ref={entradaRef}
            type="text"
            className="search-input"
            placeholder={textos.placeholder}
            value={palabraClave}
            onChange={evento => setPalabraClave(evento.target.value)}
            onKeyDown={manejarTecla}
          />
          <button
            className="search-btn"
            onClick={manejarBusqueda}
            disabled={cargando}
          >
            {cargando ? textos.loading : textos.btnSearch}
          </button>
        </div>

        {/* Clases disponibles */}
        {clases.length > 0 && !resultados && (
          <div className="classes-strip">
            <span className="strip-label">{textos.classes}:</span>
            {clases.slice(0, 12).map((clase, indice) => (
              <button
                key={indice}
                className="class-chip"
                onClick={() => { setPalabraClave(clase.label); }}
              >
                {clase.label}
              </button>
            ))}
          </div>
        )}

        {/* Resultados */}
        {resultados && (
          <div className="results-section">
            {/* Tabs */}
            <div className="tabs">
              <button
                className={`tab ${pestanaActiva === "local" ? "active" : ""}`}
                onClick={() => setPestanaActiva("local")}
              >
                {textos.tabLocal}
                <span className="tab-count">{resultados.local?.length ?? 0}</span>
              </button>
              <button
                className={`tab ${pestanaActiva === "dbpedia" ? "active" : ""}`}
                onClick={() => setPestanaActiva("dbpedia")}
              >
                {textos.tabDbpedia}
                <span className="tab-count">{resultados.dbpedia?.length ?? 0}</span>
              </button>
              <span className="total-badge">
                {resultados.total} {textos.totalResults}
              </span>
            </div>

            {/* Lista */}
            <div className="results-list">
              {listaMostrar.length === 0 ? (
                <div className="no-results">{textos.noResults}</div>
              ) : (
                listaMostrar.map((elemento, indice) => (
                  <TarjetaResultado key={indice} elemento={elemento} textos={textos} />
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}