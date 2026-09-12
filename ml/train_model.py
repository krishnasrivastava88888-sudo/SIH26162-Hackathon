import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from feature_engineering import ThermoGuardFeatureTransformer, load_dataset

MODEL_DIR = "ml/models"
DATA_DIR = "ml/data"
MODEL_PATH = os.path.join(MODEL_DIR, "thermoguard_rf.pkl")
TRAIN_SNAPSHOT_PATH = os.path.join(DATA_DIR, "training_data.csv")


def train():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Loading hotspot records...")
    df = load_dataset()
    df.to_csv(TRAIN_SNAPSHOT_PATH, index=False)

    target_col = "classification"
    X = df.drop(columns=[target_col])
    y = df[target_col]
    groups = df["spatial_cluster_group"]

    # Spatial cluster split: entire geographic clusters stay in train OR test
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]

    print(f"Dataset split: {len(X_train)} train rows, {len(X_test)} spatially isolated test rows.")
    print("Training classes:", y_train.value_counts().to_dict())

    # Build Pipeline
    pipeline = Pipeline([
        ("preprocessor", ThermoGuardFeatureTransformer()),
        ("classifier", RandomForestClassifier(
            n_estimators=120,
            max_depth=6,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1
        ))
    ])

    print("Fitting Cost-Sensitive Random Forest...")
    pipeline.fit(X_train, y_train)

    # Persist model bundle and evaluation partitions
    joblib.dump({
        "pipeline": pipeline,
        "classes": pipeline.named_steps["classifier"].classes_.tolist(),
        "test_indices": test_idx.tolist(),
        "model_version": "RF-v1.0"
    }, MODEL_PATH)

    print(f"Model saved successfully to: {MODEL_PATH}")


if __name__ == "__main__":
    train()