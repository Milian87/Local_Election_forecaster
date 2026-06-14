import geopandas as gpd
import os
import pandas as pd

base_dir = r"C:\Users\ianmi\Computer Programs\IRP-computer_program"

# 1. Load your existing Ward GeoJSON and the new County Division CSV
ward_geojson_path = os.path.join(base_dir, "ward_boundaries.geojson")
lookup_path = os.path.join(base_dir, "Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2025)_Lookup_for_EN.csv")
output_path = os.path.join(base_dir, "county_divisions.geojson") # New output file

# Load datasets
ward_gdf = gpd.read_file(ward_geojson_path)
lookup_df = pd.read_csv(lookup_path, usecols=["WD25CD", "CED25CD", "CED25NM", "LAD25CD", "LAD25NM"])

# 2. Filter the lookup table specifically for West Norfolk
lookup_df = lookup_df[lookup_df["LAD25NM"] == "King's Lynn and West Norfolk"].copy()
print(f"Lookup filtered! Found {lookup_df['CED25NM'].nunique()} unique County Council divisions.")

# 3. Merge current geometries with the County Electoral Division mapping
# We link them via the common 'WD25CD' (Ward Code) column
merged = ward_gdf.merge(lookup_df, on="WD25CD", how="inner")

# 4. Dissolve the boundaries by County Division Code (CED25CD)
print("Dissolving District Wards into County Council Divisions...")
division_gdf = merged.dissolve(
    by="CED25CD",
    as_index=False,
    aggfunc={
        "CED25NM": "first",
        "LAD25CD_y": "first", # pandas adds suffixes if names overlap
        "LAD25NM_y": "first",
    },
)

# 5. Rename columns so your frontend Map Engine works automatically without changes
division_gdf = division_gdf.rename(columns={
    "CED25NM": "WD25NM", 
    "LAD25CD_y": "LAD25CD", 
    "LAD25NM_y": "LAD25NM"
})
division_gdf["WD25CD"] = division_gdf["CED25CD"] # Match code expectation

# Clean up columns and simplify layout slightly for faster GUI loading
division_gdf = division_gdf[["WD25CD", "WD25NM", "LAD25CD", "LAD25NM", "geometry"]]
division_gdf["geometry"] = division_gdf["geometry"].simplify(tolerance=0.0001, preserve_topology=True)

# Save out to a clean file
division_gdf.to_file(output_path, driver="GeoJSON")
print(f"[SUCCESS] County Divisions GeoJSON generated at: {output_path}")
print(f"Sample County Division names:\n{division_gdf['WD25NM'].unique()[:16]}")