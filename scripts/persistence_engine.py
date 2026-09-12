import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

# --- Setup project imports ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
ML_DIR = os.path.join(PROJECT_ROOT, "ml")

for p in [PROJECT_ROOT, ML_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import joblib
import pandas as pd
from webhook_notifier import dispatch_critical_alert

PROXIMITY_THRESHOLD_KM = 5.0
LOOKBACK_DAYS = 30
GRID_PRECISION_DEG = 0.015  # ~1.6 km spatial binning
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))

MEMORY_FILE_PATH = "data/processed/temporal_memory.json"
OSM_GEOJSON_PATH = "gis/osm/lucknow_industrial_sites.geojson"
RAW_FIRMS_PATH = "data/raw/firms_india.csv"
OUTPUT_CSV_PATH = "data/processed/classified_hotspots.csv"
OUTPUT_JSON_PATH = "data/processed/classified_hotspots.json"
MODEL_PATH = os.path.join(ML_DIR, "models", "thermoguard_rf.pkl")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two coordinates in kilometers."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def get_spatial_grid_key(lat: float, lon: float) -> str:
    """Bins coordinates into a grid cell key for recurrence tracking."""
    lat_bin = round(lat / GRID_PRECISION_DEG) * GRID_PRECISION_DEG
    lon_bin = round(lon / GRID_PRECISION_DEG) * GRID_PRECISION_DEG
    return f"{lat_bin:.3f}_{lon_bin:.3f}"


def load_industrial_assets(geojson_path: str) -> list:
    """Loads industrial asset centroids from OpenStreetMap GeoJSON."""
    if not os.path.exists(geojson_path):
        return []
    with open(geojson_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    assets = []
    for feat in data.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            props = feat.get("properties", {})
            assets.append({
                "name": props.get("name", "Industrial Asset"),
                "lon": float(coords[0]),
                "lat": float(coords[1]),
                "type": props.get("landuse") or props.get("power") or "industrial",
            })
    return assets


def build_ml_explanation(record: dict, predicted_class: str) -> str:
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


def run_classification_pipeline():
    os.makedirs("data/processed", exist_ok=True)

    if not os.path.exists(RAW_FIRMS_PATH):
        raise FileNotFoundError(f"Missing FIRMS dataset at {RAW_FIRMS_PATH}.")

    firms_df = pd.read_csv(RAW_FIRMS_PATH)
    industrial_sites = load_industrial_assets(OSM_GEOJSON_PATH)

    # 1. Spatially index occurrence frequency
    spatial_recurrence = {}
    for _, r in firms_df.iterrows():
        key = get_spatial_grid_key(float(r["latitude"]), float(r["longitude"]))
        spatial_recurrence[key] = spatial_recurrence.get(key, 0) + 1

    now_utc = datetime.now(timezone.utc)

    # Hackathon demo injection: Jamnagar industrial hazard
    demo_accident = pd.DataFrame([{
        "latitude": 22.4707,
        "longitude": 70.0577,
        "bright_ti4": 382.4,
        "frp": 310.0,
        "satellite": "VIIRS_NOAA21_NRT",
        "acq_date": now_utc.strftime("%Y-%m-%d"),
        "acq_time": "1845",
        "confidence": "high",
    }])
    firms_df = pd.concat([demo_accident, firms_df], ignore_index=True)

    # 2. Rule-Based Classification Pass
    records_pre_ml = []
    for _, row in firms_df.iterrows():
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        frp = float(row.get("frp", 0.0))
        brightness = float(row.get("bright_ti4", 0.0))
        satellite = str(row.get("satellite", "VIIRS_NOAA21"))
        acq_date = str(row.get("acq_date", now_utc.strftime("%Y-%m-%d")))
        acq_time = str(row.get("acq_time", "0000")).zfill(4)

        nearest_site_name = None
        min_dist_km = float("inf")
        for site in industrial_sites:
            dist = haversine_distance(lat, lon, site["lat"], site["lon"])
            if dist < min_dist_km:
                min_dist_km = dist
                nearest_site_name = site["name"]

        is_industrial_zone = min_dist_km <= PROXIMITY_THRESHOLD_KM
        facility_label = (
            nearest_site_name if is_industrial_zone else "None (Open / Rural Area)"
        )
        distance_val = round(min_dist_km, 2) if is_industrial_zone else None

        grid_key = get_spatial_grid_key(lat, lon)
        recurrence_count = spatial_recurrence.get(grid_key, 1)

        # Rule Engine
        if is_industrial_zone:
            if frp >= 200.0 or brightness >= 375.0:
                classification = "CRITICAL_ACCIDENTAL"
                severity = "CRITICAL"
                confidence = 0.98
            else:
                classification = "INDUSTRIAL_FLARE"
                severity = "LOW"
                confidence = 0.92
        else:
            if frp < 30.0:
                classification = "AGRICULTURAL_FIRE"
                severity = "MODERATE"
                confidence = 0.88
            else:
                classification = "WILDFIRE_BIOMASS"
                severity = "HIGH"
                confidence = 0.85

        time_hr, time_min = int(acq_time[:2]), int(acq_time[2:])
        detection_dt = datetime.strptime(acq_date, "%Y-%m-%d").replace(
            hour=time_hr, minute=time_min, tzinfo=timezone.utc
        ).astimezone(IST_OFFSET)

        record = {
            "id": hashlib.md5(f"{lat}_{lon}_{acq_date}_{acq_time}".encode()).hexdigest()[:10],
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "frp": round(frp, 2),
            "brightness_k": round(brightness, 2),
            "satellite": satellite,
            "acq_timestamp_ist": detection_dt.strftime("%Y-%m-%d %H:%M:%S IST"),
            "persistence_count_30d": recurrence_count,
            "nearest_facility": facility_label,
            "distance_to_facility_km": distance_val,
            "classification": classification,
            "severity": severity,
            "confidence_score": round(confidence, 2),
        }
        records_pre_ml.append(record)

    # 3. Dynamic ML Scoring Pass
    print(f"Loading ML model artifact from '{MODEL_PATH}'...")
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model file {MODEL_PATH} not found. Train first via train_model.py")

    bundle = joblib.load(MODEL_PATH)
    ml_pipeline = bundle["pipeline"]
    ml_classes = bundle["classes"]

    # Convert records to DataFrame for batch vector scoring
    df_for_ml = pd.DataFrame(records_pre_ml)
    print("Running high-throughput ML inference...")
    prob_matrix = ml_pipeline.predict_proba(df_for_ml)

    classified_records = []
    critical_alerts = []

    for idx, row_dict in enumerate(records_pre_ml):
        probs = prob_matrix[idx]
        best_idx = probs.argmax()
        ml_prediction = ml_classes[best_idx]
        ml_confidence = float(probs[best_idx])
        ml_explanation = build_ml_explanation(row_dict, ml_prediction)

        # Append ML outputs to schema
        row_dict["ml_prediction"] = ml_prediction
        row_dict["ml_confidence"] = round(ml_confidence, 4)
        row_dict["ml_explanation"] = ml_explanation

        classified_records.append(row_dict)

        # Hybrid Decision Logic for Notifications:
        # Trigger if rule-based == 'CRITICAL_ACCIDENTAL' OR ML flags critical with confidence >= 0.35
        rule_is_critical = (row_dict["classification"] == "CRITICAL_ACCIDENTAL")
        ml_is_critical = (ml_prediction == "CRITICAL_ACCIDENTAL" and ml_confidence >= 0.35)

        if rule_is_critical or ml_is_critical:
            critical_alerts.append(row_dict)

    # 4. Save Processed Artifacts
    out_df = pd.DataFrame(classified_records)
    out_df.to_csv(OUTPUT_CSV_PATH, index=False)

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(classified_records, f, indent=2)

    print(f"\nPipeline successfully scored {len(classified_records)} thermal events.")
    print(f"Results written to:\n  - {OUTPUT_CSV_PATH}\n  - {OUTPUT_JSON_PATH}")
    print("\nML Classification Distribution:")
    print(out_df["ml_prediction"].value_counts().to_dict())

    # 5. Dispatch Alert Notifications
    if critical_alerts:
        print(f"\nIdentified {len(critical_alerts)} high-priority events. Evaluating alerts...")
        for alert in critical_alerts:
            dispatch_critical_alert(alert)


if __name__ == "__main__":
    run_classification_pipeline()