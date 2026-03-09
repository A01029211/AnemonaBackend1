from sqlalchemy import Column, Boolean, Integer, String, TIMESTAMP, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Proyecto(Base):
    __tablename__ = "proyecto"

    folio = Column(Integer, primary_key=True, index=True)
    fechaCreacion = Column(TIMESTAMP, server_default=func.now())
    nombreProyecto = Column(String(200))
    fechaActualizacion = Column(TIMESTAMP)
    tipoIniciativa = Column(String(100))
    CR = Column(Integer)
    patrocinador = Column(String(150))
    socioNegocio = Column(String(150))
    descripcionGeneral = Column(Text)
    objetivoIniciativa = Column(Text)
    requerimientosNegocio = Column(Text)
    beneficios = Column(Text)
    participacionAreas = Column(Text)
    supuestos = Column(Text)
    exclusiones = Column(Text)
    restricciones = Column(Text)
    anexos = Column(Text)


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



class Usuario(Base):
    __tablename__ = "usuario"

    idusuario = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50))
    apellidopaterno = Column(String(50))
    apellidomaterno = Column(String(50))
    correo = Column(String(150), unique=True, index=True)
    password = Column(String(255))
    ultimoacceso = Column(TIMESTAMP)
    activo = Column(Boolean)
    iddepartamento = Column(Integer, ForeignKey("departamento.iddepartamento"))
    idrol = Column(Integer, ForeignKey("rol.idrol"))



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
