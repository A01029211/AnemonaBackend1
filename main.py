from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine
from routes.login_route import router as login_router
from routes.agent_call import router as agent_call
from routes.datos_proyecto_route import router as datos_proyecto_route
from routes.firestore_srs import router as firestore_router
from routes.modificacion_widgets import router as widgets_router
from routes.email_route import router as email_router
from routes.arquitectura import router as arquitectura
from dotenv import load_dotenv
import os
#
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://10.22.151.18:3000", 
                   "sa://service-637376850775@gcp-sa-aiplatform-re.iam.gserviceaccount.com", "https://anemona-backend-fireabse--anemona-2130e.us-east4.hosted.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login_router)
app.include_router(datos_proyecto_route)
app.include_router(firestore_router)
app.include_router(widgets_router)
app.include_router(arquitectura)
app.include_router(
    agent_call,
    prefix="/agent",
    tags=["VertexAI"]
)
app.include_router(
    email_router,
    prefix="/email",
    tags=["Email"]
)

@app.get("/test-db")
def test_db():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT NOW();"))
            fecha = result.scalar()
        return {"conexion": "exitosa", "hora_db": str(fecha)}
    except Exception as e:
        return {"error": str(e)}

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))