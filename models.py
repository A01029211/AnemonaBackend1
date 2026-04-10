from typing import Optional
from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, Text
from sqlalchemy import Column, Boolean, Integer, String, TIMESTAMP, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Proyecto(Base):
    __tablename__ = "proyecto"
  
    folio = Column(Integer, primary_key=True, index=True)
    fechacreacion = Column(TIMESTAMP, server_default=func.now())
    nombreproyecto = Column(String(200))
    fechaactualizacion = Column(TIMESTAMP)
    tipoiniciativa = Column(String(100))
    cr = Column(Integer)
    patrocinador = Column(String(150))
    socionegocio = Column(String(150))
    descripciongeneral = Column(Text)
    objetivoiniciativa = Column(Text)
    requerimientosnegocio = Column(Text)
    beneficios = Column(Text)
    participacionareas = Column(Text)
    supuestos = Column(Text)
    exclusiones = Column(Text)
    restricciones = Column(Text)
    anexos = Column(Text)


class Usuario(Base):
    __tablename__ = 'usuario'

    idusuario = Column(Text, primary_key=True, index=True)
    nombre = Column(String(50))
    apellidopaterno = Column(String(50))
    apellidomaterno = Column(String(50))
    correo = Column(String(150))
    password = Column(String(255))
    ultimoacceso = Column(TIMESTAMP)
    activo = Column(Boolean)
    iddepartamento = Column(Integer)
    idrol = Column(Integer)


class Departamento(Base):
    __tablename__ = "departamento"

    iddepartamento = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))



class Rol(Base):
    __tablename__ = "rol"

    idrol = Column(Integer, primary_key=True, index=True)
    nombrerol = Column(String(100))



class empleados_proyecto(Base):
    __tablename__ = "empleados_proyecto"

    folio = Column(Integer, ForeignKey("proyecto.folio"), primary_key=True)
    idusuario = Column(Text, ForeignKey("usuario.idusuario"), primary_key=True)


class Mensaje(Base):
    __tablename__ = "mensajes"

    idmensaje = Column(Integer, primary_key=True, index=True)
    contenido = Column(Text)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    folio = Column(Integer, ForeignKey("proyecto.folio"))
    id_session = Column(Integer, ForeignKey("session_chat.id_session"))


class SessionChat(Base):
    __tablename__ = "session_chat"

    id_session = Column(Integer, primary_key=True, index=True)
    
    session_id = Column(String(70))
    folio = Column(Integer, ForeignKey("proyecto.folio"))
    idusuario = Column(Text, ForeignKey("usuario.idusuario"))
    fecha_inicio = Column(TIMESTAMP, server_default=func.now())
    id_firestore_document = Column(String(50))
    fecha_conclusion = Column(TIMESTAMP)
