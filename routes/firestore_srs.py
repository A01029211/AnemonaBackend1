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
RESOURCE_ID = "6363802327509368832"

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
    plantilla: List[Dict[str, Any]]




@router.post("/subir")
async def subir_documento(payload: DocumentoPayload):
    try:
        _db.collection(COLLECTION).document(DOC_ID).set(payload.data)
        return {"ok": True, "mensaje": f"Documento '{DOC_ID}' guardado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bajar")
async def bajar_documento(doc_id: str):
    try:
        doc = _db.collection(COLLECTION).document(doc_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return {"ok": True, "data": doc.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint específico para obtener nodos y aristas para la arquitectura
@router.get("/arquitectura")
async def obtener_arquitectura(doc_id: str):
    try:
        doc = _db.collection(COLLECTION).document(doc_id).get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        data = doc.to_dict() or {}

        return {
            "ok": True,
            "doc_id": doc_id,
            "nodes": data.get("NODOS", []),
            "edges": data.get("ARISTAS", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generar-arquitectura")
async def generar_arquitectura(session_id: str):
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id requerido")

        # Ejecuta el agente remoto de Vertex
        response = await remote_app.async_run(
            session_id=session_id,
            input="crea los nodos para el diagrama de arquitectura"
        )

        return {
            "ok": True,
            "mensaje": "Agente ejecutado correctamente",
            "response": response
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/new_project")
async def new_project(payload: NuevoProyectoPayload, db: Session = Depends(get_db)):
    try:
        widgets = [dict(w) for w in payload.plantilla]
        formulario = payload.formulario

        # 1. Inyectar datos del formulario en w_000
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

        for widget in widgets:
            if widget["id_widget"] == "w_000":
                for campo_modelo, campo_plantilla in mapeo.items():
                    valor = getattr(formulario, campo_modelo, None)
                    if valor is not None:
                        widget["campos"][campo_plantilla] = valor
                if formulario.departamentos_impactados:
                    widget["campos"]["AREAS_IMPACTADAS"] = formulario.departamentos_impactados
                break

        # 2. Construir el documento con la misma estructura que /modificar
        widgets_ordenados = sorted(widgets, key=lambda w: w["posicion"])

        nuevo_doc = {}
        for w in widgets:
            nuevo_doc[w["id_widget"]] = {
                "titulo":             w["titulo"],
                "descripcion_campos": w["descripcion_campos"],
                "campos":             w["campos"],
            }

        nuevo_doc["posiciones"] = [w["id_widget"] for w in widgets_ordenados]

        # 3. Subir a Firestore
        async def crear_firestore():
            def _crear():
                _, doc_ref = _db.collection(COLLECTION).add(nuevo_doc)
                return doc_ref.id
            return await asyncio.to_thread(_crear)

        # 4. Crear sesión en Vertex AI
        async def crear_vertex_session(id_firestore_document):
            def _crear():
                remote_session = remote_app.create_session(
                    user_id=formulario.usuario_id,
                    state={"doc_id": id_firestore_document}
                )
                return remote_session["id"]
            return await asyncio.to_thread(_crear)

        firestore_id = await crear_firestore()
        session_id   = await crear_vertex_session(firestore_id)

        # 5. Guardar sesión en memoria
        sessions[session_id] = {
            "user_id":    formulario.usuario_id,
            "session_id": session_id,
            "project_id": firestore_id,
        }

        # 6. Insertar en SQL
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
                fecha_conclusion=None,
                id_firestore_document=firestore_id,
            )
            db.add(nueva_session)
            db.commit()
            db.refresh(nuevo_proyecto)
            return nuevo_proyecto.folio

        folio = await asyncio.to_thread(insertar_en_sql)

        return {
            "ok":         True,
            "project_id": firestore_id,
            "session_id": session_id,
            "folio":      folio,
            "orden":      nuevo_doc["posiciones"],
            "mensaje":    f"Documento '{firestore_id}' y sesión '{session_id}' creados",
        }

    except Exception as e:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=500, detail=str(e))
    


def eliminar_documento_firestore(id_firestore_document: str):
    try:
        doc_ref = _db.collection(COLLECTION).document(id_firestore_document)
        doc = doc_ref.get()

        if not doc.exists:
            raise Exception("El documento no existe en Firestore")
        
        doc_ref.delete()
        return True
    
    except Exception as e:
        raise Exception(f"Error al eliminar el documento de Firestore: {str(e)}")
    