import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from google.oauth2 import service_account
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from requests import Session
import vertexai
from vertexai import agent_engines
from fastapi import APIRouter, HTTPException, Depends

from database import get_db
from models import Proyecto, SessionChat
from fastapi import FastAPI
from typing import List

app = FastAPI()
FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT")
COLLECTION = os.getenv("FIRESTORE_COLLECTION", "documentos")
FIRESTORE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_FIRESTORE")
credentials = service_account.Credentials.from_service_account_file(
    FIRESTORE_CREDENTIALS_PATH
)
_db = firestore.Client(
    project=FIRESTORE_PROJECT,
    credentials=credentials
)
router = APIRouter(prefix="/widgets", tags=["widgets"])

class Widget(BaseModel):
    posicion: int
    id_widget: str
    titulo: str
    # descripción de cada campo (ej: {"nombre": "Nombre del usuario"})
    descripcion_campos: Dict[str, str]
    # valores de los campos (ej: {"nombre": "Darío"})
    campos: Dict[str, Any]

    
@router.get("/bajar")
async def bajar_documento(doc_id: str):
    try:
        doc = _db.collection(COLLECTION).document(doc_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return doc.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    


@router.post("/modificar/{doc_id}")
async def crear_widgets(widgets: List[Widget], doc_id: str ):
    doc = await bajar_documento(doc_id)
    
    SKIP_FIELDS = {"posiciones", "nodos"}
    
    ids_recibidos = {w.id_widget for w in widgets}
    
    nuevo_doc = {}
    for key in doc:
        if key in SKIP_FIELDS:
            continue
        if key in ids_recibidos:
            nuevo_doc[key] = doc[key]
    
    for w in widgets:
        nuevo_doc[w.id_widget] = {
            "titulo": w.titulo,
            "descripcion_campos": w.descripcion_campos,
            "campos": w.campos,
        }
    
    widgets_ordenados = sorted(widgets, key=lambda w: w.posicion)
    nuevo_doc["posiciones"] = [w.id_widget for w in widgets_ordenados]

    _db.collection(COLLECTION).document(doc_id).set(nuevo_doc)

    return {"orden": nuevo_doc["posiciones"], "widgets_guardados": list(nuevo_doc.keys())}