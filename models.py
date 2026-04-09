from typing import Optional
from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, Text
from sqlalchemy import Column, Boolean, Integer, String, TIMESTAMP, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Proyecto(Base):
    __tablename__ = "proyecto"
  
    folio = Column(Integer, primary_key=True, index=True)
    fechaCreacion = Column("fechacreacion", TIMESTAMP, server_default=func.now())
    nombreProyecto = Column("nombreproyecto", String(200))
    fechaActualizacion = Column("fechaactualizacion", TIMESTAMP)
    tipoIniciativa = Column("tipoiniciativa", String(100))
    CR = Column("cr", Integer)
    patrocinador = Column("patrocinador", String(150))
    socioNegocio = Column("socionegocio", String(150))
    descripcionGeneral = Column("descripciongeneral", Text)
    objetivoIniciativa = Column("objetivoiniciativa", Text)
    requerimientosNegocio = Column("requerimientosnegocio", Text)
    beneficios = Column("beneficios", Text)
    participacionAreas = Column("participacionareas", Text)
    supuestos = Column("supuestos", Text)
    exclusiones = Column("exclusiones", Text)
    restricciones = Column("restricciones", Text)
    anexos = Column("anexos", Text)


class Usuario(Base):
    __tablename__ = 'usuario'

    idusuario = Column(Integer, primary_key=True, index=True)
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



class EmpleadosProyecto(Base):
    __tablename__ = "empleados_proyecto"

    folio = Column(Integer, ForeignKey("proyecto.folio"), primary_key=True)
    idusuario = Column(Integer, ForeignKey("usuario.idusuario"), primary_key=True)




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
    idusuario = Column(Integer, ForeignKey("usuario.idusuario"))
    fecha_inicio = Column(TIMESTAMP, server_default=func.now())
    fecha_conclusion = Column(TIMESTAMP)
