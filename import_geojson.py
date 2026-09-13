import json
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "thermoguard")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

geojson_path = "gis/osm/lucknow_industrial_sites.geojson"

if not os.path.exists(geojson_path):
    raise FileNotFoundError(f"OSM dataset not found at {geojson_path}")

with open(geojson_path, "r", encoding="utf-8") as f:
    geojson = json.load(f)

features = geojson.get("features", [])
print(f"[*] Ingesting {len(features)} industrial facilities from GeoJSON...")

for feature in features:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        continue

    longitude = float(coordinates[0])
    latitude = float(coordinates[1])

    name = (
        properties.get("name")
        or properties.get("Name")
        or properties.get("NAME")
        or "Unknown Industrial Site"
    )

    cur.execute(
        """
        INSERT INTO industrial_sites (name, latitude, longitude, geom)
        VALUES (
            %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
        );
        """,
        (name, latitude, longitude, longitude, latitude)
    )

conn.commit()
print(f"✓ Successfully synced {len(features)} industrial facilities to PostgreSQL.")

cur.close()
conn.close()