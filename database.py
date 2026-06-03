from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# cargar variables del .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# conexión a PostgreSQL en Aiven
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

engine = create_engine(
    DATABASE_URL,

    # IMPORTANTE para Aiven con límite de 20 conexiones
    pool_size=1,
    max_overflow=0,

    # Evita que requests se queden esperando demasiado una conexión
    pool_timeout=10,

    # Recicla conexiones viejas
    pool_recycle=300,

    # Verifica que la conexión siga viva antes de usarla
    pool_pre_ping=True,

    # Reutiliza la conexión más reciente
    pool_use_lifo=True,

    connect_args={
        "connect_timeout": 10,
        "application_name": "anemona-backend",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()