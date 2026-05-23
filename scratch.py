import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
from services.ontology_service import graph
from queries.search import busqueda_local

def test_search():
    keyword = "natacion 100m"
    res = busqueda_local(keyword)
    print(f"Results for '{keyword}':")
    for r in res:
        print(r)

if __name__ == "__main__":
    test_search()
