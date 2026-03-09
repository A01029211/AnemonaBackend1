from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from utils.auth import hashear_password, verificar_password, crear_token, leer_token
router = APIRouter()  # ← esto cambia

usuarios_db = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class DatosRegistro(BaseModel):
    email: str
    password: str

@router.post("/register")  # ← app. cambia a router.
def registrar_usuario(datos: DatosRegistro):
    if datos.email in usuarios_db:
        raise HTTPException(status_code=400, detail="Este email ya está registrado")
    usuarios_db[datos.email] = hashear_password(datos.password)
    return {"mensaje": "Usuario creado exitosamente"}

@router.post("/login")  # ← app. cambia a router.
def login(form: OAuth2PasswordRequestForm = Depends()):
    password_guardado = usuarios_db.get(form.username)
    if not password_guardado or not verificar_password(form.password, password_guardado):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    token = crear_token(form.username)
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")  # ← app. cambia a router.
def obtener_mi_info(token: str = Depends(oauth2_scheme)):
    email = leer_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return {"email": email}