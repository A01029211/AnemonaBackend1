from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database import get_db
from models import Departamento, Proyecto, Mensaje, SessionChat, Usuario, empleados_proyecto
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import desc, func
import requests
import json
from routes.firestore_srs import eliminar_documento_firestore
from fastapi import APIRouter, HTTPException, Body
import vertexai
from vertexai import agent_engines


from routes.firestore_srs import Formulario

router = APIRouter()

# obtener proyectos
@router.get("/proyectos")
def obtener_proyectos(db: Session = Depends(get_db)):
    proyectos = db.query(Proyecto).all()
    return proyectos

@router.get("/usuarios/{idusuario}/proyectos")
def obtener_mis_proyectos(idusuario: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    depto = (
        db.query(Departamento)
        .filter(Departamento.iddepartamento == usuario.iddepartamento)
        .first()
    )
    nombre_depto = depto.nombre if depto else "Sin área"

    resultados = (
        db.query(Proyecto, SessionChat)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(SessionChat.idusuario == idusuario)
        .order_by(Proyecto.fechacreacion.desc())
        .all()
    )

    return [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "departamento": nombre_depto,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
        }
        for proyecto, session in resultados
    ]

# obtener mensajes
@router.get("/mensajes")
def obtener_mensajes(db: Session = Depends(get_db)):
    mensajes = db.query(Mensaje).all()
    return mensajes

# obtener mensajes de un proyecto específico
@router.get("/proyectos/{folio}/mensajes")
def obtener_mensajes_proyecto(folio: int, db: Session = Depends(get_db)):
    mensajes = db.query(Mensaje).filter(Mensaje.folio == folio).all()
    return mensajes

# obtener mensajes de una sesión
@router.get("/chat/{id_session}")
def obtener_chat(id_session: int, db: Session = Depends(get_db)):
    
    mensajes = db.query(Mensaje).filter(
        Mensaje.id_session == id_session
    ).order_by(Mensaje.fecha_creacion).all()

    return mensajes

# ver usuarios en una sesión
@router.get("/session/{session_id}/usuarios")
def usuarios_sesion(session_id: str, db: Session = Depends(get_db)):

    usuarios = db.query(SessionChat).filter(
        SessionChat.session_id == session_id
    ).all()

    return usuarios

# ver los departamentos existentes
@router.get("/departamentos")
def obtener_departamentos(db: Session = Depends(get_db)):
    departamentos = db.query(Departamento).all()
    return departamentos


"""
#Obtener los proyectos más recientes, (filtrando por tablla empleados_proyecto)
@router.get("/usuarios/{idusuario}/proyectos_recientes")
def obtener_proyectos_recientes(idusuario: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    resultados = (
        db.query(Proyecto, SessionChat)
        .join(empleados_proyecto, Proyecto.folio == empleados_proyecto.folio)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(empleados_proyecto.idusuario == idusuario)
        .order_by(
            desc(func.coalesce(Proyecto.fechaactualizacion, Proyecto.fechacreacion))
        )
        .limit(4)
        .all()
    )

    return [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechaactualizacion": proyecto.fechaactualizacion.isoformat() if proyecto.fechaactualizacion else None,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
        }
        for proyecto, session in resultados
    ]

"""

#Obtener los proyectos más recientes, por el session_chat
@router.get("/usuarios/{idusuario}/proyectos_recientes")
def obtener_proyectos_recientes(idusuario: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    resultados = (
        db.query(Proyecto, SessionChat)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(SessionChat.idusuario == idusuario)
        .order_by(desc(func.coalesce(Proyecto.fechaactualizacion, Proyecto.fechacreacion)))
        .limit(4)
        .all()
    )

    return [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechaactualizacion": proyecto.fechaactualizacion.isoformat() if proyecto.fechaactualizacion else None,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
        }
        for proyecto, session in resultados
    ]



#Eliminar proyecto según su folio
@router.delete("/proyectos/{folio}")
def eliminar_proyecto(folio: int, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.folio == folio).first()

    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        
        sesion = db.query(SessionChat).filter(SessionChat.folio == folio).first()


        # Borrar documento de Firestore
        if sesion and sesion.id_firestore_document:
            eliminar_documento_firestore(sesion.id_firestore_document)

        # Borrar documento y sesión en SQL
        if sesion:
            db.query(Mensaje).filter(Mensaje.id_session == sesion.id_session).delete()
            db.query(SessionChat).filter(SessionChat.folio == folio).delete()

       
        db.query(empleados_proyecto).filter(empleados_proyecto.folio == folio).delete()

     
        db.query(Proyecto).filter(Proyecto.folio == folio).delete()

        db.commit()

        return {
            "ok": True,
            "message": "Proyecto eliminado correctamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo eliminar el proyecto: {str(e)}"
        )




#AGENTE DE FILTRADO

#Endpoints iniciales para probar funcionamiento del agente
@router.post("/proyectos/filtrar")
def filtrar_proyectos(payload: dict = Body(...), db: Session = Depends(get_db)):
    filtros = payload.get("filters", {})
    limit = payload.get("limit", 20)

    query = db.query(Proyecto.folio)

    if filtros.get("folio") is not None:
        query = query.filter(Proyecto.folio == int(filtros["folio"]))

    if filtros.get("patrocinador"):
        valor = str(filtros["patrocinador"]).strip()
        query = query.filter(Proyecto.patrocinador.ilike(f"%{valor}%"))

    if filtros.get("nombreproyecto"):
        valor = str(filtros["nombreproyecto"]).strip()
        query = query.filter(Proyecto.nombreproyecto.ilike(f"%{valor}%"))

    if filtros.get("socionegocio"):
        valor = str(filtros["socionegocio"]).strip()
        query = query.filter(Proyecto.socionegocio.ilike(f"%{valor}%"))

    if filtros.get("tipoiniciativa"):
        valor = str(filtros["tipoiniciativa"]).strip()
        query = query.filter(Proyecto.tipoiniciativa.ilike(f"%{valor}%"))

    if filtros.get("descripciongeneral"):
        valor = str(filtros["descripciongeneral"]).strip()
        query = query.filter(Proyecto.descripciongeneral.ilike(f"%{valor}%"))

    if filtros.get("cr") is not None:
        query = query.filter(Proyecto.cr == int(filtros["cr"]))

    if filtros.get("fechacreacion"):
        fechas = filtros["fechacreacion"]

        if fechas.get("from"):
            fecha_desde = datetime.fromisoformat(fechas["from"])
            query = query.filter(Proyecto.fechacreacion >= fecha_desde)

        if fechas.get("to"):
            fecha_hasta = datetime.fromisoformat(fechas["to"])
            query = query.filter(Proyecto.fechacreacion <= fecha_hasta)
            
    
    if filtros.get("fechaactualizacion"):
        fechas_actualizacion = filtros["fechaactualizacion"]

        if fechas_actualizacion.get("from"):
            fecha_desde = datetime.fromisoformat(fechas_actualizacion["from"])
            query = query.filter(Proyecto.fechaactualizacion >= fecha_desde)

        if fechas_actualizacion.get("to"):
            fecha_hasta = datetime.fromisoformat(fechas_actualizacion["to"])
            query = query.filter(Proyecto.fechaactualizacion <= fecha_hasta)


    resultados = query.limit(limit).all()

    folios = [fila[0] for fila in resultados]

    return {
        "folios": folios,
        "total": len(folios),
        "filtros_recibidos": filtros
    }



@router.get("/proyectos/debug/folios")
def debug_folios(db: Session = Depends(get_db)):
    proyectos = db.query(
        Proyecto.folio,
        Proyecto.nombreproyecto,
        Proyecto.patrocinador
    ).order_by(Proyecto.folio.desc()).limit(10).all()

    return [
        {
            "folio": p.folio,
            "nombreproyecto": p.nombreproyecto,
            "patrocinador": p.patrocinador
        }
        for p in proyectos
    ]



@router.post("/proyectos/por-folios")
def obtener_proyectos_por_folios(payload: dict = Body(...), db: Session = Depends(get_db)):
    folios = payload.get("folios", [])

    if not folios:
        return {
            "proyectos": [],
            "total": 0
        }

    proyectos = (
        db.query(Proyecto)
        .filter(Proyecto.folio.in_(folios))
        .all()
    )

    return {
        "proyectos": [
            {
                "folio": p.folio,
                "nombreproyecto": p.nombreproyecto,
                "fechacreacion": p.fechacreacion.isoformat() if p.fechacreacion else None,
                "fechaactualizacion": p.fechaactualizacion.isoformat() if p.fechaactualizacion else None,
                "tipoiniciativa": p.tipoiniciativa,
                "cr": p.cr,
                "patrocinador": p.patrocinador,
                "socionegocio": p.socionegocio,
                "descripciongeneral": p.descripciongeneral,
                "objetivoiniciativa": p.objetivoiniciativa,
                "requerimientosnegocio": p.requerimientosnegocio,
                "beneficios": p.beneficios,
                "participacionareas": p.participacionareas,
                "supuestos": p.supuestos,
                "exclusiones": p.exclusiones,
                "restricciones": p.restricciones,
                "anexos": p.anexos
            }
            for p in proyectos
        ],
        "total": len(proyectos)
    }




# Endpint específicos para buscar únicamente proyectos pertenecientes al usuario logueado

@router.post("/usuarios/{idusuario}/proyectos/filtrar")
def filtrar_proyectos_usuario(
    idusuario: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.idusuario == idusuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    depto = (
        db.query(Departamento)
        .filter(Departamento.iddepartamento == usuario.iddepartamento)
        .first()
    )
    nombre_depto = depto.nombre if depto else "Sin área"

    filtros = payload.get("filters", {})
    limit = payload.get("limit", 20)

    query = (
        db.query(Proyecto, SessionChat)
        .join(SessionChat, Proyecto.folio == SessionChat.folio)
        .filter(SessionChat.idusuario == idusuario)
    )

    if filtros.get("folio") is not None:
        query = query.filter(Proyecto.folio == int(filtros["folio"]))

    if filtros.get("patrocinador"):
        valor = str(filtros["patrocinador"]).strip()
        query = query.filter(Proyecto.patrocinador.ilike(f"%{valor}%"))

    if filtros.get("nombreproyecto"):
        valor = str(filtros["nombreproyecto"]).strip()
        query = query.filter(Proyecto.nombreproyecto.ilike(f"%{valor}%"))

    if filtros.get("socionegocio"):
        valor = str(filtros["socionegocio"]).strip()
        query = query.filter(Proyecto.socionegocio.ilike(f"%{valor}%"))

    if filtros.get("tipoiniciativa"):
        valor = str(filtros["tipoiniciativa"]).strip()
        query = query.filter(Proyecto.tipoiniciativa.ilike(f"%{valor}%"))

    if filtros.get("descripciongeneral"):
        valor = str(filtros["descripciongeneral"]).strip()
        query = query.filter(Proyecto.descripciongeneral.ilike(f"%{valor}%"))

    if filtros.get("cr") is not None:
        query = query.filter(Proyecto.cr == int(filtros["cr"]))

    if filtros.get("fechacreacion"):
        fechas = filtros["fechacreacion"]

        if fechas.get("from"):
            fecha_desde = datetime.fromisoformat(fechas["from"])
            query = query.filter(Proyecto.fechacreacion >= fecha_desde)

        if fechas.get("to"):
            fecha_hasta = datetime.fromisoformat(fechas["to"])
            query = query.filter(Proyecto.fechacreacion <= fecha_hasta)

    if filtros.get("fechaactualizacion"):
        fechas_actualizacion = filtros["fechaactualizacion"]

        if fechas_actualizacion.get("from"):
            fecha_desde = datetime.fromisoformat(fechas_actualizacion["from"])
            query = query.filter(Proyecto.fechaactualizacion >= fecha_desde)

        if fechas_actualizacion.get("to"):
            fecha_hasta = datetime.fromisoformat(fechas_actualizacion["to"])
            query = query.filter(Proyecto.fechaactualizacion <= fecha_hasta)

    resultados = (
        query
        .order_by(Proyecto.fechacreacion.desc())
        .limit(limit)
        .all()
    )

    proyectos = [
        {
            "folio": proyecto.folio,
            "nombreproyecto": proyecto.nombreproyecto,
            "fechacreacion": proyecto.fechacreacion.isoformat() if proyecto.fechacreacion else None,
            "fechaactualizacion": proyecto.fechaactualizacion.isoformat() if proyecto.fechaactualizacion else None,
            "departamento": nombre_depto,
            "session_id": session.session_id,
            "id_firestore_document": session.id_firestore_document,
            "patrocinador": proyecto.patrocinador,
            "socionegocio": proyecto.socionegocio,
            "tipoiniciativa": proyecto.tipoiniciativa,
            "cr": proyecto.cr
        }
        for proyecto, session in resultados
    ]

    return {
        "proyectos": proyectos,
        "folios": [p["folio"] for p in proyectos],
        "total": len(proyectos),
        "idusuario": idusuario,
        "filtros_recibidos": filtros
    }



# Endpoint para buscar con el agente desde el frontend
@router.post("/usuarios/{idusuario}/proyectos/buscar-con-agente-local")
def buscar_con_agente_local(
    idusuario: str,
    payload: dict = Body(...)
):
    mensaje = payload.get("mensaje")

    if not mensaje:
        raise HTTPException(status_code=400, detail="El campo 'mensaje' es obligatorio")

    app_name = "agente_filtrado"
    user_id = idusuario
    session_id = f"filter_session_{idusuario}"

    # Crear sesión si no existe
    session_url = f"http://127.0.0.1:8002/apps/{app_name}/users/{user_id}/sessions"

    session_payload = {
        "sessionId": session_id,
        "state": {}
    }

    session_response = requests.post(session_url, json=session_payload)

    if session_response.status_code not in [200, 409]:
        raise HTTPException(
            status_code=500,
            detail=f"Error creando sesión ADK: {session_response.text}"
        )

    # Mandar mensaje al agente
    run_url = "http://127.0.0.1:8002/run_sse"

    run_payload = {
        "app_name": app_name,
        "user_id": user_id,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [
                {
                    "text": f"{mensaje}. Usa idusuario {idusuario}."
                }
            ]
        },
        "streaming": False
    }

    response = requests.post(run_url, json=run_payload)

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando agente ADK: {response.text}"
        )

    # Leer eventos SSE
    final_text = ""
    proyectos = []
    total = 0

    for line in response.text.splitlines():
        if line.startswith("data: "):
            raw_json = line.replace("data: ", "")

            try:
                event = json.loads(raw_json)
                content = event.get("content", {})

                # texto final del agente
                if content.get("role") == "model":
                    for part in content.get("parts", []):
                        if "text" in part:
                            final_text += part["text"]

                # respuesta de la función/tool
                if content.get("role") == "user":
                    for part in content.get("parts", []):
                        function_response = part.get("functionResponse")
                        if function_response:
                            response_data = function_response.get("response", {})

                            if "proyectos" in response_data:
                                proyectos = response_data.get("proyectos", [])
                                total = response_data.get("total", 0)

            except Exception:
                pass

    return {
        "respuesta_agente": final_text,
        "proyectos": proyectos,
        "total": total,
        "idusuario": idusuario
    }