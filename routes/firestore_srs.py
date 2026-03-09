from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT")
COLLECTION        = os.getenv("FIRESTORE_COLLECTION", "documentos")
DOC_ID            = "DDYWBQOZG2WYrHrs4a3e"

router = APIRouter(prefix="/firestore", tags=["firestore"])
_db = firestore.Client(project=FIRESTORE_PROJECT)


class DocumentoPayload(BaseModel):
    data: dict


@router.post("/subir")
async def subir_documento(payload: DocumentoPayload):
    try:
        _db.collection(COLLECTION).document(DOC_ID).set(payload.data)
        return {"ok": True, "mensaje": f"Documento '{DOC_ID}' guardado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bajar")
async def bajar_documento():
    try:
        doc = _db.collection(COLLECTION).document(DOC_ID).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return {"ok": True, "data": doc.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
