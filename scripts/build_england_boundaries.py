from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


REQUIRED_LOOKUP_COLUMNS = [
    "WD25CD",
    "WD25NM",
    "LAD25CD",
    "LAD25NM",
    "CTY25CD",
    "CTY25NM",
    "CED25CD",
    "CED25NM",
]


def norm_key(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
    )


def ensure_required_inputs(geometry_path: Path, lookup_path: Path, lsoa_lookup_path: Path) -> None:
    missing = [str(p) for p in [geometry_path, lookup_path, lsoa_lookup_path] if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required input files: " + ", ".join(missing))


def load_and_prepare_ward_geometry(geometry_path: Path, lsoa_lookup_path: Path) -> gpd.GeoDataFrame:
    print(f"[STEP] Loading ONS geometry source: {geometry_path}")
    gdf = gpd.read_file(geometry_path)
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        raise ValueError("Geometry source has no valid polygon geometries.")

    has_ward_fields = all(c in gdf.columns for c in ["WD25CD", "WD25NM", "LAD25CD", "LAD25NM"])

    if has_ward_fields:
        gdf["WD25CD"] = gdf["WD25CD"].astype(str).str.strip()
        gdf["WD25NM"] = gdf["WD25NM"].astype(str).str.strip()
        gdf["LAD25CD"] = gdf["LAD25CD"].astype(str).str.strip()
        gdf["LAD25NM"] = gdf["LAD25NM"].astype(str).str.strip()
    else:
        if "LSOA21CD" not in gdf.columns:
            raise ValueError(
                "Geometry source is missing WD/LAD fields and does not include LSOA21CD for lookup bridging."
            )

        print(f"[STEP] Bridging LSOA to Ward/LAD using: {lsoa_lookup_path}")
        lsoa_lookup = pd.read_csv(
            lsoa_lookup_path,
            usecols=["LSOA21CD", "WD25CD", "WD25NM", "LAD25CD", "LAD25NM"],
        )
        lsoa_lookup["LSOA21CD"] = lsoa_lookup["LSOA21CD"].astype(str).str.strip()
        for col in ["WD25CD", "WD25NM", "LAD25CD", "LAD25NM"]:
            lsoa_lookup[col] = lsoa_lookup[col].astype(str).str.strip()

        gdf["LSOA21CD"] = gdf["LSOA21CD"].astype(str).str.strip()
        gdf = gdf.merge(lsoa_lookup, on="LSOA21CD", how="left")
        gdf = gdf[gdf["WD25CD"].notna()].copy()

        if gdf.empty:
            raise ValueError("No rows remained after LSOA->Ward/LAD enrichment.")

    print("[STEP] Dissolving source geometry to ward-level polygons")
    wards = gdf.dissolve(
        by="WD25CD",
        as_index=False,
        aggfunc={
            "WD25NM": "first",
            "LAD25CD": "first",
            "LAD25NM": "first",
        },
    )
    wards["k_w"] = norm_key(wards["WD25NM"])
    wards["k_l"] = norm_key(wards["LAD25NM"])
    print(f"[INFO] Ward polygons: {len(wards):,}")
    return wards


def load_lookup(lookup_path: Path) -> pd.DataFrame:
    print(f"[STEP] Loading ONS lookup: {lookup_path}")
    lookup = pd.read_csv(lookup_path, usecols=REQUIRED_LOOKUP_COLUMNS)
    lookup = lookup.copy()

    for col in ["WD25CD", "WD25NM", "LAD25CD", "LAD25NM", "CTY25CD", "CTY25NM", "CED25CD", "CED25NM"]:
        lookup[col] = lookup[col].astype(str).str.strip()

    # Normalize blank placeholders from CSV reading
    for col in ["CTY25CD", "CTY25NM", "CED25CD", "CED25NM"]:
        lookup.loc[lookup[col].isin(["", "nan", "None", "<NA>"]), col] = pd.NA

    lookup["k_w"] = norm_key(lookup["WD25NM"])
    lookup["k_l"] = norm_key(lookup["LAD25NM"])
    lookup = lookup.drop_duplicates()
    print(f"[INFO] Lookup rows: {len(lookup):,}")
    return lookup


def attach_lookup_to_wards(wards: gpd.GeoDataFrame, lookup: pd.DataFrame) -> gpd.GeoDataFrame:
    print("[STEP] Joining ward polygons to lookup by WD25CD")
    by_code = wards.merge(lookup, on="WD25CD", how="left", suffixes=("", "_lk"))

    matched_code = by_code["CED25CD"].notna() | by_code["CTY25CD"].notna()
    unresolved = by_code[~matched_code].copy()
    resolved = by_code[matched_code].copy()

    print(f"[INFO] Matched by code: {len(resolved):,}; unresolved: {len(unresolved):,}")

    if unresolved.empty:
        return resolved

    print("[STEP] Resolving unmatched wards by normalized name + LAD fallback")
    lk_fallback = lookup[
        ["k_w", "k_l", "CTY25CD", "CTY25NM", "CED25CD", "CED25NM", "LAD25CD", "LAD25NM"]
    ].drop_duplicates(subset=["k_w", "k_l"])

    fallback = unresolved.merge(
        lk_fallback,
        on=["k_w", "k_l"],
        how="left",
        suffixes=("", "_fb"),
    )

    for col in ["CTY25CD", "CTY25NM", "CED25CD", "CED25NM"]:
        fallback[col] = fallback[col].fillna(fallback.get(f"{col}_fb"))

    still_unresolved = fallback["CED25CD"].isna() & fallback["CTY25CD"].isna()
    print(f"[INFO] Resolved by fallback: {(~still_unresolved).sum():,}; still unresolved: {still_unresolved.sum():,}")

    keep_cols = [c for c in fallback.columns if not c.endswith("_fb")]
    final = pd.concat([resolved, fallback[keep_cols]], ignore_index=True)
    return gpd.GeoDataFrame(final, geometry="geometry", crs=wards.crs)


def build_county_divisions(ward_with_lookup: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("[STEP] Building county electoral divisions (county councils)")
    county = ward_with_lookup[
        ward_with_lookup["CTY25CD"].notna() & ward_with_lookup["CED25CD"].notna()
    ].copy()

    county_div = county.dissolve(
        by="CED25CD",
        as_index=False,
        aggfunc={
            "CED25NM": "first",
            "CTY25CD": "first",
            "CTY25NM": "first",
        },
    )

    county_div["authority_type"] = "county_council"
    county_div["authority_code"] = county_div["CTY25CD"]
    county_div["authority_name"] = county_div["CTY25NM"]
    county_div["geo_code"] = county_div["CED25CD"]
    county_div["geo_name"] = county_div["CED25NM"]
    print(f"[INFO] County divisions: {len(county_div):,}")
    return county_div


def build_unitary_wards(ward_with_lookup: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("[STEP] Building unitary authority ward boundaries")
    # In the lookup, unitary authorities typically have no CTY code.
    unitary = ward_with_lookup[ward_with_lookup["CTY25CD"].isna()].copy()

    unitary["authority_type"] = "unitary_authority"
    unitary["authority_code"] = unitary["LAD25CD"]
    unitary["authority_name"] = unitary["LAD25NM"]
    unitary["geo_code"] = unitary["WD25CD"]
    unitary["geo_name"] = unitary["WD25NM"]

    keep = [
        "authority_type",
        "authority_code",
        "authority_name",
        "geo_code",
        "geo_name",
        "LAD25CD",
        "LAD25NM",
        "geometry",
    ]
    unitary = unitary[keep]
    print(f"[INFO] Unitary wards: {len(unitary):,}")
    return unitary


def save_outputs(
    county_divisions: gpd.GeoDataFrame,
    unitary_wards: gpd.GeoDataFrame,
    out_dir: Path,
    simplify_tolerance: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    if simplify_tolerance > 0:
        county_divisions = county_divisions.copy()
        unitary_wards = unitary_wards.copy()
        county_divisions["geometry"] = county_divisions.geometry.simplify(
            tolerance=simplify_tolerance,
            preserve_topology=True,
        )
        unitary_wards["geometry"] = unitary_wards.geometry.simplify(
            tolerance=simplify_tolerance,
            preserve_topology=True,
        )

    county_path = out_dir / "england_county_council_divisions.geojson"
    unitary_path = out_dir / "england_unitary_authority_wards.geojson"
    county_divisions.to_file(county_path, driver="GeoJSON")
    unitary_wards.to_file(unitary_path, driver="GeoJSON")

    print(f"[DONE] Wrote county divisions: {county_path}")
    print(f"[DONE] Wrote unitary wards: {unitary_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build England-wide county council division and unitary authority ward boundaries "
            "from ONS geometry + lookup inputs."
        )
    )
    parser.add_argument(
        "--geometry",
        type=Path,
        default=Path("data") / "OA_2021_EW_BGC_V2.shp",
        help=(
            "ONS geometry source. Either a WD/LAD-enriched geometry file, or OA/LSOA geometry "
            "that can be bridged with --lsoa-ward-lookup."
        ),
    )
    parser.add_argument(
        "--lsoa-ward-lookup",
        type=Path,
        default=Path("data") / "csv" / "LSOA_(2021)_to_Electoral_Ward_(2025)_to_LAD_(2025)_Best_Fit_Lookup_in_EW_v2.csv",
        help="ONS LSOA->Ward->LAD lookup used when geometry lacks WD/LAD columns.",
    )
    parser.add_argument(
        "--lookup",
        type=Path,
        default=Path("Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2025)_Lookup_for_EN.csv"),
        help="ONS ward->LAD->county->CED lookup CSV.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data") / "processed",
        help="Output directory for generated GeoJSON files.",
    )
    parser.add_argument(
        "--simplify",
        type=float,
        default=0.00005,
        help="Geometry simplify tolerance in EPSG:4326 units (0 disables simplification).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ensure_required_inputs(args.geometry, args.lookup, args.lsoa_ward_lookup)
    wards = load_and_prepare_ward_geometry(args.geometry, args.lsoa_ward_lookup)
    lookup = load_lookup(args.lookup)
    joined = attach_lookup_to_wards(wards, lookup)

    county_divisions = build_county_divisions(joined)
    unitary_wards = build_unitary_wards(joined)

    save_outputs(county_divisions, unitary_wards, args.out_dir, args.simplify)


if __name__ == "__main__":
    main()
