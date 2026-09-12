import os
import joblib
import pandas as pd

MODEL_PATH = "ml/models/thermoguard_rf.pkl"

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}. Run train_model.py first.")

bundle = joblib.load(MODEL_PATH)
pipeline = bundle["pipeline"]
classes = bundle["classes"]
version = bundle.get("model_version", "RF-v1.0")


def predict_hotspot(record: dict) -> dict:
    """
    Accepts a single telemetry dictionary and returns class probabilities
    plus a non-causal feature-attribution explanation.
    """
    df_input = pd.DataFrame([record])
    probs = pipeline.predict_proba(df_input)[0]
    pred_idx = probs.argmax()
    predicted_class = classes[pred_idx]
    confidence = float(probs[pred_idx])

    prob_dict = {cls_name: round(float(prob), 4) for cls_name, prob in zip(classes, probs)}

    # Build non-causal feature-based narrative
    reasons = []
    frp_val = float(record.get("frp", 0.0))
    dist_val = record.get("distance_to_facility_km")
    rec_val = int(record.get("persistence_count_30d", 1))

    if dist_val is not None and float(dist_val) <= 5.0:
        reasons.append(f"spatial proximity to an industrial facility ({dist_val} km)")
    else:
        reasons.append("rural coordinates beyond active industrial buffers")

    if frp_val >= 150.0:
        reasons.append(f"very high radiative power ({frp_val} MW)")
    elif frp_val < 30.0:
        reasons.append(f"low-intensity thermal signature ({frp_val} MW)")

    if rec_val >= 3:
        reasons.append(f"repeated temporal persistence ({rec_val} recorded events)")
    else:
        reasons.append("isolated/spontaneous thermal occurrence")

    explanation = (
        f"Event labeled as {predicted_class} primarily based on: "
        + "; ".join(reasons)
        + ". (Note: Statistical feature correlation, not verified physical causality)."
    )

    return {
        "prediction": predicted_class,
        "confidence": round(confidence, 4),
        "probabilities": prob_dict,
        "model_version": version,
        "explanation": explanation
    }


if __name__ == "__main__":
    # Test 1: Industrial Event
    sample_industrial = {
        "latitude": 22.4707,
        "longitude": 70.0577,
        "frp": 310.0,
        "brightness_k": 382.4,
        "distance_to_facility_km": 0.42,
        "persistence_count_30d": 1,
        "acq_timestamp_ist": "2026-09-12 18:45:00 IST"
    }
    print("Industrial Test Sample Output:")
    print(predict_hotspot(sample_industrial))

    # Test 2: Agricultural Event
    sample_agri = {
        "latitude": 26.85,
        "longitude": 80.90,
        "frp": 14.5,
        "brightness_k": 312.0,
        "distance_to_facility_km": None,
        "persistence_count_30d": 1,
        "acq_timestamp_ist": "2026-09-12 14:15:00 IST"
    }
    print("\nAgricultural Test Sample Output:")
    print(predict_hotspot(sample_agri))