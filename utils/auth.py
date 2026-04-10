from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "mi-clave-secreta-123"
ALGORITHM = "HS256"
MINUTOS_EXPIRACION = 30

pwd_context = CryptContext(schemes=["bcrypt"])

def hashear_password(password: str) -> str:
    return pwd_context.hash(password)


# La base de datos tiene que estan hasheada 
def verificar_password(password_plano: str, password_guardado: str) -> bool:
    if password_guardado.startswith("$2b$") or password_guardado.startswith("$2a$"):
        return pwd_context.verify(password_plano, password_guardado)
    else:
        return password_plano == password_guardado

def crear_token(correo: str, idusuario: str) -> str:
    datos = {
        "sub": correo,
        "idusuario": idusuario,
        "exp": datetime.utcnow() + timedelta(minutes=MINUTOS_EXPIRACION)
    }
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)

def leer_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "correo": payload.get("sub"),
            "idusuario": payload.get("idusuario")
        }
    except JWTError:
        return None