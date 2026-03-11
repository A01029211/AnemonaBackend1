from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import vertexai
from vertexai import agent_engines
from fastapi import APIRouter, HTTPException, Depends

# Configuration
PROJECT_ID = "anemona-2130e"
LOCATION = "us-central1"
RESOURCE_ID = "4527541493065318400"
               
AGENT_RESOURCE_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{RESOURCE_ID}"

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Initialize FastAPI app
router = APIRouter()

# Store sessions in memory (for production, use a database)
sessions = {}


# Request/Response Models
class CreateSessionRequest(BaseModel):
    user_id: str


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str


class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    message: str


class QueryResponse(BaseModel):
    content: str
    session_id: str
    user_id: str


# Endpoints
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """CREAR NUEVA SESSIÓN DEL CHAT, CONTEXTO SE GUARDA"""
    try:
        remote_app = agent_engines.get(AGENT_RESOURCE_NAME)
        remote_session = await remote_app.async_create_session(user_id=request.user_id)

        # TODO: GUARDAR SESIÓN EN BASE DE DATOS, ASOCIADA AL USUARIO
        sessions[remote_session['id']] = {
            "user_id": request.user_id,
            "session_id": remote_session['id']
        }
        
        return CreateSessionResponse(
            session_id=remote_session['id'],
            user_id=request.user_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """ENPOINT PARA ENVIAR MENSAJES AL AGENTE, SE DEBE DE MANDAR LA SESIÓN PARA HACER REFERENCIA A LA MISMA"""
    try:
        # Verify session exists
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        remote_app = agent_engines.get(AGENT_RESOURCE_NAME)
        
        # RECIBE LA RESPUESTA
        final_text = ""
        async for event in remote_app.async_stream_query(
            user_id=request.user_id,
            session_id=request.session_id,
            message=request.message,
        ):
            content = event.get("content")
            if content and content.get("role") == "model":
                for part in content.get("parts", []):
                    if "text" in part:
                        final_text += part["text"]
        
        return QueryResponse(
            content=final_text,
            session_id=request.session_id,
            user_id=request.user_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

