import os
import re
import pandas as pd

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


# Build normalized lookup so renamed/restructured councils can still match target scope.
normalized_target_lookup = {_norm_council_name(name): name for name in target_councils}
for alias_name, canonical_name in council_aliases.items():
    normalized_target_lookup[_norm_council_name(alias_name)] = canonical_name

# Set folder paths
input_folder = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\democracy club"
output_folder_1 = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results"
output_folder_2 = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results\processed"

# Ensure output directories exist
os.makedirs(output_folder_1, exist_ok=True)
os.makedirs(output_folder_2, exist_ok=True)

# Scan for all candidate CSV files in the democracy club directory
democracy_club_files = [f for f in os.listdir(input_folder) if f.endswith('.csv')]
print(f"Found {len(democracy_club_files)} CSV source file(s) inside: {input_folder}")

# Master list to accumulate rows across all source files
all_processed_rows = []

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

    # Select and structure required schema features
    df_staged = pd.DataFrame({
        'wd_code': df_filtered['gss'],
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