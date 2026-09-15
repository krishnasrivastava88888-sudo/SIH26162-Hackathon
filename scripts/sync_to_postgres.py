import hashlib
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

load_dotenv()


def clean_timestamp(ts_str):
  """Strips ' IST' and handles ISO timestamp conversion for PostgreSQL."""
  if not ts_str:
    return datetime.now()
  cleaned = re.sub(r"\s+IST", "", str(ts_str)).strip()
  try:
    return datetime.fromisoformat(cleaned)
  except ValueError:
    return datetime.now()


def generate_hotspot_id(r: dict) -> str:
  """Generates a deterministic 10-char hex identifier if 'id' is absent."""
  if r.get("id"):
    return str(r["id"])
  seed = (
      f"{float(r['latitude']):.4f}_{float(r['longitude']):.4f}_{float(r.get('frp', 0)):.1f}"
  )
  return hashlib.md5(seed.encode("utf-8")).hexdigest()[:10]


def sync_enriched_hotspots():
  json_path = "data/processed/enriched_hotspots.json"
  if not os.path.exists(json_path):
    raise FileNotFoundError(
        f"Missing enriched dataset at {json_path}. Run spatial analysis first."
    )

  with open(json_path, "r", encoding="utf-8") as f:
    records = json.load(f)

  conn = psycopg2.connect(
      host=os.getenv("DB_HOST", "localhost"),
      port=os.getenv("DB_PORT", "5432"),
      database=os.getenv("DB_NAME", "thermoguard"),
      user=os.getenv("DB_USER", "postgres"),
      password=os.getenv("DB_PASSWORD"),
  )
  cur = conn.cursor()

  print(f"[*] Synchronizing {len(records)} enriched records into PostgreSQL...")

  # Replace the previous hotspot snapshot so stale records are removed.
  # Replace the previous hotspot snapshot so stale records are removed.`r`n  cur.execute("DELETE FROM classified_events;")
  cur.execute("DELETE FROM thermal_anomalies;")

  print("[*] Cleared previous hotspot snapshot.")

  synced_count = 0
  for r in records:
    rec_id = generate_hotspot_id(r)
    ts = clean_timestamp(r.get("acq_timestamp_ist") or r.get("acq_date"))

    # Extract distance and confidence with fallbacks
    distance = r.get("distance_km")
    if distance is None:
      distance = r.get("distance_to_facility_km")
    dist_val = float(distance) if distance is not None else None

    raw_conf = r.get("confidence_score") or r.get("confidence") or 0.8
    try:
      conf_val = float(raw_conf)
      if conf_val > 1.0:
        conf_val = conf_val / 100.0  # Normalize percentage to 0-1 range
    except (ValueError, TypeError):
      conf_val = 0.8

    fac_name = (
        r.get("nearest_facility_name")
        or r.get("nearest_facility")
        or "None (Open / Rural Area)"
    )
    risk_zone_val = str(r.get("risk_zone") or r.get("industrial_relevance", "LOW"))
    explanation = r.get("ml_explanation") or (
        f"Event labeled as {r.get('classification', 'UNKNOWN')} with proximity"
        f" {dist_val:.2f} km."
        if dist_val is not None
        else "Evaluated by ThermoGuard geospatial pipeline."
    )

    # 1. Upsert into thermal_anomalies
    cur.execute(
        """
            INSERT INTO thermal_anomalies (
                id, latitude, longitude, frp, brightness_k, satellite,
                acq_timestamp_ist, persistence_count_30d, cluster_id, cluster_size, risk_zone, geom
            ) VALUES (
                %(id)s, %(lat)s, %(lon)s, %(frp)s, %(bright)s, %(sat)s,
                %(ts)s, %(pers)s, %(cluster_id)s, %(cluster_size)s, %(risk_zone)s,
                ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
            )
            ON CONFLICT (id) DO UPDATE SET
                frp = EXCLUDED.frp,
                brightness_k = EXCLUDED.brightness_k,
                cluster_id = EXCLUDED.cluster_id,
                cluster_size = EXCLUDED.cluster_size,
                risk_zone = EXCLUDED.risk_zone,
                persistence_count_30d = EXCLUDED.persistence_count_30d;
        """,
        {
            "id": rec_id,
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
            "frp": float(r["frp"]),
            "bright": float(r["brightness_k"]),
            "sat": r.get("satellite", "VIIRS_NOAA21_NRT"),
            "ts": ts,
            "pers": int(r.get("persistence_count_30d", 1)),
            "cluster_id": str(r.get("cluster_id", "SINGLETON")),
            "cluster_size": int(r.get("cluster_size", 1)),
            "risk_zone": risk_zone_val,
        },
    )

    # 2. Upsert into classified_events
    cur.execute(
        """
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
                classification = EXCLUDED.classification,
                severity = EXCLUDED.severity,
                confidence_score = EXCLUDED.confidence_score,
                industrial_relevance = EXCLUDED.industrial_relevance,
                cluster_id = EXCLUDED.cluster_id,
                ml_explanation = EXCLUDED.ml_explanation;
        """,
        {
            "id": rec_id,
            "fac": fac_name,
            "dist": dist_val,
            "cls": str(r.get("classification", "UNKNOWN")),
            "sev": str(r.get("severity", "LOW")),
            "conf": conf_val,
            "ml_pred": str(
                r.get("ml_prediction") or r.get("classification", "UNKNOWN")
            ),
            "ml_conf": float(r.get("ml_confidence", conf_val)),
            "ml_exp": explanation,
            "rel": str(r.get("industrial_relevance", "LOW")),
            "cluster_id": str(r.get("cluster_id", "SINGLETON")),
        },
    )
    synced_count += 1

  conn.commit()
  cur.close()
  conn.close()
  print(
      f"✓ Successfully synchronized {synced_count} GIS-enriched hotspots to"
      " PostgreSQL."
  )


if __name__ == "__main__":
  sync_enriched_hotspots()
