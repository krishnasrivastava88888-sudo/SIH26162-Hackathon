import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml.feature_engineering_v2 import FEATURE_COLUMNS_V2, ThermoGuardFeatureTransformerV2

# [FIX]: Point to the verified CSV that has the flat distance_to_facility_km column
DATA_PATH = "ml/data/training_data.csv"
MODEL_V1_PATH = "ml/models/thermoguard_rf.pkl"
MODEL_V2_PATH = "ml/models/thermoguard_rf_v2.pkl"
METRICS_PATH = "ml/models/rf_v2_evaluation.json"

def run_training_pipeline():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Missing dataset at {DATA_PATH}.")

    # Load directly from the CSV
    df = pd.read_csv(DATA_PATH)
    
    # --- BULLETPROOF DATA AUGMENTATION ---
    majority_class = df["classification"].value_counts().idxmax()
    
    minority_mask = df["classification"] != majority_class
    minority_df = df[minority_mask]
    majority_df = df[~minority_mask]
    
    print(f"[*] Majority class ignored for boosting: '{majority_class}'")
    print(f"[*] Minority hazards being boosted: {minority_df['classification'].unique().tolist()}")
    
    # Duplicate the rare minority records 50 times to force spatial feature utilization
    augmented_minority = pd.concat([minority_df] * 50, ignore_index=True)
    df_balanced = pd.concat([majority_df, augmented_minority], ignore_index=True)
    
    print(f"[*] Augmented dataset shape: {len(df_balanced)} records.")

    y = df_balanced["classification"].astype(str)
    
    transformer = ThermoGuardFeatureTransformerV2()
    X = transformer.transform(df_balanced)

    # Stratified split ensures critical hazards are tested
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    print(f"[*] Train set: {len(X_train)} samples | Test set: {len(X_test)} samples")

    clf_v2 = RandomForestClassifier(
        n_estimators=150,
        max_depth=10,
        min_samples_split=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    clf_v2.fit(X_train, y_train)
    y_pred_v2 = clf_v2.predict(X_test)

    # Evaluation
    macro_f1_v2 = f1_score(y_test, y_pred_v2, average="macro", zero_division=0)
    print("\n" + "=" * 50)
    print(f"RF-v2.0 CLASSIFICATION REPORT (Macro-F1: {macro_f1_v2:.4f})")
    print("=" * 50)
    print(classification_report(y_test, y_pred_v2, zero_division=0))

    # Feature Importance
    importances = clf_v2.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("\n[*] RF-v2.0 Feature Importances:")
    for idx in sorted_idx:
        print(f"  - {FEATURE_COLUMNS_V2[idx]}: {importances[idx]:.4f}")

    os.makedirs("ml/models", exist_ok=True)
    joblib.dump(clf_v2, MODEL_V2_PATH)
    print(f"\n[+] Saved model artifact to {MODEL_V2_PATH}")

    # Fix dict-loading issue for baseline model comparison
    comparison = {"model_v2": {"macro_f1": float(macro_f1_v2)}}
    if os.path.exists(MODEL_V1_PATH):
        try:
            v1_obj = joblib.load(MODEL_V1_PATH)
            clf_v1 = v1_obj.get("model") if isinstance(v1_obj, dict) else v1_obj
            
            if hasattr(clf_v1, "n_features_in_") and X_test.shape[1] >= clf_v1.n_features_in_:
                y_pred_v1 = clf_v1.predict(X_test[:, :clf_v1.n_features_in_])
                macro_f1_v1 = f1_score(y_test, y_pred_v1, average="macro", zero_division=0)
                comparison["model_v1"] = {"macro_f1": float(macro_f1_v1)}
                print(f"[*] Comparative Baseline: RF-v1.0 Macro-F1 = {macro_f1_v1:.4f} vs RF-v2.0 Macro-F1 = {macro_f1_v2:.4f}")
        except Exception as e:
            print(f"[*] Baseline RF-v1 comparison skipped: {e}")

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

if __name__ == "__main__":
    run_training_pipeline()