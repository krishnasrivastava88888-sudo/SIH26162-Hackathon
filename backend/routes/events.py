from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ClassifiedEvent
from backend.schemas import ClassifiedEventResponse

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/", response_model=list[ClassifiedEventResponse])
def get_events(db: Session = Depends(get_db)):
    return db.query(ClassifiedEvent).all()
