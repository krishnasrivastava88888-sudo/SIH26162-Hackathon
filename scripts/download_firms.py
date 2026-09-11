import os
import pandas as pd
from dotenv import load_dotenv

# 1. Load secret MAP_KEY from the .env file
load_dotenv()
MAP_KEY = os.getenv("FIRMS_MAP_KEY")

if not MAP_KEY:
    raise ValueError("Error: FIRMS_MAP_KEY is missing. Check your .env file!")

# 2. Query FIRMS Area API: VIIRS NOAA-21 satellite over India for the past 5 days
# Coordinates format: West, South, East, North (68, 6, 98, 37)
url = (
    f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    f"{MAP_KEY}/VIIRS_NOAA21_NRT/68,6,98,37/5"
)

print("Connecting to NASA FIRMS API...")
df = pd.read_csv(url)

print(f"Success! Retrieved {len(df)} thermal anomalies.")
print(df[["latitude", "longitude", "acq_date", "bright_ti4", "frp", "confidence"]].head())

# 3. Save directly to your raw data folder
output_path = "data/raw/firms_india.csv"
df.to_csv(output_path, index=False)
print(f"Dataset successfully saved to: {output_path}")