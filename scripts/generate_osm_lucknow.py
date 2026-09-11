import json
import os

industrial_data = {
    "type": "FeatureCollection",
    "features": [
        # Lucknow Local Sites
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [80.8872, 26.8315]}, "properties": {"name": "Talkatora Industrial Estate"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [80.8624, 26.7601]}, "properties": {"name": "Amausi Industrial Area"}},
        
        # Major National Heavy Industrial & Flare Complexes
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [70.0577, 22.4707]}, "properties": {"name": "Jamnagar Petrochemical & Flare Complex"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [77.7011, 27.5956]}, "properties": {"name": "Mathura Refinery (IOCL)"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [86.1854, 22.8046]}, "properties": {"name": "Tata Steel Plant, Jamshedpur"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [85.9667, 20.9333]}, "properties": {"name": "Kalinganagar Industrial Corridor"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [81.3800, 21.1900]}, "properties": {"name": "Bhilai Steel Complex"}}
    ]
}

os.makedirs("gis/osm", exist_ok=True)
with open("gis/osm/lucknow_industrial_sites.geojson", "w", encoding="utf-8") as f:
    json.dump(industrial_data, f, indent=2)

print("Updated industrial facilities catalog.")