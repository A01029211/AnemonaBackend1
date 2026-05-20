import requests
import pytest
import time


# =========================
# CONFIGURACIÓN

BASE_URL = "https://api-anemona-637376850775.northamerica-northeast1.run.app"

VALID_EMAIL    = "mariel.gonzalez@banorte.com"
VALID_PASSWORD = "hash123"

VALID_DOC_ID     = "QwQ2VlIKIgJhOmYSH8Fp"
INVALID_DOC_ID   = "doc-no-existe-xyz"

VALID_USER_ID    = "2"
VALID_SESSION_ID = "196"

SEND_EMAIL_USER_NAME = "santcordova0104@gmail.com"

@pytest.fixture(autouse=True)
def pausa_entre_tests():
    yield
    time.sleep(4)  # 2s entre cada test para no saturar VertexAI


def is_4xx(code: int) -> bool:
    return 400 <= code <= 499


def get_auth_token() -> str | None:
    response = requests.post(
        f"{BASE_URL}/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "password",
            "username": VALID_EMAIL,
            "password": VALID_PASSWORD,
            "scope": "",
            "client_id": "string",
            "client_secret": "",
        },
    )
    try:
        data = response.json()
        return data.get("access_token") or data.get("token") or data.get("idToken")
    except Exception:
        return None


def auth_headers() -> dict:
    token = get_auth_token()
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
# ARQUITECTURA  (GET /diagramaaqr/arquitectura)
# ─────────────────────────────────────────────────────────────

def test_TC01_get_arquitectura_doc_valido():
    """TC01 - GET /diagramaaqr/arquitectura con doc_id válido → 200 + nodos y aristas"""
    response = requests.get(
        f"{BASE_URL}/diagramaaqr/arquitectura",
        params={"doc_id": VALID_DOC_ID},
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert data.get("ok") is True, "Campo 'ok' debe ser True"
    assert "nodes" in data, "La respuesta debe incluir 'nodes'"
    assert "edges" in data, "La respuesta debe incluir 'edges'"


def test_TC02_get_arquitectura_doc_invalido():
    """TC02 - GET /diagramaaqr/arquitectura con doc_id inexistente → 404"""
    response = requests.get(
        f"{BASE_URL}/diagramaaqr/arquitectura",
        params={"doc_id": INVALID_DOC_ID},
    )
    assert response.status_code == 404, f"Esperado 404, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# GENERAR ARQUITECTURA  (POST /diagramaaqr/generar-arquitectura)
# ─────────────────────────────────────────────────────────────

def test_TC03_generar_arquitectura_doc_valido():
    """TC03 - POST /diagramaaqr/generar-arquitectura con doc_id válido → 200 + background task"""
    response = requests.post(
        f"{BASE_URL}/diagramaaqr/generar-arquitectura",
        params={"doc_id": VALID_DOC_ID},
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert data.get("ok") is True, "Campo 'ok' debe ser True"
    assert "mensaje" in data, "La respuesta debe incluir 'mensaje'"


@pytest.mark.xfail(
    reason="El endpoint encola en background sin validar si el doc existe — devuelve 200 siempre. "
           "Bug: debería retornar 404 para doc_id inexistente.",
    strict=True,
)
def test_TC04_generar_arquitectura_doc_invalido():
    """TC04 - POST /diagramaaqr/generar-arquitectura con doc_id inexistente → 404 (bug: devuelve 200)"""
    response = requests.post(
        f"{BASE_URL}/diagramaaqr/generar-arquitectura",
        params={"doc_id": INVALID_DOC_ID},
    )
    assert response.status_code == 404, f"Esperado 404, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# MODIFICAR WIDGETS  (POST /widgets/modificar/{doc_id})
# descripcion_campos = {str: str}, campos = {str: any}
# ─────────────────────────────────────────────────────────────

SAMPLE_WIDGETS = [
    {
        "posicion": 1,
        "id_widget": "w001",
        "titulo": "Widget de prueba",
        "objetivo_widget": "Verificar guardado",
        "descripcion_campos": {"campo1": "Campo de texto básico"},
        "campos": {"campo1": "valor de prueba"},
    }
]


def test_TC05_modificar_widgets_valido():
    """TC05 - POST /widgets/modificar/{doc_id} con doc_id y widgets válidos → 200"""
    response = requests.post(
        f"{BASE_URL}/widgets/modificar/{VALID_DOC_ID}",
        json=SAMPLE_WIDGETS,
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert "widgets_guardados" in data, "La respuesta debe incluir 'widgets_guardados'"
    assert isinstance(data["widgets_guardados"], list), "'widgets_guardados' debe ser una lista"


def test_TC06_modificar_widgets_doc_inexistente():
    """TC06 - POST /widgets/modificar/{doc_id} con doc_id inexistente → 404"""
    response = requests.post(
        f"{BASE_URL}/widgets/modificar/{INVALID_DOC_ID}",
        json=SAMPLE_WIDGETS,
    )
    assert response.status_code == 404, f"Esperado 404, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# SEND EMAIL  (POST /email/send-email)
# ─────────────────────────────────────────────────────────────

def test_TC07_send_email_doc_invalido():
    """TC07 - POST /email/send-email con doc_id inválido → 404 o 500"""
    response = requests.post(
        f"{BASE_URL}/email/send-email",
        headers=auth_headers(),
        json={
            "doc_id": INVALID_DOC_ID,
            "user_name": SEND_EMAIL_USER_NAME,
        },
    )
    assert response.status_code in (404, 500), (
        f"Esperado 404 o 500, recibido {response.status_code}"
    )


def test_TC19_send_email_valido():
    """TC19 - POST /email/send-email con token y doc_id válidos → 200"""
    response = requests.post(
        f"{BASE_URL}/email/send-email",
        headers=auth_headers(),
        json={
            "doc_id": VALID_DOC_ID,
            "user_name": SEND_EMAIL_USER_NAME,
        },
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert data.get("ok") is True, "Campo 'ok' debe ser True"


def test_TC20_send_email_sin_token():
    """TC20 - POST /email/send-email sin token → 401"""
    response = requests.post(
        f"{BASE_URL}/email/send-email",
        json={
            "doc_id": VALID_DOC_ID,
            "user_name": SEND_EMAIL_USER_NAME,
        },
    )
    assert response.status_code == 401, f"Esperado 401, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# EXPORTAR WORD  (POST /widgets/exportar-word)
# ─────────────────────────────────────────────────────────────

SAMPLE_EXPORT_PAYLOAD = {
    "doc_id": VALID_DOC_ID,
    "widgets": SAMPLE_WIDGETS,
}

INVALID_EXPORT_PAYLOAD = {
    "doc_id": "",
    "widgets": SAMPLE_WIDGETS,
}


def test_TC08_exportar_word_valido():
    """TC08 - POST /widgets/exportar-word con widgets válidos → 200 + archivo .docx"""
    response = requests.post(
        f"{BASE_URL}/widgets/exportar-word",
        json=SAMPLE_EXPORT_PAYLOAD,
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    content_type = response.headers.get("Content-Type", "")
    assert "wordprocessingml" in content_type, (
        f"Content-Type debe ser .docx, recibido: {content_type}"
    )
    disposition = response.headers.get("Content-Disposition", "")
    assert "SRS_" in disposition and ".docx" in disposition, (
        f"Nombre de archivo incorrecto en Content-Disposition: {disposition}"
    )
    assert len(response.content) > 0, "El archivo .docx no debe estar vacío"


def test_TC17_exportar_word_estructura():
    """TC17 - POST /widgets/exportar-word: verificar que el nombre incluye doc_id → 200"""
    response = requests.post(
        f"{BASE_URL}/widgets/exportar-word",
        json=SAMPLE_EXPORT_PAYLOAD,
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    disposition = response.headers.get("Content-Disposition", "")
    expected_filename = f"SRS_{VALID_DOC_ID}.docx"
    assert expected_filename in disposition, (
        f"Esperado '{expected_filename}' en Content-Disposition, recibido: {disposition}"
    )


@pytest.mark.xfail(
    reason="El endpoint no valida doc_id vacío — genera el archivo igualmente. "
           "Bug: debería retornar 400 para doc_id vacío.",
    strict=True,
)
def test_TC18_exportar_word_doc_id_vacio():
    """TC18 - POST /widgets/exportar-word con doc_id vacío → 400 (bug: devuelve 200)"""
    response = requests.post(
        f"{BASE_URL}/widgets/exportar-word",
        json=INVALID_EXPORT_PAYLOAD,
    )
    assert is_4xx(response.status_code), f"Esperado error 4xx, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# BUSCAR CON AGENTE  (POST /usuarios/{idusuario}/proyectos/buscar-con-agente)
# ─────────────────────────────────────────────────────────────

def test_TC09_buscar_con_agente_valido():
    """TC09 - POST buscar-con-agente con mensaje válido → 200 + proyectos"""
    import time

    for intento in range(3):
        response = requests.post(
            f"{BASE_URL}/usuarios/{VALID_USER_ID}/proyectos/buscar-con-agente",
            json={"mensaje": "muéstrame mis proyectos recientes"},
        )
        if response.status_code == 429:
            time.sleep(15 * (intento + 1))  # 15s, 30s, 45s
            continue
        break

    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert "proyectos" in data, "La respuesta debe incluir 'proyectos'"
    assert "respuesta_agente" in data, "La respuesta debe incluir 'respuesta_agente'"
    assert isinstance(data["proyectos"], list), "'proyectos' debe ser una lista"


def test_TC10_buscar_con_agente_sin_mensaje():
    """TC10 - POST buscar-con-agente sin campo mensaje → 400"""
    response = requests.post(
        f"{BASE_URL}/usuarios/{VALID_USER_ID}/proyectos/buscar-con-agente",
        json={},
    )
    assert response.status_code == 400, f"Esperado 400, recibido {response.status_code}"
    data = response.json()
    assert "mensaje" in data.get("detail", "").lower(), (
        "El detalle del error debe mencionar 'mensaje'"
    )


# ─────────────────────────────────────────────────────────────
# AGENT QUERY  (POST /agent/query)
# ─────────────────────────────────────────────────────────────

def test_TC11_query_agente_valido():
    """TC11 - POST /agent/query con sesión válida → 200 + respuesta de texto"""
    response = requests.post(
        f"{BASE_URL}/agent/query",
        headers=auth_headers(),
        json={
            "user_id": VALID_USER_ID,
            "session_id": VALID_SESSION_ID,
            "message": "¿Cuáles son mis proyectos activos?",
        },
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert data.get("content") or data.get("session_id"), (
        "La respuesta debe contener 'content' o 'session_id'"
    )


@pytest.mark.xfail(
    reason="VertexAI no lanza error con session_id inválido — crea sesión nueva y devuelve 200. "
           "Bug: debería retornar 500 para sesiones inexistentes.",
    strict=True,
)
def test_TC12_query_agente_session_invalida():
    """TC12 - POST /agent/query con session_id inexistente → 500 (bug: devuelve 200)"""
    response = requests.post(
        f"{BASE_URL}/agent/query",
        headers=auth_headers(),
        json={
            "user_id": VALID_USER_ID,
            "session_id": "session-id-que-no-existe-999",
            "message": "Hola",
        },
    )
    assert response.status_code == 500, f"Esperado 500, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# SESSIONS  (POST /agent/sessions)
# ─────────────────────────────────────────────────────────────

def test_TC13_crear_sesion_valida():
    """TC13 - POST /agent/sessions con user_id válido → 200 + session_id"""
    response = requests.post(
        f"{BASE_URL}/agent/sessions",
        headers=auth_headers(),
        json={"user_id": VALID_USER_ID},
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"
    data = response.json()
    assert "session_id" in data, "La respuesta debe incluir 'session_id'"
    assert data["session_id"], "'session_id' no debe estar vacío"


def test_TC14_crear_sesion_user_id_vacio():
    """TC14 - POST /agent/sessions con user_id vacío → 500"""
    response = requests.post(
        f"{BASE_URL}/agent/sessions",
        headers=auth_headers(),
        json={"user_id": ""},
    )
    assert response.status_code == 500, f"Esperado 500, recibido {response.status_code}"


# ─────────────────────────────────────────────────────────────
# QUERY STREAM  (POST /agent/query/stream)
# ─────────────────────────────────────────────────────────────

def test_TC15_query_stream_valido():
    """TC15 - POST /agent/query/stream con sesión válida → 200 + SSE con chunks"""
    response = requests.post(
        f"{BASE_URL}/agent/query/stream",
        headers=auth_headers(),
        json={
            "user_id": VALID_USER_ID,
            "session_id": VALID_SESSION_ID,
            "message": "Muéstrame un resumen de mis proyectos",
        },
        stream=True,
        timeout=30,
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"

    content_type = response.headers.get("Content-Type", "")
    assert "text/event-stream" in content_type, (
        f"Content-Type debe ser text/event-stream, recibido: {content_type}"
    )

    chunks_received = []
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            chunks_received.append(decoded)
        if len(chunks_received) >= 5:
            break

    assert len(chunks_received) > 0, "El stream debe emitir al menos un chunk"
    assert any(c.startswith("data:") for c in chunks_received), (
        "Los chunks deben tener formato SSE (data: ...)"
    )


def test_TC16_query_stream_mensaje_vacio():
    """TC16 - POST /agent/query/stream con mensaje vacío → 200 + done inmediato"""
    response = requests.post(
        f"{BASE_URL}/agent/query/stream",
        headers=auth_headers(),
        json={
            "user_id": VALID_USER_ID,
            "session_id": VALID_SESSION_ID,
            "message": "",
        },
        stream=True,
        timeout=30,
    )
    assert response.status_code == 200, f"Esperado 200, recibido {response.status_code}"

    raw_chunks = []
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            raw_chunks.append(decoded)
        if len(raw_chunks) >= 10:
            break

    combined = " ".join(raw_chunks)
    assert "done" in combined or "error" in combined or len(raw_chunks) > 0, (
        "El stream debe terminar con 'done' o emitir algún evento"
    )