import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

# --- Dynamic Path Resolution to prevent ModuleNotFoundError on unpickling ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

for path in [CURRENT_DIR, PROJECT_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Load Serialized Pipeline Bundle ---
MODEL_PATH = os.path.join(CURRENT_DIR, "models", "thermoguard_rf.pkl")

if not os.path.exists(MODEL_PATH):
    raise RuntimeError(
        f"Critical Failure: Model bundle not found at '{MODEL_PATH}'. "
        "Execute 'python ml/train_model.py' to generate the artifact."
    )

bundle = joblib.load(MODEL_PATH)
pipeline = bundle["pipeline"]
classes: List[str] = bundle["classes"]
model_version: str = bundle.get("model_version", "RF-v1.0")

# --- App Initialization ---
app = FastAPI(
    title="ThermoGuard AI - Thermal Anomaly ML Microservice",
    description="Operational REST API for real-time industrial fire and flare discrimination (SIH26162).",
    version=model_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic v2 Schemas ---
class HotspotInput(BaseModel):
    latitude: float = Field(..., description="WGS84 Latitude coordinate")
    longitude: float = Field(..., description="WGS84 Longitude coordinate")
    frp: float = Field(..., ge=0.0, description="Fire Radiative Power (MW)")
    brightness_k: float = Field(..., ge=0.0, description="Brightness temperature in Kelvin")
    distance_to_facility_km: Optional[float] = Field(
        None, description="Distance to nearest industrial facility in km"
    )
    persistence_count_30d: int = Field(
        1, ge=1, description="Number of distinct active days in 30-day baseline"
    )
    acq_timestamp_ist: Optional[str] = Field(
        None, description="Acquisition timestamp in IST (e.g., '2026-09-12 18:45:00 IST')"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 22.4707,
                "longitude": 70.0577,
                "frp": 310.0,
                "brightness_k": 382.4,
                "distance_to_facility_km": 0.42,
                "persistence_count_30d": 1,
                "acq_timestamp_ist": "2026-09-12 18:45:00 IST",
            }
        }
    }


class PredictionResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: Dict[str, float]
    model_version: str
    explanation: str


class HealthResponse(BaseModel):
    status: str
    model_version: str
    supported_classes: List[str]
    timestamp_utc: str


# --- Helper: Feature-Attribution Narrative Generator ---
def build_explanation(record: dict, predicted_class: str) -> str:
    reasons = []
    frp_val = float(record.get("frp", 0.0))
    dist_val = record.get("distance_to_facility_km")
    rec_val = int(record.get("persistence_count_30d", 1))

    if dist_val is not None and float(dist_val) <= 5.0:
        reasons.append(f"spatial proximity to an industrial facility ({float(dist_val):.2f} km)")
    else:
        reasons.append("rural coordinates beyond active industrial buffers")

    if frp_val >= 150.0:
        reasons.append(f"very high radiative power ({frp_val:.1f} MW)")
    elif frp_val < 30.0:
        reasons.append(f"low-intensity thermal signature ({frp_val:.1f} MW)")
    else:
        reasons.append(f"moderate thermal radiative power ({frp_val:.1f} MW)")

    if rec_val >= 3:
        reasons.append(f"repeated temporal persistence ({rec_val} recorded events)")
    else:
        reasons.append("isolated/spontaneous thermal occurrence")

    return (
        f"Event labeled as {predicted_class} primarily based on: "
        + "; ".join(reasons)
        + ". (Note: Statistical feature correlation, not verified physical causality)."
    )


# --- API Routes ---
@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
def health_check():
    """Returns microservice health, active model version, and class labels."""
    return HealthResponse(
        status="HEALTHY",
        model_version=model_version,
        supported_classes=classes,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/predict", response_model=PredictionResponse, tags=["Inference"])
def predict_single(hotspot: HotspotInput):
    """Classifies a single satellite thermal event with calibrated probabilities and explanation."""
    try:
        input_data = hotspot.model_dump()
        df_input = pd.DataFrame([input_data])

        probabilities = pipeline.predict_proba(df_input)[0]
        pred_idx = probabilities.argmax()
        predicted_class = classes[pred_idx]
        confidence = float(probabilities[pred_idx])

        prob_dict = {
            cls_name: round(float(prob), 4)
            for cls_name, prob in zip(classes, probabilities)
        }
        explanation = build_explanation(input_data, predicted_class)

        return PredictionResponse(
            prediction=predicted_class,
            confidence=round(confidence, 4),
            probabilities=prob_dict,
            model_version=model_version,
            explanation=explanation,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(e)}",
        )


@app.post("/predict/batch", response_model=List[PredictionResponse], tags=["Inference"])
def predict_batch(hotspots: List[HotspotInput]):
    """Batch-classifies a collection of thermal anomalies in a single pass."""
    if not hotspots:
        return []

    try:
        records = [h.model_dump() for h in hotspots]
        df_batch = pd.DataFrame(records)

        prob_matrix = pipeline.predict_proba(df_batch)
        results = []

        for idx, (record, probs) in enumerate(zip(records, prob_matrix)):
            pred_idx = probs.argmax()
            predicted_class = classes[pred_idx]
            confidence = float(probs[pred_idx])

            prob_dict = {
                cls_name: round(float(p), 4)
                for cls_name, p in zip(classes, probs)
            }
            explanation = build_explanation(record, predicted_class)

            results.append(
                PredictionResponse(
                    prediction=predicted_class,
                    confidence=round(confidence, 4),
                    probabilities=prob_dict,
                    model_version=model_version,
                    explanation=explanation,
                )
            )

        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch inference execution failed: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)