# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# created: 19/05/2026

import geopandas as gpd
from shapely.geometry import Point
import pyproj
import sys

print("=============================================")
print(f"Python Version: {sys.version.split()[0]}")
print("Running Geospatial Pipeline Diagnostics...")
print("=============================================\n")

# Test 1: Verify Projection Engine can read the British National Grid (EPSG:27700)
try:
    bng = pyproj.CRS("EPSG:27700")
    print("[SUCCESS] 1. PyProj initialized. British National Grid standard found.")
except Exception as e:
    print(f"[ERROR] 1. Projection alignment failure: {e}")

# Test 2: Verify Geometry creation works
try:
    # Generate a sample point coordinates roughly near King's Lynn / Norfolk area
    test_point = Point(562000, 320000) 
    print(f"[SUCCESS] 2. Shapely generated valid geometry object: {test_point}")
except Exception as e:
    print(f"[ERROR] 2. Geometry engine failure: {e}")

# Test 3: Verify GeoPandas structures are active
try:
    gdf = gpd.GeoDataFrame(geometry=[test_point], crs="EPSG:27700")
    print(f"[SUCCESS] 3. GeoPandas active. Active Coordinate Reference System: {gdf.crs}")
except Exception as e:
    print(f"[ERROR] 3. Spatial DataFrame framework failure: {e}")

print("\n=============================================")
print("Diagnostic Complete. Environment is stable.")
print("=============================================")