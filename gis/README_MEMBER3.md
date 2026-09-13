# Member 3 — GIS + Industrial Proximity

This module is the **location intelligence layer** for ThermoGuard AI.

It uses the **existing** OSM-derived file:
`gis/osm/lucknow_industrial_sites.geojson`

It does **not** download OSM again.

## What it does

1. Reads `data/processed/classified_hotspots.csv`.
2. Finds the nearest existing industrial facility for every hotspot.
3. Calculates the great-circle distance in kilometres.
4. Assigns industrial relevance:
   - `< 1 km` → `CRITICAL`
   - `1–3 km` → `HIGH`
   - `3–5 km` → `MODERATE`
   - `> 5 km` → `LOW`
5. Groups nearby hotspots using DBSCAN-style spatial clustering.
6. Adds cluster size and event-group information.
7. Writes CSV, JSON and GeoJSON outputs.

> The distance bands and 1 km clustering radius are **project operational assumptions for the prototype**, not universal fire-science thresholds.

## Run it

From the `ThermoGuardAi` folder:

```bash
python gis/run_member3.py
```

No extra package is required beyond Python and pandas already used by the project.

## Outputs

```text
data/processed/enriched_hotspots.csv
data/processed/enriched_hotspots.json
data/processed/enriched_hotspots.geojson
```

## Example fields

```text
nearest_facility_id
nearest_facility_name
distance_km
industrial_relevance
risk_zone
cluster_id
cluster_size
event_group
```

### What to tell the team

**Member 3:** "I built the GIS intelligence layer. For every satellite hotspot, the system finds the nearest industrial facility from our existing OSM dataset, calculates the distance, assigns industrial relevance/risk zone, and clusters nearby hotspots into events. The enriched data is then ready for the FastAPI and dashboard teams."
