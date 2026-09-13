from datetime import datetime

from pydantic import BaseModel


class ThermalAnomalyResponse(BaseModel):
    id: str
    latitude: float
    longitude: float
    frp: float
    brightness_k: float
    satellite: str
    acq_timestamp_ist: datetime
    persistence_count_30d: int

    class Config:
        from_attributes = True




class IndustrialSiteResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    created_at: datetime

    class Config:
        from_attributes = True





class ClassifiedEventResponse(BaseModel):
    id: str
    anomaly_id: str
    nearest_facility: str | None
    distance_to_facility_km: float | None
    classification: str
    severity: str
    confidence_score: float
    ml_prediction: str
    ml_confidence: float
    ml_explanation: str
    classified_at: datetime

    class Config:
        from_attributes = True



class AlertResponse(BaseModel):
    id: int
    event_id: str
    severity: str
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True