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

load_dotenv()

FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT")
COLLECTION = os.getenv("FIRESTORE_COLLECTION", "documentos")
DOC_ID = "DDYWBQOZG2WYrHrs4a3e"

FIRESTORE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_FIRESTORE")
credentials = service_account.Credentials.from_service_account_file(
    FIRESTORE_CREDENTIALS_PATH
)
_db = firestore.Client(
    project=FIRESTORE_PROJECT,
    credentials=credentials
)

PROJECT_ID = "anemona-2130e"
LOCATION = "us-central1"
RESOURCE_ID = "4527541493065318400"

AGENT_RESOURCE_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{RESOURCE_ID}"

# Initialize Vertex AI — una sola vez
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Instancia del agente — una sola vez al arrancar
remote_app = agent_engines.get(AGENT_RESOURCE_NAME)

router = APIRouter(prefix="/firestore", tags=["firestore"])


class DocumentoPayload(BaseModel):
    data: dict

sessions = {}


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
    usuario_id: Optional[str] = None
    session_id: Optional[str] = None


class NuevoProyectoPayload(BaseModel):
    formulario: Formulario
    plantilla: Dict[str, Any]


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


@router.post("/new_project")
async def new_project(payload: NuevoProyectoPayload, db: Session = Depends(get_db)):
    try:
        # 1. Plantilla base
        documento = payload.plantilla.copy()
        formulario = payload.formulario
        mapeo = {
            "solicitante":          "SOLICITANTE",
            "dga":                  "DGA",
            "info_contacto":        "INFO_CONTACTO",
            "patrocinador":         "PATROCINADOR",
            "nombre_socio_negocio": "SOCIO",
            "cr":                   "CR",
            "nombre_iniciativa":    "NOMBRE_INICIATIVA",
            "tipo_iniciativa":      "TIPO_INICIATIVA",
        }
        datos_generales = documento.get("DATOS_GENERALES", {})
        for campo_modelo, campo_plantilla in mapeo.items():
            valor = getattr(formulario, campo_modelo, None)
            if valor is not None:
                datos_generales[campo_plantilla] = valor
        documento["DATOS_GENERALES"] = datos_generales

        if formulario.departamentos_impactados:
            documento["AREAS_IMPACTADAS"] = [
                {"AREA_NEGOCIO": area, "PROCESO_IMPACTO": ""}
                for area in formulario.departamentos_impactados
            ]

        # 2. Firestore y Vertex AI corren en paralelo
        async def crear_firestore():
            _, doc_ref = _db.collection(COLLECTION).add(documento)
            return doc_ref.id

        async def crear_vertex_session():
            remote_session = await remote_app.async_create_session(
                user_id=formulario.usuario_id
            )
            return remote_session["id"]

        project_id, session_id = await asyncio.gather(
            crear_firestore(),
            crear_vertex_session()
        )

        # 3. Guardar sesión en memoria
        sessions[session_id] = {
            "user_id":    formulario.usuario_id,
            "session_id": session_id,
            "project_id": project_id
        }

        # 4. Insertar en SQL en un thread separado para no bloquear
        def insertar_en_sql():
            nuevo_proyecto = Proyecto(
                fechacreacion=datetime.now(),
                fechaactualizacion=datetime.now(),
                nombreproyecto=formulario.nombre_iniciativa,
                tipoiniciativa=formulario.tipo_iniciativa,
                cr=int(formulario.cr) if formulario.cr and formulario.cr.isdigit() else None,
                patrocinador=formulario.patrocinador,
                socionegocio=formulario.nombre_socio_negocio,
                descripciongeneral=formulario.info_contacto,
                participacionareas=", ".join(formulario.departamentos_impactados)
                if formulario.departamentos_impactados else None,
            )
            db.add(nuevo_proyecto)
            db.flush()

            nueva_session = SessionChat(
                session_id=session_id,
                folio=nuevo_proyecto.folio,
                idusuario=formulario.usuario_id if formulario.usuario_id else None,
                fecha_inicio=datetime.now(),
                fecha_conclusion=None
            )
            db.add(nueva_session)
            db.commit()
            db.refresh(nuevo_proyecto)
            return nuevo_proyecto.folio

        folio = await asyncio.to_thread(insertar_en_sql)

        return {
            "ok":         True,
            "project_id": project_id,
            "session_id": session_id,
            "mensaje":    f"Proyecto '{project_id}' y sesión '{session_id}' creados"
        }

    except Exception as e:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=500, detail=str(e))