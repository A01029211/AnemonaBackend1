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

#@router.post("/register")  # ← app. cambia a router.
#def registrar_usuario(datos: DatosRegistro):
#    if datos.email in usuarios_db:
#        raise HTTPException(status_code=400, detail="Este email ya está registrado")
#    usuarios_db[datos.email] = hashear_password(datos.password)
#    return {"mensaje": "Usuario creado exitosamente"}

@router.post("/login")  # ← app. cambia a router.
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == form.username).first()
    if not usuario or not verificar_password(form.password, usuario.password):
        raise HTTPException(status_code=401, detail='Correo o contraseña incorrectos')
    token = crear_token(form.username)
    return{"access_token": token, "token_type": "bearer"}

@router.get("/me")  # ← app. cambia a router.
def obtener_mi_info(token: str = Depends(oauth2_scheme)):
    correo = leer_token(token)
    if not correo:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return {"correo": correo}