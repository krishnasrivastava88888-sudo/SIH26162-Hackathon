from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import IndustrialSite
from backend.schemas import IndustrialSiteResponse

router = APIRouter(prefix="/api/industrial-sites", tags=["Facilities"])


@router.get("", response_model=list[IndustrialSiteResponse])
def get_facilities(db: Session = Depends(get_db)):
    return db.query(IndustrialSite).all()