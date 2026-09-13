from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ThermalAnomaly(Base):
    __tablename__ = "thermal_anomalies"

    id = Column(String, primary_key=True)
    latitude = Column(Float)
    longitude = Column(Float)
    frp = Column(Float)
    brightness_k = Column(Float)
    satellite = Column(String)
    acq_timestamp_ist = Column(DateTime)
    persistence_count_30d = Column(Integer)





class IndustrialSite(Base):
    __tablename__ = "industrial_sites"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime)





class ClassifiedEvent(Base):
    __tablename__ = "classified_events"

    id = Column(String, primary_key=True)
    anomaly_id = Column(String)
    nearest_facility = Column(String)
    distance_to_facility_km = Column(Float)
    classification = Column(String)
    severity = Column(String)
    confidence_score = Column(Float)
    ml_prediction = Column(String)
    ml_confidence = Column(Float)
    ml_explanation = Column(String)
    classified_at = Column(DateTime)



class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    event_id = Column(String)
    severity = Column(String)
    message = Column(String)
    status = Column(String)
    created_at = Column(DateTime)