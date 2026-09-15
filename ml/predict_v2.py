import os
import sys

# Ensure root directory is on Python path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
  sys.path.insert(0, BASE_DIR)

import joblib
from ml.feature_engineering_v2 import ThermoGuardFeatureTransformerV2
import numpy as np
import pandas as pd

# Robust relative path resolution
MODEL_V2_PATH = os.path.join(
    os.path.dirname(__file__), "models", "thermoguard_rf_v2.pkl"
)
if not os.path.exists(MODEL_V2_PATH):
  MODEL_V2_PATH = os.path.join(
      BASE_DIR, "ml", "models", "thermoguard_rf_v2.pkl"
  )


class ThermoGuardPredictorV2:

  def __init__(self):
    if not os.path.exists(MODEL_V2_PATH):
      raise FileNotFoundError(f"RF-v2 model not found at {MODEL_V2_PATH}")
    self.model = joblib.load(MODEL_V2_PATH)
    self.transformer = ThermoGuardFeatureTransformerV2()
    self.classes = self.model.classes_

  def calculate_risk(
      self, data: dict, prediction: str, confidence: float
  ) -> dict:
    """Calculates composite risk score (0-100) using SIH Phase 7 rubric:

    - Thermal Intensity: up to 40 pts
    - Asset Proximity:   up to 35 pts
    - Threat Class:      up to 25 pts
    """
    raw_frp = data.get("frp")
    frp = float(raw_frp) if raw_frp is not None else 0.0

    raw_dist = data.get("distance_to_facility_km")
    dist = float(raw_dist) if raw_dist is not None else 999.0

    # 1. Thermal Intensity (0 - 40 pts, saturates at 200 MW)
    s_thermal = min(max(frp, 0.0) / 200.0, 1.0) * 40.0

    # 2. Asset Proximity (0 - 35 pts)
    if dist <= 0.5:
      s_proximity = 35.0
    elif dist >= 10.0:
      s_proximity = 0.0
    else:
      s_proximity = (1.0 - (dist - 0.5) / 9.5) * 35.0

    # 3. Model Threat Classification (0 - 25 pts)
    threat_weights = {
        "CRITICAL_ACCIDENTAL": 25.0,
        "WILDFIRE_BIOMASS": 15.0,
        "INDUSTRIAL_FLARE": 8.0,
        "AGRICULTURAL_FIRE": 2.0,
    }
    s_threat = threat_weights.get(prediction, 5.0) * float(confidence)

    total_score = round(
        min(max(s_thermal + s_proximity + s_threat, 0.0), 100.0), 1
    )

    if total_score >= 75.0:
      tier = "CRITICAL"
      color = "#EF4444"
    elif total_score >= 50.0:
      tier = "HIGH"
      color = "#F97316"
    elif total_score >= 25.0:
      tier = "MODERATE"
      color = "#FBBF24"
    else:
      tier = "LOW"
      color = "#10B981"

    return {
        "score": total_score,
        "tier": tier,
        "color": color,
        "breakdown": {
            "thermal_score": round(s_thermal, 1),
            "proximity_score": round(s_proximity, 1),
            "threat_score": round(s_threat, 1),
        },
    }

  def generate_explanation(
      self, record: dict, prediction: str, confidence: float
  ) -> str:
    """Human-readable, feature-grounded XAI reasoning for judges and operators."""
    raw_dist = record.get("distance_to_facility_km")
    dist = float(raw_dist) if raw_dist is not None else 999.0

    raw_frp = record.get("frp")
    frp = float(raw_frp) if raw_frp is not None else 0.0

    raw_pers = record.get("persistence_count_30d")
    pers = int(raw_pers) if raw_pers is not None else 1

    conf_pct = int(round(confidence * 100))

    if prediction == "CRITICAL_ACCIDENTAL":
      return (
          f"CRITICAL HAZARD ({conf_pct}% confidence): Severe thermal emission"
          f" ({frp:.1f} MW) within {dist:.2f} km of industrial facility with no"
          " planned operational recurrence."
      )
    elif prediction == "INDUSTRIAL_FLARE":
      return (
          f"Operational flare ({conf_pct}% confidence): Controlled {frp:.1f} MW"
          f" thermal emission inside industrial perimeter ({dist:.2f} km)"
          f" matching continuous operational baseline ({pers} detections in 30"
          " days)."
      )
    elif prediction == "AGRICULTURAL_FIRE":
      return (
          f"Rural open-burning ({conf_pct}% confidence): Typical low-intensity"
          f" stubble/agricultural signature ({frp:.1f} MW) located {dist:.1f}"
          " km from industrial infrastructure."
      )
    elif prediction == "WILDFIRE_BIOMASS":
      loc = (
          f"within {dist:.2f} km buffer of industrial perimeter"
          if dist <= 5.0
          else "in unmonitored rural sector"
      )
      return (
          f"Wildfire / Biomass fire ({conf_pct}% confidence): High-radiance"
          f" thermal front ({frp:.1f} MW) detected {loc}."
      )
    return f"Ensemble classification: {prediction} with {conf_pct}% confidence."

  def predict_single(self, data: dict) -> dict:
    """Runs end-to-end inference for a single hotspot dictionary."""
    return self.predict_batch([data])[0]

  def predict_batch(self, items: list) -> list:
    """High-throughput vectorized batch inference for multiple hotspot records."""
    if not items:
      return []

    df = pd.DataFrame(items)
    features = self.transformer.transform(df)
    probas = self.model.predict_proba(features)

    results = []
    for i, data in enumerate(items):
      probabilities = probas[i]
      max_idx = np.argmax(probabilities)
      prediction = self.classes[max_idx]
      confidence = float(probabilities[max_idx])

      prob_dict = {
          cls: round(float(p), 4) for cls, p in zip(self.classes, probabilities)
      }
      risk = self.calculate_risk(data, prediction, confidence)
      explanation = self.generate_explanation(data, prediction, confidence)

      results.append({
          "prediction": prediction,
          "confidence": round(confidence, 4),
          "probabilities": prob_dict,
          "risk_score": risk["score"],  # Direct access alias
          "risk_tier": risk["tier"],  # Direct access alias
          "risk_factor": risk,
          "explanation": explanation,
          "model_version": "RF-v2.0",
      })

    return results


predictor_v2 = ThermoGuardPredictorV2()