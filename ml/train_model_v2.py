import os
import sys

# Ensure project root is in sys.path regardless of execution method
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupKFold

from ml.feature_engineering_v2 import FEATURE_COLUMNS_V2, ThermoGuardFeatureTransformerV2

DATA_PATH = "data/processed/enriched_hotspots.json"
MODEL_V1_PATH = "ml/models/thermoguard_rf.pkl"
MODEL_V2_PATH = "ml/models/thermoguard_rf_v2.pkl"
METRICS_PATH = "ml/models/rf_v2_evaluation.json"

def run_training_pipeline():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Missing dataset at {DATA_PATH}. Run gis/run_member3.py first.")

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    df = pd.DataFrame(records)
    print(f"[*] Loaded {len(df)} records for RF-v2 training.")

    # Target assignment
    y = df["classification"].astype(str)
    
    # Feature extraction via V2 transformer
    transformer = ThermoGuardFeatureTransformerV2()
    X = transformer.transform(df)

    # Prevent spatial auto-correlation leakage: Group K-Fold by cluster_id
    groups = df["cluster_id"].fillna("SINGLETON").astype(str)
    gkf = GroupKFold(n_splits=5)
    train_idx, test_idx = next(gkf.split(X, y, groups=groups))

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    print(f"[*] Train set: {len(X_train)} samples | Test set: {len(X_test)} samples (clustered)")

    # Balanced class weights for low-frequency accidental/flare categories
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

    # Persist RF-v2 without modifying RF-v1
    os.makedirs("ml/models", exist_ok=True)
    joblib.dump(clf_v2, MODEL_V2_PATH)
    print(f"\n✓ Saved model artifact to {MODEL_V2_PATH}")

    # Evaluate against baseline RF-v1 on the same test fold
    comparison = {"model_v2": {"macro_f1": float(macro_f1_v2)}}
    if os.path.exists(MODEL_V1_PATH):
        try:
            clf_v1 = joblib.load(MODEL_V1_PATH)
            y_pred_v1 = clf_v1.predict(X_test[:, :7])
            macro_f1_v1 = f1_score(y_test, y_pred_v1, average="macro", zero_division=0)
            comparison["model_v1"] = {"macro_f1": float(macro_f1_v1)}
            print(f"[*] Comparative Baseline: RF-v1.0 Macro-F1 = {macro_f1_v1:.4f} vs RF-v2.0 Macro-F1 = {macro_f1_v2:.4f}")
        except Exception as e:
            print(f"[*] Baseline RF-v1 comparison skipped: {e}")

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

if __name__ == "__main__":
    run_training_pipeline()