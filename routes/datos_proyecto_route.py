from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Departamento, Proyecto, Mensaje, SessionChat, Usuario, empleados_proyecto
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import desc, func


from routes.firestore_srs import Formulario

router = APIRouter()

# obtener proyectos
@router.get("/proyectos")
def obtener_proyectos(db: Session = Depends(get_db)):
    proyectos = db.query(Proyecto).all()
    return proyectos

@router.get("/usuarios/{idusuario}/proyectos")
def obtener_mis_proyectos(idusuario: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    depto = (
        db.query(Departamento)
        .filter(Departamento.iddepartamento == usuario.iddepartamento)
        .first()
    )
    nombre_depto = depto.nombre if depto else "Sin área"

    resultados = (
        db.query(Proyecto, SessionChat)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(SessionChat.idusuario == idusuario)
        .order_by(Proyecto.fechacreacion.desc())
        .all()
    )

    return [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "departamento": nombre_depto,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
        }
        for proyecto, session in resultados
    ]

# obtener mensajes
@router.get("/mensajes")
def obtener_mensajes(db: Session = Depends(get_db)):
    mensajes = db.query(Mensaje).all()
    return mensajes

# obtener mensajes de un proyecto específico
@router.get("/proyectos/{folio}/mensajes")
def obtener_mensajes_proyecto(folio: int, db: Session = Depends(get_db)):
    mensajes = db.query(Mensaje).filter(Mensaje.folio == folio).all()
    return mensajes

# obtener mensajes de una sesión
@router.get("/chat/{id_session}")
def obtener_chat(id_session: int, db: Session = Depends(get_db)):
    
    mensajes = db.query(Mensaje).filter(
        Mensaje.id_session == id_session
    ).order_by(Mensaje.fecha_creacion).all()

    return mensajes

# ver usuarios en una sesión
@router.get("/session/{session_id}/usuarios")
def usuarios_sesion(session_id: str, db: Session = Depends(get_db)):

    usuarios = db.query(SessionChat).filter(
        SessionChat.session_id == session_id
    ).all()

    return usuarios

# ver los departamentos existentes
@router.get("/departamentos")
def obtener_departamentos(db: Session = Depends(get_db)):
    departamentos = db.query(Departamento).all()
    return departamentos


"""
#Obtener los proyectos más recientes, (filtrando por tablla empleados_proyecto)
@router.get("/usuarios/{idusuario}/proyectos_recientes")
def obtener_proyectos_recientes(idusuario: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    resultados = (
        db.query(Proyecto, SessionChat)
        .join(empleados_proyecto, Proyecto.folio == empleados_proyecto.folio)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(empleados_proyecto.idusuario == idusuario)
        .order_by(
            desc(func.coalesce(Proyecto.fechaactualizacion, Proyecto.fechacreacion))
        )
        .limit(4)
        .all()
    )

    return [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechaactualizacion": proyecto.fechaactualizacion.isoformat() if proyecto.fechaactualizacion else None,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
        }
        for proyecto, session in resultados
    ]

"""

#Obtener los proyectos más recientes, por el session_chat
@router.get("/usuarios/{idusuario}/proyectos_recientes")
def obtener_proyectos_recientes(idusuario: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    resultados = (
        db.query(Proyecto, SessionChat)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(SessionChat.idusuario == idusuario)
        .order_by(desc(func.coalesce(Proyecto.fechaactualizacion, Proyecto.fechacreacion)))
        .limit(4)
        .all()
    )

    return [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechaactualizacion": proyecto.fechaactualizacion.isoformat() if proyecto.fechaactualizacion else None,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
        }
        for proyecto, session in resultados
    ]

