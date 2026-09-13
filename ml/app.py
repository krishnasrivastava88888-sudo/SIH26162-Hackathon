import os
import sys
from datetime import datetime
from typing import Optional

import joblib
import pandas as pd
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ============================================================
# PATHS
# ============================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

sys.path.append(CURRENT_DIR)
sys.path.append(PROJECT_ROOT)


# ============================================================
# ML MODEL
# ============================================================

MODEL_PATH = os.path.join(
    CURRENT_DIR,
    "models",
    "thermoguard_rf.pkl"
)

bundle = joblib.load(MODEL_PATH)

pipeline = bundle["pipeline"]
classes = bundle["classes"]
model_version = bundle.get("model_version", "RF-v1.0")


# ============================================================
# DATABASE CONFIG
# ============================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "thermoguard")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD" )

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="ThermoGuard AI API",
    description="ThermoGuard AI ML + PostgreSQL/PostGIS API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MODELS
# ============================================================

class HotspotInput(BaseModel):
    latitude: float
    longitude: float
    frp: float
    brightness_k: float
    distance_to_facility_km: Optional[float] = None
    persistence_count_30d: int = 1
    acq_timestamp_ist: Optional[str] = None


class PredictionResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: dict
    model_version: str
    explanation: str


class HealthResponse(BaseModel):
    status: str
    model_version: str
    supported_classes: list
    timestamp_utc: str


# ============================================================
# ML EXPLANATION
# ============================================================

def build_explanation(data: HotspotInput) -> str:

    reasons = []

    if data.distance_to_facility_km is not None:
        if data.distance_to_facility_km <= 2:
            reasons.append("very close to an industrial facility")
        elif data.distance_to_facility_km <= 10:
            reasons.append("near an industrial facility")

    if data.frp >= 100:
        reasons.append("high fire radiative power")

    if data.persistence_count_30d >= 3:
        reasons.append("repeated thermal activity")

    if not reasons:
        return "Classification based on thermal hotspot characteristics."

    return "Classification influenced by " + ", ".join(reasons) + "."


# ============================================================
# HEALTH
# ============================================================

@app.get("/health", response_model=HealthResponse)
def health():

    return HealthResponse(
        status="healthy",
        model_version=model_version,
        supported_classes=list(classes),
        timestamp_utc=datetime.utcnow().isoformat()
    )


# ============================================================
# DATABASE TEST
# ============================================================

@app.get("/api/db-test")
def database_test():

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1;")
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return {
            "status": "connected",
            "database": DB_NAME,
            "result": result[0]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )


# ============================================================
# HOTSPOTS FROM POSTGRESQL
# ============================================================

@app.get("/api/hotspots")
def get_hotspots():

    query = """
        SELECT
            a.id,
            a.latitude,
            a.longitude,
            a.frp,
            a.brightness_k,
            a.satellite,
            TO_CHAR(
                a.acq_timestamp_ist,
                'YYYY-MM-DD HH24:MI:SS'
            ) || ' IST' AS acq_timestamp_ist,
            a.persistence_count_30d,

            e.nearest_facility,
            e.distance_to_facility_km,
            e.classification,
            e.severity,
            e.confidence_score,
            e.ml_prediction,
            e.ml_confidence,
            e.ml_explanation

        FROM thermal_anomalies a

        LEFT JOIN classified_events e
            ON e.anomaly_id = a.id

        ORDER BY a.acq_timestamp_ist DESC;
    """

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(query)

        columns = [desc[0] for desc in cursor.description]

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        data = []

        for row in rows:

            item = dict(zip(columns, row))

            data.append(item)

        return data

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch hotspots: {str(e)}"
        )


# ============================================================
# INDUSTRIAL SITES
# ============================================================

@app.get("/api/industrial-sites")
def get_industrial_sites():

    query = """
        SELECT
            id,
            name,
            latitude,
            longitude
        FROM industrial_sites
        ORDER BY id;
    """

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(query)

        columns = [desc[0] for desc in cursor.description]

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch industrial sites: {str(e)}"
        )


# ============================================================
# ALERTS
# ============================================================

@app.get("/api/alerts")
def get_alerts():

    query = """
        SELECT
            id,
            event_id,
            severity,
            message,
            status,
            created_at
        FROM alerts
        ORDER BY created_at DESC, id DESC;
    """

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(query)

        columns = [desc[0] for desc in cursor.description]

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch alerts: {str(e)}"
        )


# ============================================================
# STATISTICS
# ============================================================

@app.get("/api/stats")
def get_stats():

    query = """
        SELECT
            (SELECT COUNT(*) FROM thermal_anomalies) AS total_anomalies,
            (SELECT COUNT(*) FROM classified_events) AS total_events,
            (SELECT COUNT(*) FROM industrial_sites) AS industrial_sites,
            (SELECT COUNT(*) FROM alerts) AS alerts;
    """

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(query)

        row = cursor.fetchone()

        cursor.close()
        conn.close()

        return {
            "total_anomalies": row[0],
            "total_events": row[1],
            "industrial_sites": row[2],
            "alerts": row[3]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


# ============================================================
# ML PREDICTION
# ============================================================

@app.post("/predict", response_model=PredictionResponse)
def predict(data: HotspotInput):

    features = pd.DataFrame([{
        "latitude": data.latitude,
        "longitude": data.longitude,
        "frp": data.frp,
        "brightness_k": data.brightness_k,
        "distance_to_facility_km": data.distance_to_facility_km,
        "persistence_count_30d": data.persistence_count_30d
    }])

    prediction = pipeline.predict(features)[0]

    probabilities_array = pipeline.predict_proba(features)[0]

    probabilities = {
        str(cls): float(prob)
        for cls, prob in zip(classes, probabilities_array)
    }

    confidence = float(max(probabilities_array))

    explanation = build_explanation(data)

    return PredictionResponse(
        prediction=str(prediction),
        confidence=confidence,
        probabilities=probabilities,
        model_version=model_version,
        explanation=explanation
    )


# ============================================================
# BATCH PREDICTION
# ============================================================

@app.post("/predict/batch")
def predict_batch(data: list[HotspotInput]):

    if not data:
        return []

    features = pd.DataFrame([
        {
            "latitude": item.latitude,
            "longitude": item.longitude,
            "frp": item.frp,
            "brightness_k": item.brightness_k,
            "distance_to_facility_km": item.distance_to_facility_km,
            "persistence_count_30d": item.persistence_count_30d
        }
        for item in data
    ])

    predictions = pipeline.predict(features)

    probabilities_array = pipeline.predict_proba(features)

    results = []

    for i, prediction in enumerate(predictions):

        probabilities = {
            str(cls): float(prob)
            for cls, prob in zip(
                classes,
                probabilities_array[i]
            )
        }

        confidence = float(
            max(probabilities_array[i])
        )

        results.append({
            "prediction": str(prediction),
            "confidence": confidence,
            "probabilities": probabilities,
            "model_version": model_version
        })

    return results


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )