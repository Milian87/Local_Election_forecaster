import os
import json
import urllib.request
from urllib.parse import urlencode, parse_qsl, urlsplit, urlunsplit
import geopandas as gpd

def download_ons_boundaries(output_dir="data/boundaries_2026"):
    # Official ONS May 2026 County Electoral Division FeatureServer query endpoint
    base_url = (
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
        "CED_MAY_2026_EN_BFC/FeatureServer/0/query"
    )
    
    os.makedirs(output_dir, exist_ok=True)
    
    parts = urlsplit(base_url)
    base_query = dict(parse_qsl(parts.query, keep_blank_values=True))
    base_query.update({"where": "1=1", "outFields": "*", "f": "geojson"})
    
    features = []
    offset = 0
    page_size = 500  # Smaller batch size to prevent server timeout (HTTP 504)
    
    print("[DOWNLOADER] Starting paginated download of May 2026 County Electoral Divisions...")
    
    while True:
        query = dict(base_query)
        query.update({"resultOffset": str(offset), "resultRecordCount": str(page_size)})
        page_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        
        print(f"[DOWNLOADER] Fetching records starting at offset {offset}...")
        try:
            with urllib.request.urlopen(page_url, timeout=90) as response:
                payload = json.load(response)
        except Exception as e:
            print(f"[DOWNLOADER] Error fetching batch at offset {offset}: {e}")
            break
            
        page_features = payload.get("features", [])
        if not page_features:
            break
            
        features.extend(page_features)
        offset += len(page_features)
        print(f"[DOWNLOADER] Downloaded {len(features)} total features so far...")
        
        # Check if we've reached the end
        if len(page_features) < page_size and not payload.get("exceededTransferLimit", False):
            break

    if not features:
        raise ValueError("[DOWNLOADER] Failed to retrieve any features from the ArcGIS server.")

    # Convert collected features into a GeoDataFrame
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    
    gdf = gpd.GeoDataFrame.from_features(geojson_data, crs="EPSG:4326")
    print(f"[DOWNLOADER] Successfully compiled GeoDataFrame with {len(gdf)} divisions covering all of England (including Norfolk & Suffolk).")
    
    # Save as GeoJSON
    geojson_path = os.path.join(output_dir, "CED_MAY_2026_EN_BFC.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"[DOWNLOADER] Saved GeoJSON to: {geojson_path}")
    
    # Optional: Save as Shapefile package if needed by legacy shapefile loaders
    shp_path = os.path.join(output_dir, "CED_MAY_2026_EN_BFC.shp")
    gdf.to_file(shp_path, driver="ESRI Shapefile")
    print(f"[DOWNLOADER] Saved Shapefile to: {shp_path}")
    
    return shp_path

if __name__ == "__main__":
    download_ons_boundaries()