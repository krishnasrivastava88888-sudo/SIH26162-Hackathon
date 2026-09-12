import json
import psycopg2

# PostgreSQL connection
conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="thermoguard",
    user="postgres",
    password="Gaurav@123"
)

cur = conn.cursor()

# GeoJSON file
geojson_path = "gis/osm/lucknow_industrial_sites.geojson"

with open(geojson_path, "r", encoding="utf-8") as f:
    geojson = json.load(f)

features = geojson["features"]

print(f"Found {len(features)} industrial sites.")

for feature in features:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})

    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        continue

    longitude = coordinates[0]
    latitude = coordinates[1]

    name = (
        properties.get("name")
        or properties.get("Name")
        or properties.get("NAME")
        or "Unknown Industrial Site"
    )

    cur.execute(
        """
        INSERT INTO industrial_sites
            (name, latitude, longitude, geom)
        VALUES
            (%s, %s, %s,
             ST_SetSRID(
                 ST_MakePoint(%s, %s),
                 4326
             )::geography
            )
        """,
        (
            name,
            latitude,
            longitude,
            longitude,
            latitude,
        )
    )

conn.commit()

print(f"Successfully imported {len(features)} industrial sites.")

cur.close()
conn.close()