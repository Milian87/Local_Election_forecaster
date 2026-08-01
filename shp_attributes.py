import geopandas as gpd

# Replace with the path to your shapefile
shp_path = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\2026 Boundaries\Norfolk Boundary\Norfolk_final_proposals.shp"

# Load the shapefile
gdf = gpd.read_file(shp_path)

# Print the head of the attribute table (the first 5 rows)
print("--- Shapefile Attribute Table Head ---")
print(gdf.head())

# search for division name "Gaywood North & Central" and print the corresponding row
division_name = "Gaywood North & Central"
division_row = gdf[gdf['Name'] == division_name]
print("\n--- Division Row ---")
print(division_row)

# Print column names to confirm the join column exists
print("\n--- Available Columns ---")
print(gdf.columns.tolist())