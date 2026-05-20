

import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import SessionChat, Usuario, Proyecto
from routes.firestore_srs import EliminarColaboradorPayload


router = APIRouter(prefix="/colaboracion", tags=["colaboracion"])


@router.post("/agregar_colaborador")
async def new_colab(correo: str, folio: int, db: Session = Depends(get_db)):
    try:
        def buscar_y_crear():
            # Buscar sesión owner por folio
            session_owner = db.query(SessionChat).filter(SessionChat.folio == folio).first()
            print(f"[DEBUG] Folio recibido: {folio}")
            if session_owner:
                print(f"[DEBUG] Session owner: {session_owner.__dict__}")
            else:
                print(f"[DEBUG] No se encontró ninguna session con folio={folio}")

            # Buscar usuario por correo
            usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
            print(f"[DEBUG] Correo recibido: {correo}")
            if usuario:
                print(f"[DEBUG] Usuario completo: {usuario.__dict__}")
            else:
                print(f"[DEBUG] No se encontró ningún usuario con correo={correo}")

            if not session_owner or not usuario:
                return session_owner, usuario, None, False

            # Verificar si ya existe sesión para este usuario en este folio
            session_existente = db.query(SessionChat).filter(
                SessionChat.folio == folio,
                SessionChat.idusuario == usuario.idusuario
            ).first()

            if session_existente:
                print(f"[DEBUG] Ya existe sesión para usuario {usuario.idusuario} en folio {folio}")
                return session_owner, usuario, session_existente, True

            # Copiar la sesión owner cambiando solo idusuario y permiso
            nueva_session = SessionChat(
                session_id=session_owner.session_id,
                folio=session_owner.folio,
                idusuario=usuario.idusuario,
                fecha_inicio=datetime.now(),
                fecha_conclusion=None,
                id_firestore_document=session_owner.id_firestore_document,
                permiso="COLAB",
                id_owner=session_owner.id_owner,
            )
            db.add(nueva_session)
            db.commit()
            db.refresh(nueva_session)
            print(f"[DEBUG] Nueva session creada: {nueva_session.__dict__}")
            return session_owner, usuario, nueva_session, False

        session_owner, usuario, result_session, ya_existia = await asyncio.to_thread(buscar_y_crear)

        if not session_owner:
            raise HTTPException(status_code=404, detail=f"No se encontró sesión con folio {folio}")
        if not usuario:
            raise HTTPException(status_code=404, detail=f"No se encontró usuario con correo {correo}")

        return {
            "ok": True,
            "ya_existia": ya_existia,
            "mensaje": "El colaborador ya tenía una sesión activa" if ya_existia else "Sesión de colaborador creada correctamente",
            
        }

    except HTTPException:
        raise
    except Exception as e:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/eliminar-colaborador")
async def eliminar_colaborador(
    payload: EliminarColaboradorPayload,
    db: Session = Depends(get_db)
):
    try:
        registro = db.query(SessionChat).filter(
            SessionChat.id_session == payload.id_session,
            SessionChat.session_id == payload.session_id,
            SessionChat.idusuario == payload.id_usuario
        ).first()

        if not registro:
            raise HTTPException(
                status_code=404,
                detail="No se encontró un registro con ese id_session, session_id e id_usuario"
            )

        db.delete(registro)
        db.commit()

        return {
            "ok": True,
            "mensaje": "Colaborador eliminado correctamente",
            "eliminado": {
                "id_session": payload.id_session,
                "session_id": payload.session_id,
                "id_usuario": payload.id_usuario
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar colaborador: {str(e)}")
    
    
# Obtener todos los colaboradores de un proyecto
@router.get("/{folio}/obtener-colaboradores")
def obtener_colaboradores(folio: int, db: Session = Depends(get_db)):
    sesiones = db.query(SessionChat).filter(SessionChat.folio == folio).all()

    if not sesiones:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado o sin sesiones")

    idusuarios = [s.idusuario for s in sesiones]
    usuarios = db.query(Usuario).filter(Usuario.idusuario.in_(idusuarios)).all()
    usuarios_map = {u.idusuario: u for u in usuarios}

    def formatear_usuario(s):
        u = usuarios_map.get(s.idusuario)
        return {
            "idusuario": s.idusuario,
            "nombre": f"{u.nombre} {u.apellidopaterno}" if u else None,
            "correo": u.correo if u else None,
            "session_id": s.session_id,
        }

    owner = next((s for s in sesiones if s.permiso == "OWNER"), None)
    colaboradores = [s for s in sesiones if s.permiso == "COLAB"]

    return {
        "folio": folio,
        "owner": formatear_usuario(owner) if owner else None,
        "colaboradores": [formatear_usuario(s) for s in colaboradores],
        "total_colaboradores": len(colaboradores)
    }
    
# Endpoint para cambiar el nombre del proyecto
class RenombrarProyectoPayload(BaseModel):
    nombreproyecto: str

@router.patch("/{folio}/renombrar-proyecto")
def renombrar_proyecto(
    folio: int,
    payload: RenombrarProyectoPayload,
    db: Session = Depends(get_db)
):
    proyecto = db.query(Proyecto).filter(Proyecto.folio == folio).first()

    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    nombre_anterior = proyecto.nombreproyecto
    proyecto.nombreproyecto = payload.nombreproyecto.strip()
    proyecto.fechaactualizacion = datetime.now()

    try:
        db.commit()
        db.refresh(proyecto)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo renombrar el proyecto: {str(e)}"
        )

    return {
        "ok": True,
        "folio": proyecto.folio,
        "nombre_anterior": nombre_anterior,
        "nombreproyecto": proyecto.nombreproyecto,
        "fechaactualizacion": proyecto.fechaactualizacion.isoformat()
    }
    
    
    
@router.get("/session/{session_id}/permiso/{idusuario}")
def obtener_permiso_sesion(session_id: str, idusuario: str, db: Session = Depends(get_db)):
    sesion = db.query(SessionChat).filter(
        SessionChat.session_id == session_id,
        SessionChat.idusuario == idusuario
    ).first()

    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada para este usuario")

    return {
        "session_id": session_id,
        "idusuario": idusuario,
        "permiso": sesion.permiso,  # "OWNER" o "COLAB"
        "id_owner": sesion.id_owner
    }