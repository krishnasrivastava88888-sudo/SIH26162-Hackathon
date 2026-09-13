import json
import os
import re
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def clean_timestamp(ts_str):
    """Strips ' IST' and handles standard datetime parsing for PostgreSQL."""
    if not ts_str:
        return None
    cleaned = re.sub(r'\s+IST', '', str(ts_str)).strip()
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None

def sync_enriched_hotspots():
    json_path = "data/processed/enriched_hotspots.json"
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Missing enriched dataset at {json_path}. Run 'python gis/run_member3.py' first.")

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "thermoguard"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    print(f"[*] Syncing {len(records)} enriched records into PostgreSQL...")

    for r in records:
        ts = clean_timestamp(r.get("acq_timestamp_ist"))
        
        # 1. Upsert into thermal_anomalies
        cur.execute("""
            INSERT INTO thermal_anomalies (
                id, latitude, longitude, frp, brightness_k, satellite,
                acq_timestamp_ist, persistence_count_30d, cluster_id, cluster_size, risk_zone, geom
            ) VALUES (
                %(id)s, %(lat)s, %(lon)s, %(frp)s, %(bright)s, %(sat)s,
                %(ts)s, %(pers)s, %(cluster_id)s, %(cluster_size)s, %(risk_zone)s,
                ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
            )
            ON CONFLICT (id) DO UPDATE SET
                cluster_id = EXCLUDED.cluster_id,
                cluster_size = EXCLUDED.cluster_size,
                risk_zone = EXCLUDED.risk_zone,
                persistence_count_30d = EXCLUDED.persistence_count_30d;
        """, {
            "id": str(r["id"]),
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
            "frp": float(r["frp"]),
            "bright": float(r["brightness_k"]),
            "sat": r.get("satellite", "VIIRS_NOAA21"),
            "ts": ts,
            "pers": int(r.get("persistence_count_30d", 1)),
            "cluster_id": str(r.get("cluster_id", "SINGLETON")),
            "cluster_size": int(r.get("cluster_size", 1)),
            "risk_zone": str(r.get("risk_zone") or r.get("industrial_relevance", "LOW"))
        })

        # 2. Upsert into classified_events
        cur.execute("""
            INSERT INTO classified_events (
                id, anomaly_id, nearest_facility, distance_to_facility_km,
                classification, severity, confidence_score, ml_prediction,
                ml_confidence, ml_explanation, industrial_relevance, cluster_id
            ) VALUES (
                %(id)s, %(id)s, %(fac)s, %(dist)s,
                %(cls)s, %(sev)s, %(conf)s, %(ml_pred)s,
                %(ml_conf)s, %(ml_exp)s, %(rel)s, %(cluster_id)s
            )
            ON CONFLICT (id) DO UPDATE SET
                nearest_facility = EXCLUDED.nearest_facility,
                distance_to_facility_km = EXCLUDED.distance_to_facility_km,
                industrial_relevance = EXCLUDED.industrial_relevance,
                cluster_id = EXCLUDED.cluster_id;
        """, {
            "id": str(r["id"]),
            "fac": str(r.get("nearest_facility", "None (Open / Rural Area)")),
            "dist": float(r["distance_to_facility_km"]) if r.get("distance_to_facility_km") is not None else None,
            "cls": str(r.get("classification", "UNKNOWN")),
            "sev": str(r.get("severity", "LOW")),
            "conf": float(r.get("confidence_score", 0.8)),
            "ml_pred": r.get("ml_prediction"),
            "ml_conf": float(r["ml_confidence"]) if r.get("ml_confidence") is not None else None,
            "ml_exp": r.get("ml_explanation"),
            "rel": str(r.get("industrial_relevance", "LOW")),
            "cluster_id": str(r.get("cluster_id", "SINGLETON"))
        })

    conn.commit()
    cur.close()
    conn.close()
    print("✓ Successfully synchronized GIS-enriched hotspots to PostgreSQL.")

if __name__ == "__main__":
    sync_enriched_hotspots()