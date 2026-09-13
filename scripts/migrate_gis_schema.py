import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate_schema():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "thermoguard"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    print("[*] Applying GIS schema migration to 'thermoguard'...")

    # 1. Add spatial cluster and risk attributes to thermal_anomalies
    cur.execute("""
        ALTER TABLE thermal_anomalies
        ADD COLUMN IF NOT EXISTS cluster_id VARCHAR(50),
        ADD COLUMN IF NOT EXISTS cluster_size INT DEFAULT 1,
        ADD COLUMN IF NOT EXISTS risk_zone VARCHAR(50);
    """)

    # 2. Add industrial proximity and relevance to classified_events
    cur.execute("""
        ALTER TABLE classified_events
        ADD COLUMN IF NOT EXISTS industrial_relevance VARCHAR(50),
        ADD COLUMN IF NOT EXISTS cluster_id VARCHAR(50);
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✓ Schema migration successful. Database is ready for GIS-enriched payloads.")

if __name__ == "__main__":
    migrate_schema()