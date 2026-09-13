from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ThermalAnomaly, ClassifiedEvent, Alert

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("/")
def get_statistics(db: Session = Depends(get_db)):

    total_hotspots = db.query(
        func.count(ThermalAnomaly.id)
    ).scalar()

    persistent_hotspots = db.query(
        func.count(ThermalAnomaly.id)
    ).filter(
        ThermalAnomaly.persistence_count_30d > 1
    ).scalar()

    high_frp_hotspots = db.query(
        func.count(ThermalAnomaly.id)
    ).filter(
        ThermalAnomaly.frp >= 100
    ).scalar()

    severity_rows = db.query(
        ClassifiedEvent.severity,
        func.count(ClassifiedEvent.id)
    ).group_by(
        ClassifiedEvent.severity
    ).all()

    classification_rows = db.query(
        ClassifiedEvent.classification,
        func.count(ClassifiedEvent.id)
    ).group_by(
        ClassifiedEvent.classification
    ).all()

    active_alerts = db.query(
        func.count(Alert.id)
    ).filter(
        Alert.status == "ACTIVE"
    ).scalar()

    return {
        "total_hotspots": total_hotspots,
        "persistent_hotspots": persistent_hotspots,
        "high_frp_hotspots": high_frp_hotspots,
        "active_alerts": active_alerts,
        "severity": {
            severity: count
            for severity, count in severity_rows
        },
        "classifications": {
            classification: count
            for classification, count in classification_rows
        }
    }