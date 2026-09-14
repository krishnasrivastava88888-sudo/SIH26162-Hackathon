import os
import sys
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.webhook_notifier import send_discord_webhook
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

# 1. Mount Database Routes
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
    acq_timestamp_ist: Optional[str] = "2026-09-14 17:30:00"

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
        input_data = payload.model_dump()
        result = predictor_v2.predict_single(input_data)
        
        # Merge telemetry payload and model inference results
        res_dict = result if isinstance(result, dict) else (result.model_dump() if hasattr(result, "model_dump") else {})
        combined = {**input_data, **res_dict}
        
        # Supply required webhook fallback keys to prevent KeyErrors
        combined.setdefault("latitude", 26.8315)
        combined.setdefault("longitude", 80.8872)
        combined.setdefault("nearest_facility", "Talkatora Industrial Estate")
        combined.setdefault("satellite", "VIIRS_NOAA21_NRT")
        combined.setdefault("acq_timestamp_ist", "2026-09-14 17:30:00 IST")
        combined.setdefault("confidence_score", combined.get("confidence", 0.95))

        # Normalize score scale (handles both decimal 0.83 and integer 83.1)
        raw_score = combined.get("risk_score") or combined.get("risk") or 0.0
        try:
            score = float(raw_score)
            if 0.0 < score <= 1.0:
                score = score * 100
        except Exception:
            score = 0.0

        # Dispatch alert when risk reaches critical threshold
        if score >= 70 or "CRITICAL" in str(combined).upper():
            print(f"[Discord] Dispatched alert for Critical Anomaly (Risk Score: {score:.1f})")
            try:
                send_discord_webhook(combined)
            except Exception as hook_err:
                print(f"[Discord Webhook Error]: {hook_err}")
        else:
            print(f"[Discord] Score {score:.1f} below threshold, skipping alert.")

        return result
    except Exception as e:
        print(f"[Inference Pipeline Error]: {e}")
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