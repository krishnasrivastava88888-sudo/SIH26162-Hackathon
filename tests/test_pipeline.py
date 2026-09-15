import pandas as pd
from ml.feature_engineering_v2 import ThermoGuardFeatureTransformerV2

def test_spatial_leakage_prevention():
    """Ensure missing distances are defensively imputed to 999.0 km."""
    transformer = ThermoGuardFeatureTransformerV2()
    # Dummy record missing the distance_to_facility_km field
    dummy_df = pd.DataFrame([{"frp": 100.5, "brightness_k": 310.0}])
    X_transformed = transformer.transform(dummy_df)
    
    # distance_km is index 3 in FEATURE_COLUMNS_V2
    assert X_transformed[0][3] == 999.0, "Missing distance was not properly imputed!"

def test_industrial_buffer_activation():
    """Ensure thermal events within 5km trigger the critical spatial buffer feature."""
    transformer = ThermoGuardFeatureTransformerV2()
    dummy_df = pd.DataFrame([{"distance_to_facility_km": 3.2}])
    X_transformed = transformer.transform(dummy_df)
    
    # industrial_buffer_5km is index 4 in FEATURE_COLUMNS_V2
    assert X_transformed[0][4] == 1.0, "Buffer flag not activated for close proximity!"