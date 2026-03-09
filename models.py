from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, Text
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

