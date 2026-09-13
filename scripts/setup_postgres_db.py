import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def initialize_database():
    # 1. Connect to default maintenance database to create 'thermoguard'
    print("[*] Connecting to PostgreSQL default server...")
    conn_default = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database="postgres",
        user=DB_USER,
        password=DB_PASSWORD
    )
    conn_default.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur_default = conn_default.cursor()

    cur_default.execute("SELECT 1 FROM pg_database WHERE datname = 'thermoguard';")
    exists = cur_default.fetchone()
    if not exists:
        print("[*] Creating database 'thermoguard'...")
        cur_default.execute("CREATE DATABASE thermoguard;")
        print("✓ Database 'thermoguard' created.")
    else:
        print("✓ Database 'thermoguard' already exists.")

    cur_default.close()
    conn_default.close()

    # 2. Connect to 'thermoguard' and create PostGIS tables
    print("[*] Connecting to 'thermoguard' to initialize tables and PostGIS...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database="thermoguard",
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    # Enable PostGIS spatial extension
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 1. Industrial Sites
    cur.execute("""
        CREATE TABLE IF NOT EXISTS industrial_sites (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            geom GEOGRAPHY(Point, 4326),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Thermal Anomalies (with Member 3 cluster fields)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS thermal_anomalies (
            id VARCHAR(50) PRIMARY KEY,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            frp DOUBLE PRECISION,
            brightness_k DOUBLE PRECISION,
            satellite VARCHAR(100),
            acq_timestamp_ist TIMESTAMP WITHOUT TIME ZONE,
            persistence_count_30d INTEGER DEFAULT 1,
            cluster_id VARCHAR(50),
            cluster_size INTEGER DEFAULT 1,
            risk_zone VARCHAR(50),
            geom GEOGRAPHY(Point, 4326),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. Classified Events (with ML and GIS fields)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS classified_events (
            id VARCHAR(50) PRIMARY KEY,
            anomaly_id VARCHAR(50) REFERENCES thermal_anomalies(id) ON DELETE CASCADE,
            nearest_facility VARCHAR(255),
            distance_to_facility_km DOUBLE PRECISION,
            classification VARCHAR(100),
            severity VARCHAR(50),
            confidence_score DOUBLE PRECISION,
            ml_prediction VARCHAR(100),
            ml_confidence DOUBLE PRECISION,
            ml_explanation TEXT,
            industrial_relevance VARCHAR(50),
            cluster_id VARCHAR(50),
            classified_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 4. Alerts
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            event_id VARCHAR(50),
            severity VARCHAR(50) NOT NULL,
            message TEXT,
            status VARCHAR(30) DEFAULT 'ACTIVE',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Spatial indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thermal_geom ON thermal_anomalies USING GIST (geom);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_industrial_geom ON industrial_sites USING GIST (geom);")

    conn.commit()
    cur.close()
    conn.close()
    print("✓ Schema and PostGIS tables initialized successfully.")

if __name__ == "__main__":
    initialize_database()