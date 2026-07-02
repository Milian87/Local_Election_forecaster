import os
import glob
import re
import traceback
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def locate_column(candidates, df):
    """Return the first column name present in df from a priority list."""
    for col in candidates:
        if col in df.columns:
            return col
    return None

def clean_party_string(val):
    """Standardize party strings and strip common descriptive variations."""
    if pd.isna(val): 
        return "Independent"
    s = str(val).strip().lower()
    
    if "conservative" in s: return "Conservative"
    if "labour" in s: return "Labour"
    if "liberal democrat" in s: return "Liberal Democrats"
    if "green party" in s or s == "green": return "Green Party"
    if "reform" in s: return "Reform UK"
    if "independent" in s: return "Independent"
    if "ukip" in s or "independence party" in s: return "UK Independence Party (UKIP)"
    
    mapping = {
        'con': 'Conservative', 'lab': 'Labour', 'ld': 'Liberal Democrats', 'ind': 'Independent'
    }
    return mapping.get(s, str(val).strip())


def parse_election_date_series(series):
    """Return datetime-like parsed election date series using UK-first mixed parsing."""
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


COUNCIL_ALIASES = {
    "Bedfordshire County Council": "Central Bedfordshire Council",
    "Dorset County Council": "Dorset Council",
    "Cumbria County Council": "Cumberland County Council",
    "County Durham": "Durham County Council",
    "Durham Council": "Durham County Council",
    "Herefordshire County Council": "Herefordshire Council",
    "Herefordshire, County of": "Herefordshire Council",
    "Cornwall County Council": "Cornwall Council",
    "Worestshire County Council": "Worcestershire County Council",
}


def normalize_council_name(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = text.replace("county council", "")
    text = text.replace("council", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonicalize_council_name(value):
    if pd.isna(value):
        return "Unknown Upper Tier Authority"
    raw = str(value).strip()
    if raw in COUNCIL_ALIASES:
        return COUNCIL_ALIASES[raw]

    normalized_alias_lookup = {
        normalize_council_name(alias): canonical
        for alias, canonical in COUNCIL_ALIASES.items()
    }
    return normalized_alias_lookup.get(normalize_council_name(raw), raw)


def build_ward_authority_map(lookups_dir):
    """Map WD/CED geography code to canonical authority code (CTY when present, else LAD)."""
    ward_map = {}
    composite_files = glob.glob(os.path.join(lookups_dir, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv"))
    flat_files = glob.glob(os.path.join(lookups_dir, "Ward_to_Local_Authority_District_*.csv"))
    files = composite_files + flat_files

    for file_path in files:
        try:
            sample = pd.read_csv(file_path, nrows=2, low_memory=False)
            cols = sample.columns.tolist()
            wd_col = next((c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'), None)
            ced_col = next((c for c in cols if re.match(r'CED\d+CD', c) or c == 'CEDCD'), None)
            lad_col = next((c for c in cols if re.match(r'LAD\d+CD', c) or c == 'LADCD'), None)
            cty_col = next((c for c in cols if re.match(r'CTY\d+CD', c) or c == 'CTYCD'), None)
            if not lad_col or (not wd_col and not ced_col):
                continue
            use_cols = [c for c in [wd_col, ced_col, lad_col, cty_col] if c]
            df = pd.read_csv(file_path, usecols=use_cols, low_memory=False)

            for _, row in df.iterrows():
                lad_code = str(row[lad_col]).strip() if pd.notna(row[lad_col]) else ""
                cty_code = str(row[cty_col]).strip() if cty_col and pd.notna(row[cty_col]) else ""
                chosen_code = cty_code if cty_code and cty_code.lower() != "nan" else lad_code
                if chosen_code and chosen_code.lower() != "nan":
                    if wd_col and pd.notna(row.get(wd_col)):
                        wd = str(row[wd_col]).strip()
                        if wd:
                            ward_map[wd] = chosen_code
                    if ced_col and pd.notna(row.get(ced_col)):
                        ced = str(row[ced_col]).strip()
                        if ced:
                            ward_map[ced] = chosen_code
        except Exception:
            continue

    return ward_map

# =========================================================================
# 1. DATABASE CONNECTION MANAGEMENT PROFILE
# =========================================================================
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Xabp74yb%'),
    'database': os.getenv('MYSQL_DB', 'irp_election_forecasting')
}

engine = create_engine(
    f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[SUCCESS] Connected to MySQL database.")
    print("==============================================")
except OperationalError as exc:
    raise RuntimeError("Database login failed. Verify user privileges and schema profiles.") from exc

# =========================================================================
# 2. FILE BATCH DIRECTORY SCANNING SETUP
# =========================================================================
repo_root = os.path.dirname(os.path.abspath(__file__))
default_input_folder = os.path.join(repo_root, "data", "election_results", "processed")

# Prefer this workspace's processed exports; legacy path remains only as fallback.
input_folder = os.getenv("RESULTS_INPUT_FOLDER", default_input_folder)
if not os.path.exists(input_folder):
    legacy_folder = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results\processed"
    input_folder = legacy_folder if os.path.exists(legacy_folder) else repo_root

lookups_folder = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\Lookups"
ward_to_authority = build_ward_authority_map(lookups_folder)
print(f"Loaded {len(ward_to_authority):,} ward->authority mappings for canonical cc_code assignment.")

target_files = []
try:
    print(f"Scanning input folder: {input_folder}")
    target_files = [f for f in os.listdir(input_folder) if f.startswith("target_council_results_") and f.endswith(".csv")]
    print(f"Found {len(target_files)} target datasets awaiting database ingestion.")
    print("------------------------------------------------------------")
except Exception as e:
    print(f"[ERROR] Failed to read directory content: {e}")

try:
    with engine.connect() as conn:
        db_vote_share_col = conn.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :schema_name AND TABLE_NAME = 'election_results'
              AND COLUMN_NAME IN ('vote_share_pc', 'vote_share')
            ORDER BY CASE COLUMN_NAME WHEN 'vote_share_pc' THEN 1 ELSE 2 END LIMIT 1
        """), {"schema_name": db_config['database']}).scalar()

        election_results_columns = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = :schema_name
                      AND TABLE_NAME = 'election_results'
                    """
                ),
                {"schema_name": db_config['database']},
            ).fetchall()
        }
except Exception as e:
    raise RuntimeError(f"FATAL: Database schema query failed. Error: {e}")

# Ensure clean slate tables exist
with engine.connect() as conn:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS electoral_wards_history (
                wd_code VARCHAR(20) NOT NULL,
                election_year INT NOT NULL,
                ward_name VARCHAR(255) NOT NULL,
                cc_code VARCHAR(20) NOT NULL,
                PRIMARY KEY (wd_code, election_year)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    conn.commit()

PURGE_ON_RUN = os.getenv('PURGE_ON_RUN', 'false').strip().lower() in {'1', 'true', 'yes', 'y'}
if PURGE_ON_RUN:
    print("[WARNING] Purging prior ingestion state to eliminate boundary alignment drift...")
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("TRUNCATE TABLE election_results;"))
        conn.execute(text("TRUNCATE TABLE electoral_wards_history;"))
        conn.execute(text("TRUNCATE TABLE electoral_wards;"))
        conn.execute(text("TRUNCATE TABLE candidates;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        conn.commit()
    print("[SUCCESS] Relational staging baseline cleared.")

# =========================================================================
# 3. CORE BATCH PROCESSING LOOP
# =========================================================================
for file_name in sorted(target_files):
    year_match = re.search(r"\d{4}", file_name)
    file_year = int(year_match.group()) if year_match else 2025
    
    file_path = os.path.join(input_folder, file_name)
    print(f"\n[Ingesting Cycle Folder Year {file_year}] --> Processing File: {file_name}")
    
    try:
        df_flat = pd.read_csv(file_path, low_memory=False)
    except Exception as e:
        print(f"   [SKIP ERROR] Failed to read file {file_name}: {e}")
        continue
    
    ward_code_col = locate_column(['ward_code', 'wd_code'], df_flat)
    ward_name_col = locate_column(['ward_name'], df_flat)
    party_col = locate_column(['party_description', 'party_name', 'registered_party'], df_flat)
    council_col = locate_column(['council_name', 'organisation_name'], df_flat)
    
    if not ward_code_col or not ward_name_col or not party_col:
        print(f"   [SKIP] Missing core schema columns in {file_name}.")
        continue
        
    df_flat['candidate_name'] = df_flat['candidate_name'].fillna('').astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    df_flat['clean_party'] = df_flat[party_col].apply(clean_party_string)
    df_flat['clean_ward_code'] = df_flat[ward_code_col].fillna('').astype(str).str.strip()
    if council_col:
        df_flat['clean_council_name'] = df_flat[council_col].apply(canonicalize_council_name)
    else:
        df_flat['clean_council_name'] = 'Unknown Upper Tier Authority'
    
    df_flat = df_flat[df_flat['candidate_name'] != ''].copy()

    # --- DATE PARSING FIX BLOCK ---
    date_col = locate_column(['election_date'], df_flat)
    if date_col:
        # Evaluate row-by-row with strict priority to UK styles, avoiding NaT errors.
        parsed_dates = parse_election_date_series(df_flat[date_col])
        df_flat['election_date'] = parsed_dates.dt.strftime('%Y-%m-%d')
        explicit_year = pd.to_numeric(df_flat['election_year'], errors='coerce') if 'election_year' in df_flat.columns else pd.Series(index=df_flat.index, dtype='float64')
        # Assign dynamic year with explicit election_year taking precedence when present.
        df_flat['row_election_year'] = explicit_year.fillna(parsed_dates.dt.year).fillna(file_year).astype(int)
    else:
        if 'election_year' in df_flat.columns:
            df_flat['row_election_year'] = pd.to_numeric(df_flat['election_year'], errors='coerce').fillna(file_year).astype(int)
        else:
            df_flat['row_election_year'] = file_year

    # -------------------------------------------------------------------------
    # STEP A: DIMENSIONS
    # -------------------------------------------------------------------------
    try:
        df_flat['derived_cc_code'] = df_flat['clean_ward_code'].map(ward_to_authority)
        df_flat = df_flat[df_flat['derived_cc_code'].notna()].copy()
        if len(df_flat) == 0:
            print(f"   [SKIP] No ward->authority matches in {file_name}.")
            continue
        df_counties = df_flat[['derived_cc_code', 'clean_council_name']].drop_duplicates().dropna()
        with engine.connect() as conn:
            county_rows = df_counties.rename(columns={'derived_cc_code': 'cc_code', 'clean_council_name': 'council_name'}).to_dict(orient='records')
            conn.execute(text("""
                INSERT INTO county_codes (cc_code, council_name) VALUES (:cc_code, :council_name)
                ON DUPLICATE KEY UPDATE council_name = VALUES(council_name)
            """), county_rows)
            conn.commit()

        df_wards_current = df_flat.sort_values(['clean_ward_code', 'row_election_year']).drop_duplicates(subset=['clean_ward_code'], keep='last')[['clean_ward_code', ward_name_col, 'derived_cc_code']].dropna()

        history_base = df_flat[['clean_ward_code', ward_name_col, 'derived_cc_code', 'row_election_year']].dropna().copy()
        history_base = history_base.reset_index().rename(columns={'index': '_src_order'})
        history_ranked = (
            history_base
            .groupby(['clean_ward_code', 'row_election_year', ward_name_col, 'derived_cc_code'], as_index=False)
            .agg(name_count=('_src_order', 'size'), first_seen=('_src_order', 'min'))
            .sort_values(['clean_ward_code', 'row_election_year', 'name_count', 'first_seen'], ascending=[True, True, False, True])
        )
        df_wards_history = history_ranked.drop_duplicates(subset=['clean_ward_code', 'row_election_year'], keep='first')[['clean_ward_code', ward_name_col, 'derived_cc_code', 'row_election_year']]

        with engine.connect() as conn:
            ward_rows = df_wards_current.rename(columns={'clean_ward_code': 'wd_code', ward_name_col: 'ward_name', 'derived_cc_code': 'cc_code'}).to_dict(orient='records')
            conn.execute(text("""
                INSERT INTO electoral_wards (wd_code, ward_name, cc_code) VALUES (:wd_code, :ward_name, :cc_code)
                ON DUPLICATE KEY UPDATE ward_name = VALUES(ward_name), cc_code = VALUES(cc_code)
            """), ward_rows)
            
            history_rows = df_wards_history.rename(columns={'clean_ward_code': 'wd_code', ward_name_col: 'ward_name', 'derived_cc_code': 'cc_code', 'row_election_year': 'election_year'}).to_dict(orient='records')
            conn.execute(text("""
                INSERT INTO electoral_wards_history (wd_code, election_year, ward_name, cc_code) VALUES (:wd_code, :election_year, :ward_name, :cc_code)
                ON DUPLICATE KEY UPDATE ward_name = VALUES(ward_name), cc_code = VALUES(cc_code)
            """), history_rows)
            conn.commit()
    except Exception as e:
        print(f"   [ERROR STEP A] Dimension update skipped: {e}")
        continue

    # -------------------------------------------------------------------------
    # STEP B: POPULATE CANDIDATES
    # -------------------------------------------------------------------------
    try:
        df_candidates = df_flat[['candidate_name', 'clean_party']].drop_duplicates().copy()
        with engine.connect() as conn:
            for _, row in df_candidates.iterrows():
                conn.execute(text("""
                    INSERT INTO candidates (candidate_name, registered_party)
                    SELECT :name, :party WHERE NOT EXISTS (
                        SELECT 1 FROM candidates WHERE candidate_name = :name AND registered_party = :party
                    );
                """), {"name": row['candidate_name'], "party": row['clean_party']})
            conn.commit()
    except Exception as e:
        print(f"   [ERROR STEP B] Candidate listing skipped: {e}")
        continue

    # -------------------------------------------------------------------------
    # STEP C: RESOLVE GENERATED DB KEYS
    # -------------------------------------------------------------------------
    try:
        df_db_candidates = pd.read_sql("SELECT candidate_id, candidate_name, registered_party FROM candidates", con=engine)
        df_db_candidates = df_db_candidates.rename(columns={'candidate_id': 'resolved_candidate_id'})
        
        df_flat['join_name'] = df_flat['candidate_name'].astype(str).str.lower().str.strip()
        df_flat['join_party'] = df_flat['clean_party'].astype(str).str.lower().str.strip()
        
        df_db_candidates['join_name'] = df_db_candidates['candidate_name'].astype(str).str.lower().str.strip()
        df_db_candidates['join_party'] = df_db_candidates['registered_party'].astype(str).str.lower().str.strip()
        
        df_staged_results = pd.merge(
            df_flat, 
            df_db_candidates[['resolved_candidate_id', 'join_name', 'join_party']], 
            on=['join_name', 'join_party'],
            how='inner'
        )

        df_flat = df_flat.drop(columns=['join_name', 'join_party'])
        if len(df_staged_results) == 0:
            print(f"   [SKIP] Keys alignment matched 0 rows for {file_name}.")
            continue
    except Exception as e:
        print(f"   [ERROR STEP C] Key mapping skipped: {e}")
        continue

    # -------------------------------------------------------------------------
    # STEP D: STRUCTURAL PARAMETER TRANSLATION
    # -------------------------------------------------------------------------
    try:
        seats_col = next((col for col in ['seats_available', 'seats_contested', 'seats'] if col in df_staged_results.columns), None)
        uncontested_col = next((col for col in ['is_uncontested', 'uncontested'] if col in df_staged_results.columns), None)
        elected_col = next((col for col in ['is_elected', 'elected'] if col in df_staged_results.columns), None)
        incumbent_col = next((col for col in ['is_incumbent_cllr', 'incumbent', 'is_incumbent'] if col in df_staged_results.columns), None)
        poll_col = locate_column(['national_poll_party_share', 'national_poll'], df_staged_results)
        closeness_col = locate_column(['prior_ward_closeness_margin', 'closeness_margin'], df_staged_results)
        vote_count_col = locate_column(['votes_received', 'vote_count', 'votes', 'votes_cast', 'votes_cast (helper)'], df_staged_results)
        vote_share_col = locate_column(['vote_share_pc', 'vote_share_value', 'vote_share', 'vote_share_percent'], df_staged_results)

        df_core_results = pd.DataFrame()
        df_core_results['wd_code'] = df_staged_results['clean_ward_code']
        df_core_results['candidate_id'] = pd.to_numeric(df_staged_results['resolved_candidate_id']).astype(int)
        df_core_results['election_date'] = df_staged_results['election_date']
        
        # Fallback date calculation for rows lacking timestamp metrics
        null_dates = df_core_results['election_date'].isna()
        if null_dates.any():
            df_core_results.loc[null_dates, 'election_date'] = df_staged_results.loc[null_dates, 'row_election_year'].apply(lambda y: f"{int(y)}-05-01")

        df_core_results['election_year'] = df_staged_results['row_election_year']
        df_core_results['votes_received'] = pd.to_numeric(df_staged_results[vote_count_col].astype(str).str.replace(',', '', regex=False).str.replace(' Elected', '', regex=False), errors='coerce').fillna(0).astype(int) if vote_count_col else 0
        df_core_results['vote_share_value'] = pd.to_numeric(df_staged_results[vote_share_col].astype(str).str.replace('%', '', regex=False), errors='coerce').fillna(0.0) if vote_share_col else 0.0
        df_core_results['seats_available'] = pd.to_numeric(df_staged_results[seats_col], errors='coerce').fillna(1).astype(int) if seats_col else 1
        df_core_results['is_uncontested'] = df_staged_results[uncontested_col].astype(str).str.lower().isin(['true', '1', 't', 'yes', 'y']).astype(int) if uncontested_col else 0
        df_core_results['is_elected'] = df_staged_results[elected_col].astype(str).str.lower().isin(['true', '1', 't', 'yes', 'y']).astype(int) if elected_col else 0
        df_core_results['is_incumbent_cllr'] = df_staged_results[incumbent_col].astype(str).str.lower().isin(['true', '1', 't', 'yes', 'y']).astype(int) if incumbent_col else 0
        df_core_results['national_poll_party_share'] = pd.to_numeric(df_staged_results[poll_col], errors='coerce').fillna(0.0) if poll_col else 0.0
        df_core_results['prior_ward_closeness_margin'] = pd.to_numeric(df_staged_results[closeness_col], errors='coerce').fillna(0.0) if closeness_col else 0.0

        df_core_results = df_core_results.where(pd.notnull(df_core_results), None)
    except Exception as e:
        print(f"   [ERROR STEP D] Metric transformation skipped: {e}")
        continue

    # -------------------------------------------------------------------------
    # STEP E: COMMIT
    # -------------------------------------------------------------------------
    try:
        insert_columns = ['wd_code', 'election_date', 'candidate_id', 'seats_available', 'is_uncontested', 'votes_received', db_vote_share_col]
        optional_columns = ['election_year', 'is_elected', 'is_incumbent_cllr', 'national_poll_party_share', 'prior_ward_closeness_margin']
        for col in optional_columns:
            if col in election_results_columns:
                insert_columns.append(col)

        value_expr = [':vote_share_value' if col == db_vote_share_col else f':{col}' for col in insert_columns]
        update_columns = [col for col in insert_columns if col not in {'wd_code', 'election_date', 'candidate_id'}]

        election_results_upsert_sql = f"""
            INSERT INTO election_results ({', '.join(insert_columns)}) VALUES ({', '.join(value_expr)})
            ON DUPLICATE KEY UPDATE {', '.join([f'{col} = VALUES({col})' for col in update_columns])}
        """

        result_rows = df_core_results.astype(object).where(pd.notnull(df_core_results), None).to_dict(orient='records')
        with engine.connect() as conn:
            for i in range(0, len(result_rows), 5000):
                conn.execute(text(election_results_upsert_sql), result_rows[i:i+5000])
            conn.commit()
        print(f"   Success! Ingested {len(result_rows):,} records.")
    except Exception as e:
        print(f"   [ERROR STEP E] SQL Upsert Execution crashed: {e}")
        continue

print("\n=============================================")
print("🎯 Batch loading process finished.")
print("=============================================")