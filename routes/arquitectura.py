import asyncio
import inspect
import logging
import json
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

logger = logging.getLogger(__name__)

# ── Configuración Firestore ──────────────────────────────────────────────────
FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT")
COLLECTION = os.getenv("FIRESTORE_COLLECTION", "srs_anemona")
DOC_ID = "DDYWBQOZG2WYrHrs4a3e"


##QUITAR PARA REMOTO, CREDIENCIALES ARRIBA SIRVE LOCAL, ABAJO REMOTO
#FIRESTORE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_FIRESTORE")
#credentials = service_account.Credentials.from_service_account_file(
#    FIRESTORE_CREDENTIALS_PATH
#)
FIRESTORE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS")
credentials_info = json.loads(FIRESTORE_CREDENTIALS_JSON)
credentials = service_account.Credentials.from_service_account_info(credentials_info)
##QUITAR PARA REMOTO

_db = firestore.Client(
    project=FIRESTORE_PROJECT,
    credentials=credentials,
)

# ── Configuración Vertex AI ──────────────────────────────────────────────────
PROJECT_ID = "anemona-2130e"
LOCATION = "us-central1"
RESOURCE_ID = "8795913252056858624"
AGENT_RESOURCE_NAME = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{RESOURCE_ID}"
)

vertexai.init(project=PROJECT_ID, location=LOCATION)
remote_app = agent_engines.get(AGENT_RESOURCE_NAME)

# ── Router ───────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/diagramaaqr", tags=["diagramaaqr"])

sessions: dict = {}


# ── Modelos ──────────────────────────────────────────────────────────────────
class DocumentoPayload(BaseModel):
    data: dict


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


# ── Helpers internos ─────────────────────────────────────────────────────────
async def _drain_stream(stream) -> str:
    """
    Consume el stream del agente de forma segura sin importar si es
    async generator, coroutine o iterable síncrono.
    Retorna el texto acumulado de todos los chunks.
    """
    chunks: list[str] = []

    try:
        if inspect.isasyncgen(stream):
            async for chunk in stream:
                text = _extract_text(chunk)
                if text:
                    chunks.append(text)
                    logger.debug(f"[stream] chunk async: {text[:120]}")

        elif asyncio.iscoroutine(stream):
            result = await stream
            text = _extract_text(result)
            if text:
                chunks.append(text)
            logger.debug(f"[stream] result coroutine: {text[:120] if text else '(vacío)'}")

        else:
            # Iterable síncrono — corre en thread para no bloquear el event loop
            def _consume():
                parts = []
                for chunk in stream:
                    t = _extract_text(chunk)
                    if t:
                        parts.append(t)
                return parts

            chunks = await asyncio.to_thread(_consume)
            logger.debug(f"[stream] result síncrono: {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"[stream] Error al consumir stream: {e}")
        raise

    return "\n".join(chunks)


def _extract_text(chunk: Any) -> str:
    """Extrae texto de un chunk del agente en cualquier formato posible."""
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        # Formato Vertex AI agent streaming
        for key in ("text", "content", "message", "output"):
            if key in chunk and isinstance(chunk[key], str):
                return chunk[key]
        # Nested: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
        candidates = chunk.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts and isinstance(parts[0].get("text"), str):
                return parts[0]["text"]
    return str(chunk) if chunk else ""


# ── Tarea background ─────────────────────────────────────────────────────────
async def _ejecutar_agente(doc_id: str) -> None:
    logger.info(f"[arq-bg] Iniciando — doc={doc_id}")

    try:
        # 1. Sesión efímera
        remote_session = await remote_app.async_create_session(
            user_id="arquitectura-agent",
            state={"doc_id": doc_id},
        )
        ephemeral_session_id = remote_session["id"]
        logger.info(f"[arq-bg] Sesión creada — {ephemeral_session_id}")

        # 2. stream_query síncrono en thread
        def _run():
            chunks = []
            for chunk in remote_app.stream_query(
                message=f"doc_id={doc_id}",
                session_id=ephemeral_session_id,
                user_id="arquitectura-agent"
            ):
                chunks.append(str(chunk))
            return "\n".join(chunks)

        response = await asyncio.to_thread(_run)
        logger.info(f"[arq-bg] Respuesta: {response[:200]!r}")

        # 3. Borrar sesión efímera
        await remote_app.async_delete_session(session_id=ephemeral_session_id, user_id="arquitectura-agent")
        logger.info(f"[arq-bg] Sesión eliminada — {ephemeral_session_id}")

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[arq-bg] Error fatal — doc={doc_id}: {e}")
    

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
            "ok": True,
            "doc_id": doc_id,
            "nodes": data.get("NODOS", []),
            "edges": data.get("ARISTAS", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generar-arquitectura")
async def generar_arquitectura(
    doc_id: str,
    background_tasks: BackgroundTasks,
):
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requerido")

    logger.info(f"[arq] Encolando agente — doc={doc_id}")
    background_tasks.add_task(_ejecutar_agente, doc_id)

    return {"ok": True, "mensaje": "Generando arquitectura en segundo plano…"}


@router.post("/new_project")
async def new_project(payload: NuevoProyectoPayload, db: Session = Depends(get_db)):
    try:
        documento = payload.plantilla.copy()
        formulario = payload.formulario

        mapeo = {
            "solicitante": "SOLICITANTE",
            "dga": "DGA",
            "info_contacto": "INFO_CONTACTO",
            "patrocinador": "PATROCINADOR",
            "nombre_socio_negocio": "SOCIO",
            "cr": "CR",
            "nombre_iniciativa": "NOMBRE_INICIATIVA",
            "tipo_iniciativa": "TIPO_INICIATIVA",
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

        async def crear_firestore() -> str:
            _, doc_ref = _db.collection(COLLECTION).add(documento)
            return doc_ref.id

        async def crear_vertex_session(id_firestore_document: str) -> str:
            remote_session = await remote_app.async_create_session(
                user_id=formulario.usuario_id,
                state={"doc_id": id_firestore_document},
            )
            return remote_session["id"]

        firestore_id = await crear_firestore()
        session_id = await crear_vertex_session(firestore_id)

        sessions[session_id] = {
            "user_id": formulario.usuario_id,
            "session_id": session_id,
            "project_id": firestore_id,
        }

        def insertar_en_sql() -> int:
            nuevo_proyecto = Proyecto(
                fechacreacion=datetime.now(),
                fechaactualizacion=datetime.now(),
                nombreproyecto=formulario.nombre_iniciativa,
                tipoiniciativa=formulario.tipo_iniciativa,
                cr=int(formulario.cr) if formulario.cr and formulario.cr.isdigit() else None,
                patrocinador=formulario.patrocinador,
                socionegocio=formulario.nombre_socio_negocio,
                descripciongeneral=formulario.info_contacto,
                participacionareas=(
                    ", ".join(formulario.departamentos_impactados)
                    if formulario.departamentos_impactados
                    else None
                ),
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
            "ok": True,
            "project_id": firestore_id,
            "session_id": session_id,
            "user_id": formulario.usuario_id,
            "folio": folio,
            "mensaje": f"Documento '{firestore_id}' y sesión '{session_id}' creados",
        }

    except Exception as e:
        await asyncio.to_thread(db.rollback)
        logger.exception("[new_project] Error creando proyecto")
        raise HTTPException(status_code=500, detail=str(e))