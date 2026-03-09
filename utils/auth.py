from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "mi-clave-secreta-123"
ALGORITHM = "HS256"
MINUTOS_EXPIRACION = 30

pwd_context = CryptContext(schemes=["bcrypt"])

def hashear_password(password: str) -> str:
    return pwd_context.hash(password)

def verificar_password(password_plano: str, password_hasheado: str) -> bool:
    return pwd_context.verify(password_plano, password_hasheado)

def crear_token(email: str) -> str:
    datos = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(minutes=MINUTOS_EXPIRACION)
    }
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)

def leer_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None