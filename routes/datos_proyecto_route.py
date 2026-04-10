from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Proyecto
from models import Mensaje
from models import SessionChat
from models import Usuario
from models import empleados_proyecto
from models import Departamento


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

    proyectos = (
        db.query(Proyecto)
        .filter(Proyecto.folio.in_(
            db.query(empleados_proyecto.folio)
            .filter(empleados_proyecto.idusuario == idusuario)
        ))
        .order_by(Proyecto.fechacreacion.desc())
        .all()
    )

    return [
        {
            "folio": p.folio,
            "nombreproyecto": p.nombreproyecto,
            "fechacreacion": p.fechacreacion.isoformat() if p.fechacreacion else None,
            "departamento": nombre_depto,
        }
        for p in proyectos
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