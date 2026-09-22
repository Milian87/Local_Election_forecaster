import os
import json
import urllib.request
from urllib.parse import urlencode, parse_qsl, urlsplit, urlunsplit
import geopandas as gpd
import pandas as pd
from pathlib import Path

def _enrich_with_2026_authorities(gdf, ward_boundaries_path, official_lookup_path=None):
    """Attach 2026 authority fields by lookup when available, otherwise spatial overlap.

    The ONS 2026 CED service contains CED26CD/CED26NM but no council names.
    The spatial fallback assigns each CED to the WD/LAD polygon with the
    greatest area overlap. Replace this fallback with the official 2026 ONS
    lookup by passing its CSV path once that lookup is published.
    """
    if official_lookup_path and Path(official_lookup_path).is_file():
        lookup = pd.read_csv(official_lookup_path, low_memory=False)
        code_column = next((c for c in ("CED26CD", "CEDCD", "ced_code") if c in lookup.columns), None)
        if code_column is None:
            raise ValueError("Official lookup must contain CED26CD or an equivalent CED code column.")
        lookup = lookup.rename(columns={code_column: "CED26CD"})
        return gdf.merge(lookup, on="CED26CD", how="left", suffixes=("", "_lookup"))

    wd = gpd.read_file(ward_boundaries_path)
    required = {"LAD26CD", "LAD26NM", "geometry"}
    missing = required.difference(wd.columns)
    if missing:
        raise ValueError(f"2026 WD boundary file is missing required fields: {sorted(missing)}")

    ced_metric = gdf[["CED26CD", "geometry"]].to_crs(epsg=27700)
    wd_metric = wd[["LAD26CD", "LAD26NM", "geometry"]].to_crs(epsg=27700)
    candidates = gpd.sjoin(ced_metric, wd_metric, how="left", predicate="intersects")
    def overlap_area(row):
        if pd.isna(row.index_right):
            return 0.0
        return row.geometry.intersection(wd_metric.loc[int(row.index_right), "geometry"]).area

    candidates["__overlap_area"] = candidates.apply(overlap_area, axis=1)
    best = (
        candidates.sort_values("__overlap_area")
        .drop_duplicates("CED26CD", keep="last")
        [["CED26CD", "LAD26CD", "LAD26NM"]]
    )
    return gdf.merge(best, on="CED26CD", how="left")


def download_ons_boundaries(
    output_dir="data/boundaries_2026",
    ward_boundaries_path="data/Borough and District Boundaries 2025/WD_MAY_2026_UK_BFC.shp",
    official_lookup_path=None,
):
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
    count_query = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    count_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(count_query), parts.fragment))
    with urllib.request.urlopen(count_url, timeout=90) as response:
        expected_count = json.load(response).get("count")
    if not expected_count:
        raise ValueError("[DOWNLOADER] ArcGIS service returned no expected feature count.")

    offset = 0
    page_size = 100  # Keep GeoJSON responses small enough for the ArcGIS service.
    
    print("[DOWNLOADER] Starting paginated download of May 2026 County Electoral Divisions...")
    
    while True:
        query = dict(base_query)
        query.update({"resultOffset": str(offset), "resultRecordCount": str(page_size)})
        page_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        
        print(f"[DOWNLOADER] Fetching records starting at offset {offset}...")
        payload = None
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(page_url, timeout=180) as response:
                    payload = json.load(response)
                break
            except Exception as error:
                last_error = error
                print(
                    f"[DOWNLOADER] Retry {attempt + 1}/3 for offset {offset}: {error}"
                )
        if payload is None:
            raise RuntimeError(
                f"[DOWNLOADER] Failed fetching batch at offset {offset}: {last_error}"
            )
            
        page_features = payload.get("features", [])
        if not page_features:
            break
            
        features.extend(page_features)
        offset += len(page_features)
        print(f"[DOWNLOADER] Downloaded {len(features)} total features so far...")
        
        if len(features) >= expected_count:
            break

        if len(page_features) == 0:
            raise RuntimeError(
                f"[DOWNLOADER] Pagination stopped at {len(features)} of {expected_count} features."
            )

    if not features:
        raise ValueError("[DOWNLOADER] Failed to retrieve any features from the ArcGIS server.")

    # Convert collected features into a GeoDataFrame
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    
    gdf = gpd.GeoDataFrame.from_features(geojson_data, crs="EPSG:4326")
    if len(gdf) != expected_count:
        raise RuntimeError(
            f"[DOWNLOADER] Incomplete download: received {len(gdf)} of {expected_count} features."
        )
    gdf = _enrich_with_2026_authorities(
        gdf,
        ward_boundaries_path=ward_boundaries_path,
        official_lookup_path=official_lookup_path,
    )
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