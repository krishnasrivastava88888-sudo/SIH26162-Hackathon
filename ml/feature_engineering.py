import os
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

UNBOUNDED_DISTANCE_KM = 50.0

class ThermoGuardFeatureTransformer(BaseEstimator, TransformerMixin):
    """
    Transforms raw FIRMS hotspot telemetry into feature vectors
    while preventing spatial and temporal leakage.
    """
    def __init__(self):
        self.feature_columns = [
            "log_frp",
            "brightness_k",
            "distance_km",
            "is_near_industrial",
            "persistence_count_30d",
            "acq_hour_sin",
            "acq_hour_cos",
            "frp_thermal_ratio"
        ]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()
        
        # 1. Fill missing distances for points in open rural areas
        if "distance_to_facility_km" in df.columns:
            df["distance_km"] = df["distance_to_facility_km"].fillna(UNBOUNDED_DISTANCE_KM)
        elif "distance_km" not in df.columns:
            df["distance_km"] = UNBOUNDED_DISTANCE_KM

        # 2. Binary buffer proximity indicator (<= 5 km)
        df["is_near_industrial"] = (df["distance_km"] <= 5.0).astype(int)

        # 3. Log-transform FRP to normalize skewed combustion values
        df["log_frp"] = np.log1p(df["frp"].clip(lower=0))

        # 4. Thermal intensity ratio
        temp_c = (df["brightness_k"] - 273.15).clip(lower=1.0)
        df["frp_thermal_ratio"] = df["frp"] / temp_c

        # 5. Extract acquisition hour safely without timezone parsing errors
        if "acq_timestamp_ist" in df.columns:
            hours = (
                df["acq_timestamp_ist"]
                .astype(str)
                .str.extract(r" (\d{1,2}):", expand=False)
                .astype(float)
                .fillna(12.0)
            )
        else:
            hours = pd.Series(12.0, index=df.index)

        df["acq_hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
        df["acq_hour_cos"] = np.cos(2 * np.pi * hours / 24.0)

        # 6. Ensure recurrence baseline exists
        if "persistence_count_30d" not in df.columns:
            df["persistence_count_30d"] = 1

        return df[self.feature_columns]


def load_dataset(csv_path="data/processed/classified_hotspots.csv"):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing processed data at {csv_path}")
    
    df = pd.read_csv(csv_path)

    # Coarse spatial binning (~11 km) to enforce Group-based train/test splitting
    df["spatial_cluster_group"] = (
        (df["latitude"].round(1).astype(str)) + "_" + (df["longitude"].round(1).astype(str))
    )
    return df