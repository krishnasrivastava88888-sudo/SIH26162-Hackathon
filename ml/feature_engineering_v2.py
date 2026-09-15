import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

FEATURE_COLUMNS_V2 = [
    "log_frp",
    "brightness_k",
    "frp_thermal_ratio",
    "distance_km",
    "industrial_buffer_5km",
    "persistence_count_30d",
    "cluster_size",
    "acq_hour_sin",
    "acq_hour_cos",
]


class ThermoGuardFeatureTransformerV2(BaseEstimator, TransformerMixin):

  def __init__(self):
    pass

  def fit(self, X, y=None):
    return self

  def transform(self, X):
    # Support dict, list of dicts, or existing DataFrame
    if isinstance(X, dict):
      df = pd.DataFrame([X])
    elif isinstance(X, pd.DataFrame):
      df = X.copy()
    else:
      df = pd.DataFrame(X).copy()

    # Prepopulate missing telemetry columns with defensive defaults
    defaults = {
        "frp": 0.0,
        "brightness_k": 300.0,
        "distance_to_facility_km": 999.0,
        "persistence_count_30d": 1,
        "cluster_size": 1,
        "acq_timestamp_ist": "12:00:00",
    }
    for col, default_val in defaults.items():
      if col not in df.columns:
        df[col] = default_val

    # 1. Radiative features
    frp = pd.to_numeric(df["frp"], errors="coerce").fillna(0.0)
    df["log_frp"] = np.log1p(np.maximum(frp, 0.0))

    # 2. Brightness temperature & thermal ratio
    brightness = pd.to_numeric(df["brightness_k"], errors="coerce").fillna(
        300.0
    )
    df["brightness_k"] = brightness
    temp_c = np.maximum(brightness - 273.15, 0.1)
    df["frp_thermal_ratio"] = frp / (temp_c + 1e-5)

    # 3. Spatial proximity to facilities
    dist = pd.to_numeric(
        df["distance_to_facility_km"], errors="coerce"
    ).fillna(999.0)
    df["distance_km"] = dist
    df["industrial_buffer_5km"] = (dist <= 5.0).astype(int)

    # 4. Temporal recurrence
    df["persistence_count_30d"] = (
        pd.to_numeric(df["persistence_count_30d"], errors="coerce")
        .fillna(1)
        .astype(int)
    )

    # 5. Spatial cluster footprint
    df["cluster_size"] = (
        pd.to_numeric(df["cluster_size"], errors="coerce")
        .fillna(1)
        .astype(int)
    )

    # 6. Cyclic temporal encoding
    timestamps = pd.to_datetime(
        df["acq_timestamp_ist"]
        .astype(str)
        .str.replace(r"\s+IST", "", regex=True),
        errors="coerce",
    )
    hours = timestamps.dt.hour.fillna(12).astype(float)
    df["acq_hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
    df["acq_hour_cos"] = np.cos(2 * np.pi * hours / 24.0)

    return df[FEATURE_COLUMNS_V2].values

  def get_feature_names_out(self, input_features=None):
    return np.array(FEATURE_COLUMNS_V2, dtype=object)