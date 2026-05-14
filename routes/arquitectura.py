import asyncio
import inspect
import logging
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
FIRESTORE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_FIRESTORE")

credentials = service_account.Credentials.from_service_account_file(
    FIRESTORE_CREDENTIALS_PATH
)
_db = firestore.Client(
    project=FIRESTORE_PROJECT,
    credentials=credentials,
)

# ── Configuración Vertex AI ──────────────────────────────────────────────────
PROJECT_ID = "anemona-2130e"
LOCATION = "us-central1"
RESOURCE_ID = "4638079245296336896"
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
async def _ejecutar_agente(session_id: str, doc_id: str) -> None:
    """
    Ejecuta el agente de arquitectura en background.
    - Actualiza el state de la sesión con el doc_id antes de lanzar el query.
    - Hace skip silencioso si el agente falla o retorna "skipped".
    - Loguea errores sin propagar excepciones (es background task).
    """
    logger.info(f"[arq-bg] Iniciando — session={session_id} | doc={doc_id}")

    try:
        # ── 1. Garantizar que el state tenga el doc_id actualizado ──────────
        # Esto es crítico: el agente lee doc_id del state, no del mensaje.
        try:
            await remote_app.async_update_session(
                session_id=session_id,
                state={"doc_id": doc_id},
            )
            logger.info(f"[arq-bg] State actualizado con doc_id={doc_id}")
        except Exception as e:
            # async_update_session puede no existir en todas las versiones del SDK.
            # Si falla, intentamos igual — el state pudo haberse seteado al crear la sesión.
            logger.warning(
                f"[arq-bg] No se pudo actualizar state explícitamente: {e}. "
                "Continuando — el doc_id debe estar en el state de creación."
            )

        # ── 2. Lanzar el agente ──────────────────────────────────────────────
        # El mensaje es solo un trigger; el doc_id viene del session state.
        stream = remote_app.async_stream_query(
            session_id=session_id,
            message="genera la arquitectura",
        )

        logger.info(f"[arq-bg] Stream tipo: {type(stream).__name__}")

        result_text = await _drain_stream(stream)

        logger.info(f"[arq-bg] Respuesta del agente: {result_text[:200]!r}")

        if "skipped" in result_text.lower():
            logger.info(f"[arq-bg] El agente hizo skip — doc={doc_id}")
        else:
            logger.info(f"[arq-bg] Agente terminó OK — doc={doc_id}")

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[arq-bg] Error fatal — session={session_id} doc={doc_id}: {e}")
        # No re-lanzamos: es background task, no hay quién maneje la excepción.


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
    session_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido")
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id requerido")

    logger.info(f"[arq] Encolando agente — session={session_id} | doc={doc_id}")
    background_tasks.add_task(_ejecutar_agente, session_id, doc_id)

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