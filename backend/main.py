from contextlib import asynccontextmanager
import os
import sys
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure project root is in Python module search path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
  sys.path.insert(0, BASE_DIR)

from backend.routes import alerts, events, facilities, hotspots, statistics
from ml.predict_v2 import predictor_v2
from scripts.webhook_notifier import send_discord_webhook

DASHBOARD_PATH = os.path.join(BASE_DIR, "dashboard.html")


# Initialize APScheduler for automated 5-minute live FIRMS pipeline
scheduler = BackgroundScheduler()


def scheduled_firms_ingestion_job():
  """Run the complete NASA FIRMS -> ML -> GIS -> PostgreSQL pipeline."""
  try:
    print("[Scheduler] Starting automated 5-minute live telemetry pipeline...")

    import subprocess

    steps = [
        ["scripts/download_firms.py"],
        ["scripts/persistence_engine.py"],
        ["gis/run_member3.py"],
        ["scripts/sync_to_postgres.py"],
        ["scripts/create_map.py"],
    ]

    for step in steps:
      script = step[0]
      print(f"[Scheduler] Running {script}...")
      result = subprocess.run(
          [sys.executable, script],
          cwd=BASE_DIR,
      )

      if result.returncode != 0:
        print(f"[Scheduler Error] {script} failed.")
        return

    print("[Scheduler] 5-minute live telemetry pipeline completed successfully.")

  except Exception as e:
    print(f"[Scheduler Error] FIRMS auto-ingestion failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
  # Startup: Schedule complete live pipeline every 5 minutes
  scheduler.add_job(
      scheduled_firms_ingestion_job,
      "interval",
      minutes=5,
      id="firms_sync_job",
      replace_existing=True,
      max_instances=1,
  )
  scheduler.start()
  print(
      "[Scheduler] APScheduler started successfully "
      "(live pipeline interval: 5 minutes)."
  )
  yield
  # Shutdown: Stop scheduler
  scheduler.shutdown()
  print("[Scheduler] APScheduler shut down.")


app = FastAPI(
    title="ThermoGuard AI | Tactical Threat Intelligence API",
    description=(
        "Integrated NASA FIRMS thermal anomaly detection and PostGIS/RF-v2"
        " classification pipeline"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for local dashboards and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount Modular Database Routers
app.include_router(hotspots.router)
app.include_router(facilities.router)
app.include_router(events.router)
app.include_router(events.router, prefix="/api")  # Dual mount for /api/events/
app.include_router(alerts.router, prefix="/api")
app.include_router(statistics.router, prefix="/api")


# 2. Hotspot Telemetry Schemas
class HotspotTelemetry(BaseModel):
  frp: float = Field(..., description="Fire Radiative Power (MW)")
  brightness_k: float = Field(
      ..., description="Brightness temperature in Kelvin"
  )
  distance_to_facility_km: Optional[float] = Field(
      999.0, description="Proximity to nearest industrial asset (km)"
  )
  latitude: Optional[float] = Field(26.8315, description="Hotspot latitude")
  longitude: Optional[float] = Field(80.8872, description="Hotspot longitude")
  nearest_facility: Optional[str] = Field(
      "Talkatora Industrial Estate", description="Asset name"
  )
  satellite: Optional[str] = Field(
      "VIIRS_NOAA21_NRT", description="Sensor payload source"
  )
  persistence_count_30d: Optional[int] = Field(
      1, description="30-day thermal recurrence count"
  )
  cluster_size: Optional[int] = Field(1, description="Detected spatial cluster")
  acq_timestamp_ist: Optional[str] = Field(
      "2026-09-15 19:30:00 IST", description="Observation timestamp"
  )


# 3. Webhook Background Dispatch Helper
def dispatch_webhook_task(payload: dict, score: float):
  try:
    print(
        f"[Discord] Dispatched alert for Critical Anomaly (Risk Score:"
        f" {score:.1f})"
    )
    send_discord_webhook(payload)
  except Exception as hook_err:
    print(f"[Discord Webhook Error]: {hook_err}")


# 4. Frontend & Core System Endpoints
@app.get("/", include_in_schema=False)
def serve_dashboard():
  """Serves the dashboard interface directly from project root."""
  if os.path.exists(DASHBOARD_PATH):
    return FileResponse(DASHBOARD_PATH, media_type="text/html")
  return {
      "status": "ONLINE",
      "service": "ThermoGuardAI Tactical Gateway",
      "detail": "dashboard.html not found in project root.",
  }


@app.get("/health", tags=["System"])
def health_check():
  return {
      "status": "ONLINE",
      "service": "ThermoGuardAI Tactical Gateway",
      "ml_engine": "RF-v2.0 Active",
      "database": "PostgreSQL 16 / PostGIS",
      "scheduler": "APScheduler 6-Hour Active",
  }


# 5. Machine Learning Inference Endpoints
@app.post("/predict", tags=["Machine Learning"])
def predict_anomaly(
    payload: HotspotTelemetry, background_tasks: BackgroundTasks
):
  try:
    input_data = payload.model_dump()
    result = predictor_v2.predict_single(input_data)

    res_dict = (
        result
        if isinstance(result, dict)
        else (result.model_dump() if hasattr(result, "model_dump") else {})
    )
    combined = {**input_data, **res_dict}

    raw_score = combined.get("risk_score") or combined.get("risk") or 0.0
    try:
      score = float(raw_score)
      if 0.0 < score <= 1.0:
        score = score * 100.0
    except Exception:
      score = 0.0

    if score >= 70.0 or "CRITICAL" in str(combined).upper():
      background_tasks.add_task(dispatch_webhook_task, combined, score)
    else:
      print(f"[Discord] Score {score:.1f} below threshold, skipping alert.")

    return result
  except Exception as e:
    print(f"[Inference Pipeline Error]: {e}")
    raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", tags=["Machine Learning"])
def predict_batch_endpoint(payloads: List[HotspotTelemetry]):
  try:
    records = [p.model_dump() for p in payloads]
    return predictor_v2.predict_batch(records)
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
  import uvicorn

  uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
