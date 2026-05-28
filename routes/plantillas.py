from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel
from typing import List, Dict, Any
import json, os
from google.oauth2 import service_account

FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT")
PLANTILLAS_COLLECTION = "plantillas"

FIRESTORE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS")
credentials_info = json.loads(FIRESTORE_CREDENTIALS_JSON)
credentials = service_account.Credentials.from_service_account_info(credentials_info)

_db = firestore.Client(project=FIRESTORE_PROJECT, credentials=credentials)

router = APIRouter(prefix="/plantillas", tags=["plantillas"])


class WidgetPlantilla(BaseModel):
    posicion: int
    id_widget: str
    titulo: str
    objetivo_widget: str
    descripcion_campos: Dict[str, Any]
    campos: Dict[str, Any]


class Plantilla(BaseModel):
    nombre: str                      # nombre legible, ej: "Plantilla Básica"
    widgets: List[WidgetPlantilla]   # el array 'plantilla' del payload actual


# ── 1. Listar todas las plantillas (solo id + nombre, liviano) ──────────────
@router.get("/")
async def listar_plantillas():
    docs = _db.collection(PLANTILLAS_COLLECTION).stream()
    return [
        {"id": doc.id, "nombre": doc.to_dict().get("nombre", doc.id)}
        for doc in docs
    ]


# ── 2. Bajar una plantilla completa ────────────────────────────────────────
@router.get("/{plantilla_id}")
async def bajar_plantilla(plantilla_id: str):
    doc = _db.collection(PLANTILLAS_COLLECTION).document(plantilla_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Plantilla '{plantilla_id}' no encontrada.")
    return {"id": doc.id, **doc.to_dict()}


# ── 3. Crear / sobreescribir una plantilla ─────────────────────────────────
@router.post("/{plantilla_id}")
async def crear_plantilla(plantilla_id: str, plantilla: Plantilla):
    ref = _db.collection(PLANTILLAS_COLLECTION).document(plantilla_id)

    ref.set({
        "nombre": plantilla.nombre,
        "widgets": [w.model_dump() for w in plantilla.widgets],
    })

    return {
        "ok": True,
        "id": plantilla_id,
        "nombre": plantilla.nombre,
        "total_widgets": len(plantilla.widgets),
    }
# ── 4. Eliminar una plantilla ───────────────────────────────────────────────
@router.delete("/{plantilla_id}")
async def eliminar_plantilla(plantilla_id: str):
    ref = _db.collection(PLANTILLAS_COLLECTION).document(plantilla_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Plantilla '{plantilla_id}' no encontrada.")
    ref.delete()
    return {"ok": True, "id": plantilla_id, "eliminada": True}