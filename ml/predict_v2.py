import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import numpy as np
import pandas as pd
from ml.feature_engineering_v2 import ThermoGuardFeatureTransformerV2

MODEL_V2_PATH = "ml/models/thermoguard_rf_v2.pkl"

class ThermoGuardPredictorV2:
    def __init__(self):
        if not os.path.exists(MODEL_V2_PATH):
            raise FileNotFoundError(f"RF-v2 model not found at {MODEL_V2_PATH}")
        self.model = joblib.load(MODEL_V2_PATH)
        self.transformer = ThermoGuardFeatureTransformerV2()
        self.classes = self.model.classes_

    def calculate_risk(self, data: dict, prediction: str, confidence: float) -> dict:
        frp = float(data.get("frp", 0.0))
        dist = float(data.get("distance_to_facility_km", 999.0))

        # 1. Thermal Intensity (0 - 40 pts)
        s_thermal = min(frp / 200.0, 1.0) * 40.0

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
            "AGRICULTURAL_FIRE": 2.0
        }
        s_threat = threat_weights.get(prediction, 5.0) * float(confidence)

        total_score = round(min(max(s_thermal + s_proximity + s_threat, 0.0), 100.0), 1)

        if total_score >= 75:
            tier = "CRITICAL"
            color = "#EF4444"
        elif total_score >= 50:
            tier = "HIGH"
            color = "#F97316"
        elif total_score >= 25:
            tier = "MODERATE"
            color = "#FBBF24"
        else:
            tier = "LOW"
            color = "#10B981"

        return {
            "score": total_score,
            "tier": tier,
            "color": color
        }

    def generate_explanation(self, record, prediction, confidence):
        dist = float(record.get("distance_to_facility_km", 999.0))
        frp = float(record.get("frp", 0.0))
        pers = int(record.get("persistence_count_30d", 1))

        if prediction == "CRITICAL_ACCIDENTAL":
            return f"Critical threat: Thermal emission ({frp:.1f} MW) within {dist:.2f} km of industrial site without historical recurrence."
        elif prediction == "INDUSTRIAL_FLARE":
            return f"Operational signature: {frp:.1f} MW emission within industrial perimeter ({dist:.2f} km) with {pers}-day recurrence."
        elif prediction == "AGRICULTURAL_FIRE":
            return f"Open-land signature: Low-intensity rural detection ({frp:.1f} MW) located {dist:.1f} km from registered facilities."
        elif prediction == "WILDFIRE_BIOMASS":
            loc = f"within {dist:.2f} km of industrial zone" if dist <= 5.0 else "in rural perimeter"
            return f"Elevated thermal signature ({frp:.1f} MW) detected {loc}; evaluated as high-intensity biomass combustion."
        return "Standard thermal detection evaluated by RF-v2.0 ensemble."

    def predict_single(self, data: dict) -> dict:
        df = pd.DataFrame([data])
        features = self.transformer.transform(df)

        probabilities = self.model.predict_proba(features)[0]
        max_idx = np.argmax(probabilities)
        prediction = self.classes[max_idx]
        confidence = float(probabilities[max_idx])

        prob_dict = {cls: round(float(p), 4) for cls, p in zip(self.classes, probabilities)}
        risk = self.calculate_risk(data, prediction, confidence)
        explanation = self.generate_explanation(data, prediction, confidence)

        return {
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "probabilities": prob_dict,
            "risk_factor": risk,
            "explanation": explanation,
            "model_version": "RF-v2.0"
        }

predictor_v2 = ThermoGuardPredictorV2()