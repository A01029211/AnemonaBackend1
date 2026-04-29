from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import vertexai
from vertexai import agent_engines
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json
# Configuration
PROJECT_ID = "anemona-2130e"
LOCATION = "us-central1"
RESOURCE_ID = "3797876439815028736"
               
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
        
        remote_app = agent_engines.get(AGENT_RESOURCE_NAME)
        
        # RECIBE LA RESPUESTA
        final_text = ""
        async for event in remote_app.async_stream_query(
            user_id=request.user_id,
            session_id=request.session_id,
            message=request.message,
        ):
            print(event)
    
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
@router.post("/query/stream")
async def query_agent_stream(request: QueryRequest):

    async def event_generator():
        try:
            remote_app = agent_engines.get(AGENT_RESOURCE_NAME)

            async for event in remote_app.async_stream_query(
                user_id=request.user_id,
                session_id=request.session_id,
                message=request.message,
            ):
                # ── DEBUG ──────────────────────────────────────────────────
                print("=" * 60)
                print("RAW:", json.dumps(event, indent=2, default=str))
                content = event.get("content", {})
                role    = content.get("role", "")
                parts   = content.get("parts", [])
                for part in parts:
                    print(f"  PART keys: {list(part.keys())} | role: {role}")
                print("=" * 60)
                # ───────────────────────────────────────────────────────────

                for part in parts:
                    if role == "model" and "text" in part:
                        payload = {"type": "text", "data": part["text"]}
                        print(f"📤 YIELD → {payload['type']}")
                        yield f"data: {json.dumps(payload)}\n\n"

                    elif "function_call" in part:
                        fn = part["function_call"]
                        payload = {"type": "tool_call", "tool": fn.get("name")}
                        print(f"📤 YIELD → {payload}")
                        yield f"data: {json.dumps(payload)}\n\n"

                    elif "function_response" in part:
                        fn = part["function_response"]
                        payload = {"type": "tool_result", "tool": fn.get("name")}
                        print(f"📤 YIELD → {payload}")
                        yield f"data: {json.dumps(payload)}\n\n"

                    else:
                        print(f"  ⚠️ PART SIN HANDLER: {part}")

            print("🏁 DONE")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            print(f"❌ ERROR: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )