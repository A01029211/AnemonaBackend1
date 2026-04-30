import asyncio
import inspect
import traceback
from datetime import datetime
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from google.cloud import firestore
from google.oauth2 import service_account
from pydantic import BaseModel
from requests import Session
import os
import vertexai
from vertexai import agent_engines

from database import get_db
from models import Proyecto, SessionChat

load_dotenv()

# ── Configuración Firestore ──────────────────────────────────────────────────
FIRESTORE_PROJECT      = os.getenv("FIRESTORE_PROJECT")
COLLECTION             = os.getenv("FIRESTORE_COLLECTION", "documentos")
FIRESTORE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_FIRESTORE")

credentials = service_account.Credentials.from_service_account_file(
    FIRESTORE_CREDENTIALS_PATH
)
_db = firestore.Client(
    project=FIRESTORE_PROJECT,
    credentials=credentials,
)

# ── Configuración Vertex AI ──────────────────────────────────────────────────
PROJECT_ID          = "anemona-2130e"
LOCATION            = "us-central1"
RESOURCE_ID         = "2255393567440633856"
AGENT_RESOURCE_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{RESOURCE_ID}"

vertexai.init(project=PROJECT_ID, location=LOCATION)
remote_app = agent_engines.get(AGENT_RESOURCE_NAME)  # una sola instancia global

# ── Router ───────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/diagramaaqr", tags=["diagramaaqr"])

sessions: dict = {}


# ── Modelos ──────────────────────────────────────────────────────────────────
class DocumentoPayload(BaseModel):
    data: dict


class Formulario(BaseModel):
    solicitante:              Optional[str]       = None
    dga:                      Optional[str]       = None
    info_contacto:            Optional[str]       = None
    patrocinador:             Optional[str]       = None
    nombre_socio_negocio:     Optional[str]       = None
    cr:                       Optional[str]       = None
    nombre_iniciativa:        Optional[str]       = None
    departamentos_impactados: Optional[List[str]] = None
    tipo_iniciativa:          Optional[str]       = None
    usuario_nombre:           Optional[str]       = None
    usuario_id:               Optional[str]       = None
    session_id:               Optional[str]       = None


class NuevoProyectoPayload(BaseModel):
    formulario: Formulario
    plantilla:  Dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/subir")
async def subir_documento(payload: DocumentoPayload):
    try:
        _db.collection(COLLECTION).document().set(payload.data)
        return {"ok": True, "mensaje": "Documento guardado"}
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


@router.get("/arquitectura")
async def obtener_arquitectura(doc_id: str):
    try:
        doc = _db.collection(COLLECTION).document(doc_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        data = doc.to_dict() or {}
        return {
            "ok":    True,
            "doc_id": doc_id,
            "nodes": data.get("NODOS", []),
            "edges": data.get("ARISTAS", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Tarea background ─────────────────────────────────────────────────────────
async def _ejecutar_agente(session_id: str):
    """Corre después de responder al cliente — nunca bloquea el HTTP response."""
    try:
        stream = remote_app.async_stream_query(
            session_id=session_id,
            message="genera el diagrama de arquitectura",
        )
        if inspect.isasyncgen(stream):
            async for _ in stream:
                pass
        else:
            await stream
        print(f"[arq-bg] ✅ Agente terminó: {session_id}")
    except Exception as e:
        traceback.print_exc()
        print(f"[arq-bg] ❌ Error en sesión {session_id}: {e}")


@router.post("/generar-arquitectura")
async def generar_arquitectura(
    session_id: str,
    background_tasks: BackgroundTasks,   # ✅ inyectado como dependencia
):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido")

    # Encola la tarea y responde de inmediato (~ms)
    # El agente escribe NODOS/ARISTAS en Firestore en background
    # El polling del frontend lo detecta en el siguiente ciclo de 5s
    background_tasks.add_task(_ejecutar_agente, session_id)

    return {"ok": True, "mensaje": "Generando arquitectura en segundo plano…"}


@router.post("/new_project")
async def new_project(payload: NuevoProyectoPayload, db: Session = Depends(get_db)):
    try:
        documento  = payload.plantilla.copy()
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

        # Firestore
        async def crear_firestore():
            _, doc_ref = _db.collection(COLLECTION).add(documento)
            return doc_ref.id

        # Vertex AI session
        async def crear_vertex_session(id_firestore_document: str):
            remote_session = await remote_app.async_create_session(
                user_id=formulario.usuario_id,
                state={"doc_id": id_firestore_document},
            )
            return remote_session["id"]

        firestore_id = await crear_firestore()
        session_id   = await crear_vertex_session(firestore_id)

        sessions[session_id] = {
            "user_id":    formulario.usuario_id,
            "session_id": session_id,
            "project_id": firestore_id,
        }

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
            "user_id":    formulario.usuario_id,
            "mensaje":    f"Documento '{firestore_id}' y sesión '{session_id}' creados",
        }

    except Exception as e:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=500, detail=str(e))