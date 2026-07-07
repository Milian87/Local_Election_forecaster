import os
import re
import pandas as pd
import glob

# Canonical list of target councils to extract data for
target_councils = [
    "Norfolk County Council",
    "Suffolk County Council",
    "Essex County Council",
    "Central Bedfordshire Council",
    "Cambridgeshire County Council",
    "Cornwall Council",
    "Cumberland County Council",
    "Devon County Council",
    "Dorset Council",
    "Dorset County Council",
    "Derbyshire County Council",
    "Durham County Council",
    "Gloucestershire County Council",
    "Hampshire County Council",
    "Herefordshire Council",
    "Kent County Council",
    "Lincolnshire County Council",
    "North Yorkshire County Council",
    "Oxfordshire County Council",
    "Shropshire Council",
    "Staffordshire County Council",
    "Surrey County Council",
    "Warwickshire County Council",
    "West Sussex County Council",
    "Worcestershire County Council"
]

# Historical/variant authority labels mapped to canonical targets.
council_aliases = {
    "Bedfordshire County Council": "Central Bedfordshire Council",
    "Dorset County Council": "Dorset Council",
    "Cumbria County Council": "Cumberland County Council",
    "County Durham": "Durham County Council",
    "Durham Council": "Durham County Council",
    "Herefordshire County Council": "Herefordshire Council",
    "Herefordshire, County of": "Herefordshire Council",
    "Cornwall County Council": "Cornwall Council",
    "Worestshire County Council": "Worcestershire County Council"
}


def _norm_council_name(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = text.replace("county council", "")
    text = text.replace("council", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_geo_name(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_division_name(value):
    text = _norm_geo_name(value)
    text = re.sub(r"\bed\b$", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Manual disambiguation for known county-division name collisions in 2026 source data.
# Keys are normalized as (normalized council name, normalized ward/division label).
MANUAL_COUNTY_CED_OVERRIDES = {
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Erpingham")): "E58001013",  # North Walsham West and Erpingham ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Hoveton")): "E58000995",   # Hoveton and Stalham ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Launditch")): "E58001009", # Necton and Launditch ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Stalham")): "E58000995",   # Hoveton and Stalham ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Coltishall & Spixworth")): "E58000992",      # Hevingham and Spixworth ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Dereham North & Scarning")): "E58000969",    # Dereham North ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Fakenham & The Raynhams")): "E58000980",     # Fakenham ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Nar & Wissey Valleys")): "E58000985",        # Gayton and Nar Valley ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("North Caister & Ormesby")): "E58000962",     # Caister-on-Sea ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("North Walsham West & Mundesley")): "E58001008",  # Mundesley ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("South Caister & Bure")): "E58000964",        # Clavering ED (best-fit)
    (_norm_council_name("Norfolk County Council"), _norm_division_name("The Fleggs")): "E58001034",                  # West Flegg ED (best-fit)
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Watlington & The Fens")): "E58000982",      # Fincham ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Waveney Valley")): "E58000977",              # East Flegg ED (best-fit)
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Yare & Necton")): "E58001038",               # Yare and All Saints ED
    (_norm_council_name("Norfolk County Council"), _norm_division_name("Yare Valley")): "E58001018",                 # South Smallburgh ED (best-fit)
}


def _parse_election_dates(series):
    s = series.astype(str).str.strip()
    s = s.replace({'': pd.NA, 'nan': pd.NA, 'None': pd.NA})
    parsed = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')

    # Parse year-first formats explicitly to avoid day/month inversion (e.g. 2025-05-01).
    year_first_mask = s.str.match(r'^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$', na=False)
    if year_first_mask.any():
        parsed.loc[year_first_mask] = pd.to_datetime(
            s.loc[year_first_mask],
            format='mixed',
            dayfirst=False,
            errors='coerce',
        )

    # Parse remaining values with UK day-first priority.
    remaining_mask = ~year_first_mask
    if remaining_mask.any():
        parsed.loc[remaining_mask] = pd.to_datetime(
            s.loc[remaining_mask],
            format='mixed',
            dayfirst=True,
            errors='coerce',
        )

    return parsed


def _build_lookup_geo_maps(lookups_dir):
    """Build fallback maps from lookup geography names to WD/CED codes."""
    by_council = {}
    unique_name_codes = {}

    files = glob.glob(os.path.join(lookups_dir, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv"))
    files += glob.glob(os.path.join(lookups_dir, "Ward_to_Local_Authority_District_*.csv"))

    for file_path in files:
        try:
            sample = pd.read_csv(file_path, nrows=2, low_memory=False)
            cols = sample.columns.tolist()

            wd_code_col = next((c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'), None)
            wd_name_col = next((c for c in cols if re.match(r'WD\d+NM', c) or c == 'WDNM'), None)
            ced_code_col = next((c for c in cols if re.match(r'CED\d+CD', c) or c == 'CEDCD'), None)
            ced_name_col = next((c for c in cols if re.match(r'CED\d+NM', c) or c == 'CEDNM'), None)
            cty_name_col = next((c for c in cols if re.match(r'CTY\d+NM', c) or c == 'CTYNM'), None)
            lad_name_col = next((c for c in cols if re.match(r'LAD\d+NM', c) or c == 'LADNM'), None)

            use_cols = [
                c for c in [
                    wd_code_col,
                    wd_name_col,
                    ced_code_col,
                    ced_name_col,
                    cty_name_col,
                    lad_name_col,
                ]
                if c
            ]
            if not use_cols:
                continue

            df_lookup = pd.read_csv(file_path, usecols=use_cols, low_memory=False)

            for _, row in df_lookup.iterrows():
                council_name = ""
                if cty_name_col and pd.notna(row.get(cty_name_col)):
                    council_name = str(row[cty_name_col]).strip()
                elif lad_name_col and pd.notna(row.get(lad_name_col)):
                    council_name = str(row[lad_name_col]).strip()
                norm_council = _norm_council_name(council_name)

                pairs = []
                if wd_code_col and wd_name_col and pd.notna(row.get(wd_code_col)) and pd.notna(row.get(wd_name_col)):
                    pairs.append((_norm_geo_name(row[wd_name_col]), str(row[wd_code_col]).strip()))
                if ced_code_col and ced_name_col and pd.notna(row.get(ced_code_col)) and pd.notna(row.get(ced_name_col)):
                    pairs.append((_norm_geo_name(row[ced_name_col]), str(row[ced_code_col]).strip()))

                for norm_name, code in pairs:
                    if not norm_name or not code or code.lower() == 'nan':
                        continue
                    if norm_council:
                        by_council.setdefault((norm_council, norm_name), code)
                    unique_name_codes.setdefault(norm_name, set()).add(code)
        except Exception:
            continue

    unique_name_map = {name: next(iter(codes)) for name, codes in unique_name_codes.items() if len(codes) == 1}
    return by_council, unique_name_map


def _build_2025_fallback_map(file_path):
    """Build a unique council+ward -> wd_code map from 2025 extracted results."""
    if not os.path.exists(file_path):
        return {}

    try:
        df_2025 = pd.read_csv(file_path, low_memory=False)
    except Exception:
        return {}

    required = {'council_name', 'ward_name', 'wd_code'}
    if not required.issubset(df_2025.columns):
        return {}

    df_2025 = df_2025.copy()
    df_2025['wd_code'] = df_2025['wd_code'].fillna('').astype(str).str.strip()
    df_2025 = df_2025[df_2025['wd_code'] != '']
    if len(df_2025) == 0:
        return {}

    df_2025['k_council'] = df_2025['council_name'].map(_norm_council_name)
    df_2025['k_ward'] = df_2025['ward_name'].map(_norm_geo_name)
    df_2025['k_key'] = list(zip(df_2025['k_council'], df_2025['k_ward']))

    grouped = df_2025.groupby('k_key')['wd_code'].agg(lambda s: set(s)).to_dict()
    return {k: next(iter(v)) for k, v in grouped.items() if len(v) == 1}


def _build_recent_history_maps(processed_dir):
    """Build per-year unique council+ward -> wd_code maps from historical processed files."""
    year_maps = {}
    files = [f for f in os.listdir(processed_dir) if f.startswith("target_council_results_") and f.endswith("_clean.csv")]

    for file_name in files:
        m = re.search(r"(\d{4})", file_name)
        if not m:
            continue
        year = int(m.group(1))
        path = os.path.join(processed_dir, file_name)
        try:
            df_hist = pd.read_csv(path, low_memory=False)
        except Exception:
            continue

        required = {'council_name', 'ward_name', 'wd_code'}
        if not required.issubset(df_hist.columns):
            continue

        df_hist = df_hist.copy()
        df_hist['wd_code'] = df_hist['wd_code'].fillna('').astype(str).str.strip()
        df_hist = df_hist[df_hist['wd_code'] != '']
        if len(df_hist) == 0:
            continue

        df_hist['k_council'] = df_hist['council_name'].map(_norm_council_name)
        df_hist['k_ward'] = df_hist['ward_name'].map(_norm_geo_name)
        df_hist['k_key'] = list(zip(df_hist['k_council'], df_hist['k_ward']))

        grouped = df_hist.groupby('k_key')['wd_code'].agg(lambda s: set(s)).to_dict()
        year_maps[year] = {k: next(iter(v)) for k, v in grouped.items() if len(v) == 1}

    return year_maps


def _lookup_file_year(file_path):
    years = [int(value) for value in re.findall(r"20\d{2}", os.path.basename(file_path))]
    return max(years) if years else 0


def _build_current_county_ced_map(lookups_dir):
    """Map latest county-council ward codes/names to current CED codes."""
    files = glob.glob(os.path.join(lookups_dir, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv"))
    if not files:
        return {}

    latest_file = max(files, key=_lookup_file_year)
    try:
        sample = pd.read_csv(latest_file, nrows=2, low_memory=False)
        cols = sample.columns.tolist()
        wd_name_col = next((c for c in cols if re.match(r'WD\d+NM', c) or c == 'WDNM'), None)
        ced_code_col = next((c for c in cols if re.match(r'CED\d+CD', c) or c == 'CEDCD'), None)
        ced_name_col = next((c for c in cols if re.match(r'CED\d+NM', c) or c == 'CEDNM'), None)
        cty_name_col = next((c for c in cols if re.match(r'CTY\d+NM', c) or c == 'CTYNM'), None)
        wd_code_col = next((c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'), None)
        if not wd_code_col or not wd_name_col or not ced_code_col or not cty_name_col:
            return {}, {}

        use_cols = [c for c in [wd_code_col, wd_name_col, ced_code_col, ced_name_col, cty_name_col] if c]
        df_lookup = pd.read_csv(latest_file, usecols=use_cols, low_memory=False)
    except Exception:
        return {}, {}

    grouped_codes = {}
    division_name_codes = {}
    wd_to_ced = {}
    for _, row in df_lookup.iterrows():
        cty_name = str(row[cty_name_col]).strip() if pd.notna(row[cty_name_col]) else ""
        ced_code = str(row[ced_code_col]).strip() if pd.notna(row[ced_code_col]) else ""
        wd_code = str(row[wd_code_col]).strip() if pd.notna(row[wd_code_col]) else ""
        if not cty_name or not ced_code or ced_code.lower() == 'nan':
            continue

        norm_council = _norm_council_name(cty_name)
        if not norm_council:
            continue

        if wd_code and wd_code.lower() != 'nan':
            wd_to_ced[(norm_council, wd_code)] = ced_code

        if ced_name_col and pd.notna(row.get(ced_name_col)):
            norm_division_name = _norm_division_name(row[ced_name_col])
            if norm_division_name:
                division_name_codes.setdefault((norm_council, norm_division_name), set()).add(ced_code)

        name_candidates = []
        if pd.notna(row.get(wd_name_col)):
            name_candidates.append(_norm_geo_name(row[wd_name_col]))
        if ced_name_col and pd.notna(row.get(ced_name_col)):
            name_candidates.append(_norm_geo_name(row[ced_name_col]))

        for norm_name in name_candidates:
            if not norm_name:
                continue
            grouped_codes.setdefault((norm_council, norm_name), set()).add(ced_code)

    unique_name_map = {key: next(iter(codes)) for key, codes in grouped_codes.items() if len(codes) == 1}
    unique_division_name_map = {key: next(iter(codes)) for key, codes in division_name_codes.items() if len(codes) == 1}
    return wd_to_ced, unique_name_map, unique_division_name_map


# Build normalized lookup so renamed/restructured councils can still match target scope.
normalized_target_lookup = {_norm_council_name(name): name for name in target_councils}
for alias_name, canonical_name in council_aliases.items():
    normalized_target_lookup[_norm_council_name(alias_name)] = canonical_name

# Set folder paths
input_folder = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\democracy club"
output_folder_1 = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results"
output_folder_2 = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results\processed"
lookups_folder = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\Lookups"
extraction_unresolved_path = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results\extraction_unresolved_wd_codes.csv"
fallback_2025_file = os.path.join(output_folder_2, "target_council_results_2025_clean.csv")
historical_fallback_years = int(os.getenv("HISTORICAL_WD_FALLBACK_YEARS", "5"))

# Ensure output directories exist
os.makedirs(output_folder_1, exist_ok=True)
os.makedirs(output_folder_2, exist_ok=True)

# Scan for all candidate CSV files in the democracy club directory
democracy_club_files = [f for f in os.listdir(input_folder) if f.endswith('.csv')]
print(f"Found {len(democracy_club_files)} CSV source file(s) inside: {input_folder}")

lookup_by_council, lookup_unique_name = _build_lookup_geo_maps(lookups_folder)
fallback_2025_map = _build_2025_fallback_map(fallback_2025_file)
recent_history_maps = _build_recent_history_maps(output_folder_2)
current_county_wd_to_ced_map, current_county_name_to_ced_map, current_county_division_name_to_ced_map = _build_current_county_ced_map(lookups_folder)
print(f"Loaded {len(lookup_by_council):,} council+name lookup codes and {len(lookup_unique_name):,} globally unique name codes.")
print(f"Loaded {len(fallback_2025_map):,} unique council+ward fallback codes from 2025 results.")
print(f"Loaded recent history maps for {len(recent_history_maps):,} year file(s); lookback window set to {historical_fallback_years} years.")
print(f"Loaded {len(current_county_wd_to_ced_map):,} latest county WD->CED mappings, {len(current_county_name_to_ced_map):,} latest county name->CED mappings and {len(current_county_division_name_to_ced_map):,} exact division-name -> CED mappings.")

# Master list to accumulate rows across all source files
all_processed_rows = []
extraction_unresolved_rows = []

for file_name in democracy_club_files:
    file_path = os.path.join(input_folder, file_name)
    print(f"\n---> Reading File: {file_name}")
    
    try:
        df_massive = pd.read_csv(file_path, low_memory=False)
    except Exception as e:
        print(f"    [SKIP ERROR] Failed to read {file_name}: {e}")
        continue
        
    if 'organisation_name' not in df_massive.columns or 'election_date' not in df_massive.columns:
        print(f"    [SKIP] Missing core columns ('organisation_name' or 'election_date') in {file_name}.")
        continue

    # Normalize authority labels before filtering to absorb historic renames/reorganizations.
    df_massive['canonical_council_name'] = df_massive['organisation_name'].map(
        lambda v: normalized_target_lookup.get(_norm_council_name(v))
    )

    # Filter for rows that map to the canonical target authority list.
    df_filtered = df_massive[df_massive['canonical_council_name'].notna()].copy()
    if len(df_filtered) == 0:
        print(f"    No relevant target council rows found in {file_name}.")
        continue
        
    print(f"    Filtered {len(df_filtered):,} candidate rows matching target councils.")
    
    # --- FIXED DATE PARSING LOGIC ---
    # Convert dates ensuring UK formats (DD/MM/YYYY) take structural priority over US flips
    parsed_dates = _parse_election_dates(df_filtered['election_date'])
    df_filtered['clean_election_date'] = parsed_dates.dt.strftime('%Y-%m-%d')
    df_filtered['election_year'] = parsed_dates.dt.year
    
    # Drop rows where dates couldn't be evaluated at all
    df_filtered = df_filtered.dropna(subset=['election_year'])
    df_filtered['election_year'] = df_filtered['election_year'].astype(int)

    # Standardize data types and database mappings
    df_filtered['votes_cast'] = pd.to_numeric(df_filtered['votes_cast'], errors='coerce').fillna(0).astype(int)
    df_filtered['is_elected'] = df_filtered['elected'].astype(str).str.lower().isin(['t', 'true', '1', 'yes', 'y']).astype(int)
    df_filtered['is_uncontested'] = df_filtered['by_election'].astype(str).str.lower().isin(['t', 'true', '1', 'yes', 'y']).astype(int)
    df_filtered['by_election'] = df_filtered['by_election'].astype(str).str.lower().isin(['t', 'true', '1', 'yes', 'y']).astype(int)

    # Resolve ward/division code with fallback map when source gss is blank.
    if 'gss' in df_filtered.columns:
        df_filtered['wd_code_resolved'] = df_filtered['gss'].fillna('').astype(str).str.strip()
    else:
        df_filtered['wd_code_resolved'] = ''

    council_keys = df_filtered['canonical_council_name'].map(_norm_council_name)
    ward_keys = df_filtered['post_label'].map(_norm_geo_name)

    # For the current cycle, convert county-council ward-style codes/names to the
    # latest county division (CED) code before any blank-code fallback runs.
    current_county_ced_series = pd.Series(
        [
            current_county_wd_to_ced_map.get((c, gss_code), '')
            for c, gss_code in zip(council_keys, df_filtered['wd_code_resolved'])
        ],
        index=df_filtered.index,
    )
    missing_current_ced = current_county_ced_series.eq('')
    if missing_current_ced.any():
        fallback_name_series = pd.Series(
            [current_county_name_to_ced_map.get((c, w), '') for c, w in zip(council_keys, ward_keys)],
            index=df_filtered.index,
        )
        current_county_ced_series.loc[missing_current_ced] = fallback_name_series.loc[missing_current_ced]

    missing_current_ced = current_county_ced_series.eq('')
    if missing_current_ced.any():
        division_keys = df_filtered['post_label'].map(_norm_division_name)
        division_name_series = pd.Series(
            [current_county_division_name_to_ced_map.get((c, d), '') for c, d in zip(council_keys, division_keys)],
            index=df_filtered.index,
        )
        current_county_ced_series.loc[missing_current_ced] = division_name_series.loc[missing_current_ced]

    # Final disambiguation for known ambiguous county ward names.
    missing_current_ced = current_county_ced_series.eq('')
    if missing_current_ced.any() and MANUAL_COUNTY_CED_OVERRIDES:
        manual_series = pd.Series(
            [
                MANUAL_COUNTY_CED_OVERRIDES.get((c, d), '')
                for c, d in zip(council_keys, df_filtered['post_label'].map(_norm_division_name))
            ],
            index=df_filtered.index,
        )
        current_county_ced_series.loc[missing_current_ced] = manual_series.loc[missing_current_ced]
    needs_county_ced = (
        df_filtered['election_year'].eq(2026)
        & current_county_ced_series.ne('')
        & ~df_filtered['wd_code_resolved'].astype(str).str.startswith('E58')
    )
    if needs_county_ced.any():
        df_filtered.loc[needs_county_ced, 'wd_code_resolved'] = current_county_ced_series.loc[needs_county_ced]
        print(f"    [INFO] Remapped {int(needs_county_ced.sum()):,} 2026 county-council rows to current CED codes.")

    blank_mask = df_filtered['wd_code_resolved'].eq('')
    if blank_mask.any():
        council_lookup = [
            lookup_by_council.get((c, w), '')
            for c, w in zip(council_keys, ward_keys)
        ]
        df_filtered.loc[blank_mask, 'wd_code_resolved'] = pd.Series(council_lookup, index=df_filtered.index).loc[blank_mask]

        still_blank = df_filtered['wd_code_resolved'].eq('')
        if still_blank.any():
            unique_lookup = ward_keys.map(lookup_unique_name).fillna('')
            df_filtered.loc[still_blank, 'wd_code_resolved'] = unique_lookup.loc[still_blank]

        # Last fallback: borrow stable keys from 2025 extracted results.
        still_blank = df_filtered['wd_code_resolved'].eq('')
        if still_blank.any() and fallback_2025_map:
            k_keys = list(zip(council_keys, ward_keys))
            from_2025 = [fallback_2025_map.get(k, '') for k in k_keys]
            from_2025_series = pd.Series(from_2025, index=df_filtered.index)
            before_2025 = int(still_blank.sum())
            df_filtered.loc[still_blank, 'wd_code_resolved'] = from_2025_series.loc[still_blank]
            after_2025 = int(df_filtered['wd_code_resolved'].eq('').sum())
            recovered_2025 = before_2025 - after_2025
            if recovered_2025 > 0:
                print(f"    [INFO] Recovered {recovered_2025:,} rows using 2025 council+ward fallback.")

        # Final fallback: use most recent unique code from prior years (default 5-year lookback).
        still_blank = df_filtered['wd_code_resolved'].eq('')
        if still_blank.any() and recent_history_maps:
            unresolved_idx = df_filtered.index[still_blank]
            unresolved_years = df_filtered.loc[unresolved_idx, 'election_year'].astype(int)
            unresolved_keys = list(zip(council_keys.loc[unresolved_idx], ward_keys.loc[unresolved_idx]))

            fallback_values = []
            for key, row_year in zip(unresolved_keys, unresolved_years):
                resolved_code = ''
                for hist_year in range(int(row_year) - 1, int(row_year) - historical_fallback_years - 1, -1):
                    year_map = recent_history_maps.get(hist_year)
                    if not year_map:
                        continue
                    resolved_code = year_map.get(key, '')
                    if resolved_code:
                        break
                fallback_values.append(resolved_code)

            recent_series = pd.Series(fallback_values, index=unresolved_idx)
            before_recent = int(still_blank.sum())
            df_filtered.loc[unresolved_idx, 'wd_code_resolved'] = recent_series
            after_recent = int(df_filtered['wd_code_resolved'].eq('').sum())
            recovered_recent = before_recent - after_recent
            if recovered_recent > 0:
                print(f"    [INFO] Recovered {recovered_recent:,} rows using most recent {historical_fallback_years}-year fallback.")

    unresolved = df_filtered['wd_code_resolved'].eq('')
    if unresolved.any():
        unresolved_cols = [c for c in ['canonical_council_name', 'post_label', 'person_name', 'party_name', 'election_date', 'gss', 'post_id'] if c in df_filtered.columns]
        chunk = df_filtered.loc[unresolved, unresolved_cols].copy()
        chunk['source_file'] = file_name
        extraction_unresolved_rows.append(chunk)
        print(f"    [WARN] {int(unresolved.sum()):,} rows still missing wd_code after extraction fallback.")

    # Select and structure required schema features
    df_staged = pd.DataFrame({
        'wd_code': df_filtered['wd_code_resolved'],
        'ward_name': df_filtered['post_label'],
        'council_name': df_filtered['canonical_council_name'],
        'election_date': df_filtered['clean_election_date'],
        'election_year': df_filtered['election_year'],
        'candidate_id': df_filtered['person_id'],
        'candidate_name': df_filtered['person_name'],
        'party_name': df_filtered['party_name'],
        'seats_available': pd.to_numeric(df_filtered['seats_contested'], errors='coerce').fillna(1).astype(int),
        'is_uncontested': df_filtered['is_uncontested'],
        'by_election': df_filtered['by_election'],
        'votes_received': df_filtered['votes_cast'],
        'is_elected': df_filtered['is_elected'],
        'is_incumbent_cllr': 0  # To be calculated via SQL history loop later
    })
    
    all_processed_rows.append(df_staged)

if extraction_unresolved_rows:
    df_unresolved = pd.concat(extraction_unresolved_rows, ignore_index=True)
    rename_map = {
        'canonical_council_name': 'council_name',
        'post_label': 'ward_name',
        'person_name': 'candidate_name',
        'gss': 'source_gss',
    }
    df_unresolved = df_unresolved.rename(columns=rename_map)
    cols = [
        'source_file',
        'election_date',
        'council_name',
        'ward_name',
        'candidate_name',
        'party_name',
        'source_gss',
        'post_id',
    ]
    existing = [c for c in cols if c in df_unresolved.columns]
    remainder = [c for c in df_unresolved.columns if c not in existing]
    df_unresolved = df_unresolved[existing + remainder]
    report_path_used = extraction_unresolved_path
    try:
        df_unresolved.to_csv(report_path_used, index=False)
    except PermissionError:
        base, ext = os.path.splitext(extraction_unresolved_path)
        report_path_used = f"{base}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        df_unresolved.to_csv(report_path_used, index=False)
        print(f"[WARN] Primary unresolved report file is locked; wrote fallback report instead.")

    print(f"[WARN] Extraction unresolved wd_code rows: {len(df_unresolved):,}")
    print(f"[WARN] Extraction unresolved report written to: {report_path_used}")

if not all_processed_rows:
    print("\n❌ Ingestion finished. No target data was generated.")
    exit()

# Combine processed datasets from all files
df_master_table = pd.concat(all_processed_rows, ignore_index=True)

# Remove rows lacking an actionable candidate identity
df_master_table = df_master_table.dropna(subset=['candidate_name'])
df_master_table = df_master_table[df_master_table['candidate_name'].str.strip() != '']

# --- VOTE SHARE CALCULATION ---
# Group by the true election year and ward label to calculate total votes cast safely
print("\nCalculating precise ward-level vote shares...")
ward_totals = df_master_table.groupby(['election_year', 'ward_name'])['votes_received'].transform('sum')
df_master_table['vote_share_pc'] = (df_master_table['votes_received'] / ward_totals * 100).round(2).fillna(0.0)

# =========================================================================
# DYNAMIC YEAR GROUPING AND EXPORT LAYER
# =========================================================================
print("\nExporting standardized datasets sorted by calendar cycles...")
for year, df_year_batch in df_master_table.groupby('election_year'):
    
    # Sort for clear downstream ingestion logs
    df_year_clean = df_year_batch.sort_values(by=['council_name', 'ward_name', 'vote_share_pc'], ascending=[True, True, False])
    
    # Establish distinct output paths for individual years
    file_name_out = f"target_council_results_{year}_clean.csv"
    out_path_1 = os.path.join(output_folder_1, file_name_out)
    out_path_2 = os.path.join(output_folder_2, file_name_out)
    
    df_year_clean.to_csv(out_path_1, index=False)
    df_year_clean.to_csv(out_path_2, index=False)
    print(f" 🎯 Success! Saved {len(df_year_clean):,} unique candidate rows to year file: {file_name_out}")

print("\n=============================================")
print(" All Democracy Club source data has been cleanly aligned.")
print("=============================================")