from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from utils.auth import hashear_password, verificar_password, crear_token, leer_token
from database import get_db
from models import Usuario


router = APIRouter()  # ← esto cambia
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class DatosRegistro(BaseModel):
    email: str
    password: str

@router.post("/login")  # ← app. cambia a router.
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == form.username).first()
    if not usuario or not verificar_password(form.password, usuario.password):
        raise HTTPException(status_code=401, detail='Correo o contraseña incorrectos')
    
    usuario.ultimoacceso = datetime.utcnow()
    db.commit()
    
    
    token = crear_token(usuario.correo, usuario.idusuario)

    return{
        "access_token": token, 
        "token_type": "bearer",
        "idusuario": usuario.idusuario,
        "nombre": usuario.nombre,
        "apellidopaterno": usuario.apellidopaterno,
        "apellidomaterno": usuario.apellidomaterno,
        "correo": usuario.correo,
        "ultimoacceso": usuario.ultimoacceso,
        "activo": usuario.activo,
        "iddepartamento": usuario.iddepartamento,
        "idrol": usuario.idrol
        }

@router.get("/me")
def obtener_mi_info(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    datos = leer_token(token)
    if not datos:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    # Busca el usuario fresco de la BD con todos sus datos
    usuario = db.query(Usuario).filter(Usuario.correo == datos["correo"]).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "idusuario":          usuario.idusuario,
        "nombre":             usuario.nombre,
        "apellidopaterno":    usuario.apellidopaterno,
        "apellidomaterno":    usuario.apellidomaterno,
        "correo":             usuario.correo,
        "ultimoacceso":       usuario.ultimoacceso,
        "activo":             usuario.activo,
        "iddepartamento":     usuario.iddepartamento,
        "idrol":              usuario.idrol
    }