import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))

project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.utils import tools


def test_get_services_by_category():
    """Prueba que la búsqueda de servicios devuelva los campos correctos"""
    results = tools.get_services_by_category('Legal', 'Valencia')
    
    print(results)  # Para depuración, muestra los resultados obtenidos
    assert len(results) > 0 

def test_service_not_found():
    """Prueba el comportamiento cuando no hay resultados"""
    results = tools.get_services_by_category('Comida', 'Madrid')
    assert len(results) == 0

if __name__ == "__main__":
    test_get_services_by_category()
    test_service_not_found()