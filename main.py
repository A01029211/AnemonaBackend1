from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine
from routes.login_route import router as login_router
from routes.agent_call import router as agent_call
from routes.datos_proyecto_route import router as datos_proyecto_route
from dotenv import load_dotenv
import os
#IMPORTANTE PARA VARIABLES DE ENTORNO
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login_router)  # ← así registras las rutas
app.include_router(datos_proyecto_route)
app.include_router(
    agent_call,    
    prefix="/agent",   # <-- prefijo que quieres para todas las rutas del router
    tags=["VertexAI"])  # ruta agent_call (dario)

@app.get("/test-db")
def test_db():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW();"))
            fecha = result.scalar()
        return {"conexion": "exitosa", "hora_db": str(fecha)}
    except Exception as e:
        return {"error": str(e)}