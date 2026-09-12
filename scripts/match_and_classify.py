import json
import math
import os
import pandas as pd

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two coordinates in kilometers."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Load OSM industrial features
geojson_path = "gis/osm/lucknow_industrial_sites.geojson"
with open(geojson_path, "r", encoding="utf-8") as f:
    osm_data = json.load(f)

industrial_sites = []
for feat in osm_data.get("features", []):
    lon, lat = feat["geometry"]["coordinates"]
    name = feat["properties"].get("name", "Industrial Complex")
    industrial_sites.append({"name": name, "lat": lat, "lon": lon})

# Load NASA FIRMS thermal anomaly data
firms_path = "data/raw/firms_india.csv"
df = pd.read_csv(firms_path)
print(f"Analyzing {len(df)} satellite hotspot detections...")

classified_records = []

# Buffer threshold: 3.0 km radius from industrial site center
PROXIMITY_THRESHOLD_KM = 3.0

for _, row in df.iterrows():
    fire_lat, fire_lon = row["latitude"], row["longitude"]
    frp = row.get("frp", 0.0)
    brightness = row.get("bright_ti4", 0.0)
    confidence = row.get("confidence", "nominal")
    
    # Find nearest industrial facility
    nearest_site = None
    min_distance = float("inf")
    
    for site in industrial_sites:
        dist = haversine_distance(fire_lat, fire_lon, site["lat"], site["lon"])
        if dist < min_distance:
            min_distance = dist
            nearest_site = site["name"]

    # Multi-criteria classification logic
    if min_distance <= PROXIMITY_THRESHOLD_KM:
        if frp > 100:
            classification = "Accidental Industrial Fire (High Hazard)"
            severity = "CRITICAL"
        else:
            classification = "Routine Industrial Flaring / Smelting"
            severity = "LOW"
    else:
        if frp < 25:
            classification = "Agricultural / Stubble Burning"
            severity = "MODERATE"
        else:
            classification = "Wildfire / Forest Thermal Event"
            severity = "HIGH"

    classified_records.append({
        "latitude": fire_lat,
        "longitude": fire_lon,
        "frp": frp,
        "brightness_k": brightness,
        "confidence": confidence,
        "nearest_facility": nearest_site if min_distance <= PROXIMITY_THRESHOLD_KM else "None",
        "distance_km": round(min_distance, 2),
        "classification": classification,
        "severity": severity
    })

# Save structured results
os.makedirs("data/processed", exist_ok=True)
results_df = pd.DataFrame(classified_records)
output_csv = "data/processed/classified_hotspots.csv"
results_df.to_csv(output_csv, index=False)

print(f"Classification finished! Output saved to: {output_csv}")
print("\nClassification Summary:")
print(results_df["classification"].value_counts())