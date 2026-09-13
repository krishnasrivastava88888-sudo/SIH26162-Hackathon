from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ThermalAnomaly
from backend.schemas import ThermalAnomalyResponse

router = APIRouter(prefix="/api/hotspots", tags=["Hotspots"])


@router.get("", response_model=list[ThermalAnomalyResponse])
def get_hotspots(db: Session = Depends(get_db)):
    return db.query(ThermalAnomaly).all()