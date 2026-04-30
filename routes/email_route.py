import smtplib
import os
import json
import base64
import ssl
import time
import urllib.request  # ← NUEVO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from google.cloud import firestore
from google import genai
from sqlalchemy.orm import Session

from utils.auth import leer_token
from database import get_db
from models import Usuario

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

FIRESTORE_PROJECT = "anemona-2130e"
COLLECTION        = "srs_anemona"
_db = firestore.Client(project=FIRESTORE_PROJECT)

SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

BANORTE_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Logo_de_Banorte.svg/1280px-Logo_de_Banorte.svg.png"


# ← NUEVO: descarga el logo y lo convierte a base64 para que no sea bloqueado sds
def _get_logo_base64() -> str:
    try:
        req = urllib.request.Request(BANORTE_LOGO_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    except Exception as e:
        print(f"No se pudo descargar el logo: {e}")
        return BANORTE_LOGO_URL


# ── Model ─────────────────────────────────────────────────────────────────
class SendEmailRequest(BaseModel):
    doc_id: str
    pdf_base64: str | None = None
    user_name: str | None = None  # ← NUEVO: viene del frontend (localStorage)


# ── Helpers ───────────────────────────────────────────────────────────────
def _get_srs_data(doc_id: str) -> dict:
    doc = _db.collection(COLLECTION).document(doc_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Documento '{doc_id}' no encontrado")
    return doc.to_dict()


def _extract_campos(srs_data: dict) -> dict:
    campos = {}

    for wid in srs_data.get("posiciones", []):
        widget_data = srs_data.get(wid, {})
        campos.update(widget_data.get("campos", {}))

    if not campos:
        datos_generales = srs_data.get("DATOS_GENERALES", {})
        if datos_generales:
            campos.update(datos_generales)

    if not campos:
        for key in ["NOMBRE_INICIATIVA", "SOLICITANTE", "TIPO_INICIATIVA",
                    "PATROCINADOR", "SOCIO", "INFO_CONTACTO", "DGA", "CR"]:
            if key in srs_data:
                campos[key] = srs_data[key]

    print(f"Campos extraídos: {campos}")
    return campos


def _generate_summary(srs_data: dict) -> str:
    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT,
        location="us-central1",
    )
    prompt = f"""
Eres un analista de negocios senior. Dado el siguiente documento SRS en JSON,
genera un resumen ejecutivo profesional en español de máximo 4 párrafos.
Incluye: propósito del proyecto, áreas impactadas, objetivos clave y beneficios esperados.
Usa lenguaje ejecutivo y conciso. Responde SOLO con el texto, sin markdown ni encabezados.

SRS:
{json.dumps(srs_data, ensure_ascii=False, indent=2)[:8000]}
"""
    for intento in range(5):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) and intento < 4:
                espera = 10 * (intento + 1)
                print(f"Rate limit, esperando {espera}s... (intento {intento+1}/5)")
                time.sleep(espera)
            else:
                raise


def _data_row(label: str, value: str) -> str:
    return f"""
        <tr>
          <td style="font-size:13px;color:#666;width:38%;padding:6px 8px 6px 0;
                     vertical-align:top;border-bottom:1px solid #f0f0f0;">{label}</td>
          <td style="font-size:13px;color:#1a1a2e;font-weight:600;
                     padding:6px 0;border-bottom:1px solid #f0f0f0;">{value or "N/A"}</td>
        </tr>
    """


def _build_html(campos: dict, summary: str, user_name: str, doc_id: str) -> str:
    nombre_iniciativa = campos.get("NOMBRE_INICIATIVA", "N/A")
    solicitante       = campos.get("SOLICITANTE", "N/A")
    tipo_iniciativa   = campos.get("TIPO_INICIATIVA", "N/A")
    socio             = campos.get("SOCIO", "N/A")
    patrocinador      = campos.get("PATROCINADOR", "N/A")
    info_contacto     = campos.get("INFO_CONTACTO", "N/A")
    dga               = campos.get("DGA", "N/A")
    cr                = campos.get("CR", "N/A")
    logo_src          = BANORTE_LOGO_URL

    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:40px 0;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.10);overflow:hidden;">

        <!-- HEADER -->
        <tr>
          <td style="background:#1a1a2e;padding:24px 36px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <img src="{logo_src}" alt="Banorte" height="40" style="display:block;"/>
                </td>
                <td align="right">
                  <span style="color:#8888aa;font-size:12px;">Gestión de Requerimientos</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- BANDA -->
        <tr>
          <td style="background:#1a1a2e;padding:18px 36px;border-top:1px solid #2e2e4e;">
            <p style="margin:0;color:#fff;font-size:17px;font-weight:700;">
              Levantamiento de Requerimiento
            </p>
            <p style="margin:4px 0 0;color:#8888aa;font-size:12px;">
              Documento generado por Anemona SRS Assistant · {doc_id}
            </p>
          </td>
        </tr>

        <!-- SALUDO -->
        <tr>
          <td style="padding:32px 36px 0;">
            <p style="margin:0;font-size:15px;color:#1a1a2e;font-weight:600;">
              Hola, <span style="color:#EB0029;">{user_name}</span>
            </p>
            <p style="margin:10px 0 0;font-size:14px;color:#555;line-height:1.65;">
              Se ha generado el documento SRS correspondiente a tu iniciativa.
              Encontrarás el resumen ejecutivo y el documento completo adjunto en este correo.
            </p>
          </td>
        </tr>

        <!-- DATOS GENERALES -->
        <tr>
          <td style="padding:24px 36px 0;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border-radius:8px;overflow:hidden;border:1px solid #e5e7eb;">
              <tr>
                <td colspan="2" style="background:#133b73;padding:11px 16px;">
                  <span style="color:#fff;font-size:13px;font-weight:700;">DATOS GENERALES</span>
                </td>
              </tr>
              <tr>
                <td colspan="2" style="padding:12px 16px 0;background:#fafbfc;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    {_data_row("Nombre de la iniciativa", nombre_iniciativa)}
                    {_data_row("Solicitante", solicitante)}
                    {_data_row("Tipo de iniciativa", tipo_iniciativa)}
                    {_data_row("Socio de negocio", socio)}
                    {_data_row("Patrocinador", patrocinador)}
                    {_data_row("Contacto", info_contacto)}
                    {_data_row("DGA", dga)}
                    {_data_row("CR", cr)}
                  </table>
                </td>
              </tr>
              <tr><td colspan="2" style="height:12px;background:#fafbfc;"></td></tr>
            </table>
          </td>
        </tr>

        <!-- RESUMEN EJECUTIVO -->
        <tr>
          <td style="padding:28px 36px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-bottom:10px;border-bottom:2px solid #EB0029;">
                  <span style="font-size:15px;font-weight:700;color:#1a1a2e;">Resumen Ejecutivo</span>
                </td>
              </tr>
            </table>
            <p style="margin:14px 0 0;font-size:14px;color:#444;line-height:1.75;white-space:pre-line;">
              {summary}
            </p>
          </td>
        </tr>

        <!-- NOTA PDF ADJUNTO -->
        <tr>
          <td style="padding:24px 36px 0;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#fff8e1;border-radius:6px;border-left:4px solid #f59e0b;">
              <tr>
                <td style="padding:12px 16px;">
                  <p style="margin:0;font-size:12px;color:#92400e;line-height:1.5;">
                    <strong>📎 Documento adjunto:</strong> El documento SRS completo
                    se encuentra adjunto en este correo en formato PDF.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="padding:32px 36px;text-align:center;border-top:1px solid #e5e7eb;margin-top:24px;">
            <p style="margin:0;font-size:11px;color:#9ca3af;">
              Este mensaje fue generado automáticamente — por favor no respondas.
            </p>
            <p style="margin:6px 0 0;font-size:11px;color:#c0c0c0;">
              ©️ 2025 Grupo Financiero Banorte · Anemona SRS Assistant
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _send_smtp(to_email: str, subject: str, html: str, pdf_base64: str | None = None):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = to_email

    msg.attach(MIMEText(html, "html", "utf-8"))

    if pdf_base64:
        pdf_bytes = base64.b64decode(pdf_base64)
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(pdf_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", "attachment", filename="SRS_Documento.pdf")
        msg.attach(attachment)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=15) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())


# ── Endpoint ─────────────────────────────────────────────────────────────
@router.post("/send-email")
async def send_srs_email(
    request: SendEmailRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    datos = leer_token(token)
    if not datos:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    usuario = db.query(Usuario).filter(Usuario.correo == datos["correo"]).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_email = usuario.correo
    # ← CAMBIADO: usa el nombre del frontend, si no viene usa el de la BD
    user_name = request.user_name or f"{usuario.nombre} {usuario.apellidopaterno}"

    try:
        print("1. Obteniendo datos de Firestore...")
        srs_data = _get_srs_data(request.doc_id)
        print("2. Firestore OK. Extrayendo campos...")
        campos = _extract_campos(srs_data)
        print("3. Campos extraídos:", campos)
        print("4. Generando resumen con Gemini...")
        summary = _generate_summary(srs_data)
        print("5. Resumen generado. Construyendo HTML...")
        html = _build_html(campos, summary, user_name, request.doc_id)
        print("6. HTML listo. Enviando correo...")
        nombre_iniciativa = campos.get("NOMBRE_INICIATIVA", request.doc_id)
        subject = f"SRS · {nombre_iniciativa}"
        _send_smtp(user_email, subject, html, request.pdf_base64)
        print("7. Correo enviado OK")

        return {"ok": True, "message": f"Correo enviado a {user_email}"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR DETALLADO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))