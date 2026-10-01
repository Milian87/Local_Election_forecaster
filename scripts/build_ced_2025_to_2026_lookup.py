"""One-off builder for the CED (May 2025) -> CED (May 2026) best-fit lookup.

Performs a geometric overlay between the two County Electoral Division boundary
vintages and, for each 2025 division, picks the 2026 division it overlaps most
with by area. Mirrors the project's existing *_Best_Fit_Lookup.csv convention.
"""
import geopandas as gpd
import pandas as pd
from pathlib import Path

root = Path(__file__).parent.parent
ced25_path = root / "data" / "County Electoral Division (May 2025) Boundaries EN BFE" / "CED_MAY_2025_EN_BFC.shp"
ced26_path = root / "data" / "boundaries_2026" / "CED_MAY_2026_EN_BFC.shp"
out_path = root / "data" / "Lookups" / "CED_2025_to_2026_Best_Fit_Lookup.csv"

ced25 = gpd.read_file(ced25_path)[["CED25CD", "CED25NM", "geometry"]].to_crs(epsg=27700)
ced26 = gpd.read_file(ced26_path)[["CED26CD", "CED26NM", "geometry"]].to_crs(epsg=27700)

ced25["area_2025"] = ced25.geometry.area
overlay = gpd.overlay(ced25, ced26, how="intersection")
overlay["overlap_area"] = overlay.geometry.area

best = (
    overlay.sort_values("overlap_area", ascending=False)
    .drop_duplicates("CED25CD", keep="first")
    .copy()
)
best["overlap_pct"] = (best["overlap_area"] / best["area_2025"]).round(4)
lookup = best[["CED25CD", "CED25NM", "CED26CD", "CED26NM", "overlap_pct"]].sort_values("CED25CD")

lookup.to_csv(out_path, index=False)
print(f"Wrote {len(lookup):,} rows to {out_path}")
print("Unmatched 2025 divisions (no 2026 overlap found):", len(ced25) - len(lookup))
print("Exact-code-match rows (CED25CD == CED26CD):", (lookup["CED25CD"] == lookup["CED26CD"]).sum())
print("Low-confidence matches (<90% area overlap):", (lookup["overlap_pct"] < 0.9).sum())
