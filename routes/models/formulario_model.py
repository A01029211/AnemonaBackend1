from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Formulario(BaseModel):
    solicitante: Optional[str] = None
    dga: Optional[str] = None
    info_contacto: Optional[str] = None
    patrocinador: Optional[str] = None
    nombre_socio_negocio: Optional[str] = None
    cr: Optional[str] = None
    nombre_iniciativa: Optional[str] = None
    departamentos_impactados: Optional[List[str]] = None
    tipo_iniciativa: Optional[str] = None
    usuario_nombre: Optional[str] = None
    usuario_id: Optional[int] = None

class Plantilla(BaseModel):
    data: Dict[str, Any]