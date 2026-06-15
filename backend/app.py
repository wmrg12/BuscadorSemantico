import threading
from rdflib import Graph

# Monkey-patch rdflib Graph.query to make it thread-safe.
# This prevents pyparsing concurrency bugs (like the Param.postParse2 TypeError) 
# when multiple queries are executed in parallel by Flask's multi-threaded server.
original_query = Graph.query
query_lock = threading.Lock()

def thread_safe_query(self, *args, **kwargs):
    with query_lock:
        return original_query(self, *args, **kwargs)

Graph.query = thread_safe_query

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
    aplicacion.run(debug=True, use_reloader=False)
