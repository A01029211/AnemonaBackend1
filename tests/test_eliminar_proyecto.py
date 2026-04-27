
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

#Test para endpoint de eliminar un proyecto específico, cuando el proyecto que se quiere eliminar no existe
def test_eliminar_proyecto_no_existente():
    response = client.delete("/proyectos/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Proyecto no encontrado"

