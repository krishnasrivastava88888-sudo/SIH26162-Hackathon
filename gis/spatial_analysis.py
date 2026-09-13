"""Member 3 - GIS + Industrial Proximity intelligence layer.

Reads the existing classified hotspot data and existing OSM industrial-site
GeoJSON. It does not download OSM data.

Outputs:
- data/processed/enriched_hotspots.csv
- data/processed/enriched_hotspots.json
- data/processed/enriched_hotspots.geojson
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Tuple

import pandas as pd

# Project paths are resolved from this file, so the script works from any folder.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOTSPOTS_CSV = os.path.join(PROJECT_ROOT, "data", "processed", "classified_hotspots.csv")
OSM_GEOJSON = os.path.join(PROJECT_ROOT, "gis", "osm", "lucknow_industrial_sites.geojson")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "enriched_hotspots.csv")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "enriched_hotspots.json")
OUTPUT_GEOJSON = os.path.join(OUTPUT_DIR, "enriched_hotspots.geojson")

EARTH_RADIUS_KM = 6371.0088
CLUSTER_EPS_KM = 1.0       # Project operational assumption: nearby = within 1 km
CLUSTER_MIN_POINTS = 2


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two latitude/longitude points."""
    p1 = math.radians(float(lat1))
    p2 = math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def load_industrial_sites() -> List[Dict]:
    """Load the existing OSM-derived industrial site catalog."""
    if not os.path.exists(OSM_GEOJSON):
        raise FileNotFoundError(f"Existing OSM file not found: {OSM_GEOJSON}")

    with open(OSM_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    sites = []
    for index, feature in enumerate(data.get("features", []), start=1):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            continue

        props = feature.get("properties") or {}
        sites.append({
            "facility_id": f"FAC-{index:03d}",
            "facility_name": props.get("name") or f"Industrial Facility {index}",
            "longitude": float(coordinates[0]),
            "latitude": float(coordinates[1]),
            "facility_type": props.get("landuse") or props.get("power") or "industrial",
        })

    if not sites:
        raise ValueError("No usable industrial facilities were found in the existing OSM GeoJSON.")
    return sites


def nearest_facility(lat: float, lon: float, sites: List[Dict]) -> Tuple[Dict, float]:
    best_site = None
    best_distance = float("inf")
    for site in sites:
        distance = haversine_km(lat, lon, site["latitude"], site["longitude"])
        if distance < best_distance:
            best_distance = distance
            best_site = site
    return best_site, best_distance


def relevance_from_distance(distance_km: float) -> str:
    """Convert facility distance into the project's operational relevance bands."""
    if distance_km < 1.0:
        return "CRITICAL"
    if distance_km <= 3.0:
        return "HIGH"
    if distance_km <= 5.0:
        return "MODERATE"
    return "LOW"


def risk_zone_from_distance(distance_km: float) -> str:
    # Kept as a separate function so the team can later replace this with a
    # multi-factor risk score without changing the rest of the pipeline.
    return relevance_from_distance(distance_km)


def region_query(index: int, points: List[Tuple[float, float]]) -> List[int]:
    """Find all hotspot indexes within CLUSTER_EPS_KM of a point."""
    lat, lon = points[index]
    neighbors = []
    for j, (other_lat, other_lon) in enumerate(points):
        if haversine_km(lat, lon, other_lat, other_lon) <= CLUSTER_EPS_KM:
            neighbors.append(j)
    return neighbors


def dbscan_haversine(points: List[Tuple[float, float]]) -> List[int]:
    """Small dependency-free DBSCAN implementation using haversine distance.

    - label -1 = noise/single hotspot
    - labels 0,1,2... = spatial clusters
    """
    labels = [None] * len(points)
    visited = [False] * len(points)

    for i in range(len(points)):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = region_query(i, points)

        if len(neighbors) < CLUSTER_MIN_POINTS:
            labels[i] = -1
            continue

        cluster_id = max([-1] + [x for x in labels if x is not None]) + 1
        labels[i] = cluster_id
        seeds = list(neighbors)
        cursor = 0

        while cursor < len(seeds):
            j = seeds[cursor]
            cursor += 1

            if not visited[j]:
                visited[j] = True
                j_neighbors = region_query(j, points)
                if len(j_neighbors) >= CLUSTER_MIN_POINTS:
                    for n in j_neighbors:
                        if n not in seeds:
                            seeds.append(n)

            if labels[j] is None or labels[j] == -1:
                labels[j] = cluster_id

    return [(-1 if x is None else x) for x in labels]


def build_geojson(df: pd.DataFrame) -> Dict:
    features = []
    for _, row in df.iterrows():
        props = {}
        for key, value in row.to_dict().items():
            if key in ("latitude", "longitude"):
                continue
            if pd.isna(value):
                props[key] = None
            elif hasattr(value, "item"):
                props[key] = value.item()
            else:
                props[key] = value

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["longitude"]), float(row["latitude"])],
            },
            "properties": props,
        })

    return {"type": "FeatureCollection", "features": features}


def run() -> pd.DataFrame:
    if not os.path.exists(HOTSPOTS_CSV):
        raise FileNotFoundError(f"Hotspot file not found: {HOTSPOTS_CSV}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.read_csv(HOTSPOTS_CSV)

    required = {"latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Hotspot CSV is missing required columns: {sorted(missing)}")

    sites = load_industrial_sites()

    # 1) Nearest facility + distance + relevance.
    nearest_names = []
    nearest_ids = []
    nearest_types = []
    distances = []
    relevances = []
    risk_zones = []

    for _, row in df.iterrows():
        site, distance = nearest_facility(float(row["latitude"]), float(row["longitude"]), sites)
        nearest_ids.append(site["facility_id"])
        nearest_names.append(site["facility_name"])
        nearest_types.append(site["facility_type"])
        distances.append(round(distance, 3))
        relevances.append(relevance_from_distance(distance))
        risk_zones.append(risk_zone_from_distance(distance))

    df["nearest_facility_id"] = nearest_ids
    df["nearest_facility_name"] = nearest_names
    df["nearest_facility_type"] = nearest_types
    df["distance_km"] = distances
    df["industrial_relevance"] = relevances
    df["risk_zone"] = risk_zones

    # 2) Spatial hotspot clustering.
    points = [(float(lat), float(lon)) for lat, lon in zip(df["latitude"], df["longitude"])]
    labels = dbscan_haversine(points)

    cluster_sizes: Dict[int, int] = {}
    for label in labels:
        if label >= 0:
            cluster_sizes[label] = cluster_sizes.get(label, 0) + 1

    cluster_ids = []
    cluster_size_values = []
    for label in labels:
        if label < 0:
            cluster_ids.append("NOISE")
            cluster_size_values.append(1)
        else:
            cluster_ids.append(f"CL-{label + 1:04d}")
            cluster_size_values.append(cluster_sizes[label])

    df["cluster_id"] = cluster_ids
    df["cluster_size"] = cluster_size_values
    df["cluster_radius_km"] = CLUSTER_EPS_KM

    # 3) Useful presentation-friendly event label.
    df["event_group"] = df.apply(
        lambda r: f"{r['cluster_id']} ({int(r['cluster_size'])} hotspot{'s' if int(r['cluster_size']) != 1 else ''})",
        axis=1,
    )

    # Keep important Member 3 fields near the front while preserving original data.
    preferred = [
        "id", "latitude", "longitude", "classification", "severity", "frp",
        "brightness_k", "satellite", "acq_timestamp_ist", "persistence_count_30d",
        "nearest_facility_id", "nearest_facility_name", "nearest_facility_type",
        "distance_km", "industrial_relevance", "risk_zone", "cluster_id",
        "cluster_size", "cluster_radius_km", "event_group", "confidence_score",
    ]
    ordered = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    df = df[ordered]

    df.to_csv(OUTPUT_CSV, index=False)
    df.to_json(OUTPUT_JSON, orient="records", indent=2)
    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(build_geojson(df), f, indent=2)

    print(f"Processed hotspots: {len(df)}")
    print(f"Existing industrial facilities used: {len(sites)}")
    print(f"Spatial cluster radius: {CLUSTER_EPS_KM} km")
    print(f"Clusters found: {len(cluster_sizes)}")
    print(f"Singleton/noise hotspots: {sum(1 for x in labels if x < 0)}")
    print(f"Saved: {OUTPUT_CSV}")
    print(f"Saved: {OUTPUT_JSON}")
    print(f"Saved: {OUTPUT_GEOJSON}")
    print("\nIndustrial relevance summary:")
    print(df["industrial_relevance"].value_counts())
    return df


if __name__ == "__main__":
    run()
