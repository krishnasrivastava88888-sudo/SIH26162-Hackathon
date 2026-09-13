import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

# Member 4 Database Routers
from backend.routes import hotspots, facilities, events, alerts, statistics
from ml.predict_v2 import predictor_v2

app = FastAPI(
    title="ThermoGuard AI | Tactical Threat Intelligence API",
    description="Integrated NASA FIRMS thermal anomaly detection and PostGIS/RF-v2 classification pipeline",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount Database Routes (prefixes already defined in route files)
app.include_router(hotspots.router)
app.include_router(facilities.router)
app.include_router(events.router)
app.include_router(events.router, prefix="/api")  # Supports both /events and /api/events
app.include_router(alerts.router, prefix="/api")
app.include_router(statistics.router, prefix="/api")

# 2. ML Prediction Schemas
class HotspotTelemetry(BaseModel):
    frp: float
    brightness_k: float
    distance_to_facility_km: Optional[float] = 999.0
    persistence_count_30d: Optional[int] = 1
    cluster_size: Optional[int] = 1
    acq_timestamp_ist: Optional[str] = "2026-09-13 12:00:00"

# 3. Dedicated ML Endpoints
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ONLINE",
        "service": "ThermoGuardAI Tactical Gateway",
        "ml_engine": "RF-v2.0 Active",
        "database": "PostgreSQL 16 / PostGIS"
    }

@app.post("/predict", tags=["Machine Learning"])
def predict_anomaly(payload: HotspotTelemetry):
    try:
        result = predictor_v2.predict_single(payload.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict/batch", tags=["Machine Learning"])
def predict_batch(payloads: List[HotspotTelemetry]):
    try:
        return [predictor_v2.predict_single(p.model_dump()) for p in payloads]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)