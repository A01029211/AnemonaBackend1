from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Proyecto

router = APIRouter()

@router.get("/proyectos")
def obtener_proyectos(db: Session = Depends(get_db)):
    proyectos = db.query(Proyecto).all()
    return proyectos