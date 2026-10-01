import geopandas as gpd
import pandas as pd
from pathlib import Path
from forecaster_data import get_database
from sqlalchemy import text

shp_path = Path("data/Borough and District Boundaries 2025/WD_MAY_2026_UK_BFC.shp")
gdf = gpd.read_file(shp_path)
print("Shapefile rows:", len(gdf))
print("Shapefile columns:", list(gdf.columns))
code_col = next((c for c in ("WD26CD", "WD25CD") if c in gdf.columns), None)
print("Using code column:", code_col)
shp_codes = set(gdf[code_col].astype(str).str.strip().str.upper())

db = get_database()
with db.engine.connect() as conn:
    wd_codes = conn.execute(text("SELECT DISTINCT wd_code FROM election_results")).fetchall()
    cc_prefixes = conn.execute(text("SELECT cc_code, council_name FROM county_codes")).fetchall()
    ew = conn.execute(text("SELECT wd_code, cc_code FROM electoral_wards")).fetchall()

db_codes = set(str(r[0]).strip().upper() for r in wd_codes)
print("Distinct wd_codes in election_results:", len(db_codes))

overlap = shp_codes & db_codes
print("Overlap between shapefile WD codes and election_results wd_codes:", len(overlap))
print("Shapefile-only codes (sample 5):", list(shp_codes - db_codes)[:5])
print("DB-only codes (sample 5):", list(db_codes - shp_codes)[:5])

# cc_code prefix breakdown for election_results via electoral_wards join
ew_df = pd.DataFrame(ew, columns=["wd_code", "cc_code"])
ew_df["wd_code"] = ew_df["wd_code"].astype(str).str.strip().str.upper()
ew_df["prefix"] = ew_df["cc_code"].astype(str).str.slice(0, 3)
print("\ncc_code prefix counts among electoral_wards:")
print(ew_df["prefix"].value_counts())

print("\nTotal county_codes rows:", len(cc_prefixes))
print("Sample county_codes:", cc_prefixes[:10])
