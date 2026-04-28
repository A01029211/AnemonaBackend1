#Este modelo representa la estructura del widget para poder modifcar la lista de contenidos 
#del SRS y que cree
from pydantic import BaseModel
from typing import Dict, Any

class Widget(BaseModel):
    posicion: int
    id_widget: str
    titulo: str
    # descripción de cada campo (ej: {"nombre": "Nombre del usuario"})
    descripcion_campos: Dict[str, str]
    # valores de los campos (ej: {"nombre": "Darío"})
    campos: Dict[str, Any]
    
    