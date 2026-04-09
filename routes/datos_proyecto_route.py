from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Departamento, Proyecto, Mensaje, SessionChat, Usuario
from pydantic import BaseModel
from typing import Optional, List

from routes.firestore_srs import Formulario

router = APIRouter()

# obtener proyectos
@router.get("/proyectos")
def obtener_proyectos(db: Session = Depends(get_db)):
    proyectos = db.query(Proyecto).all()
    return proyectos

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