from flask import Flask
from flask_cors import CORS
from routes.search_routes import busqueda_bp

aplicacion = Flask(__name__)
CORS(aplicacion)

aplicacion.register_blueprint(busqueda_bp)


@aplicacion.route("/")
def inicio():
    return "RDF/OWL + DBpedia + Multilingue - RESPONDE"


if __name__ == "__main__":
    aplicacion.run(debug=True)
