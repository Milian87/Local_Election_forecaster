import os
import glob
import re
import pandas as pd
import mysql.connector

lookups_folder = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\Lookups"

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Xabp74yb%',
    'database': 'irp_election_forecasting'
}

print("==========================================================")
print("Executing Multi-Vintage Flat Ward Lookup Assembly...")
print("==========================================================\n")

try:
    # 1. Gather ALL flat Ward-to-LAD lookup files (including 2022, 2019, 2016)
    flat_files = glob.glob(os.path.join(lookups_folder, "Ward_to_Local_Authority_District_*.csv"))
    # Also catch shorter provisional names if present
    flat_files.extend(glob.glob(os.path.join(lookups_folder, "*_LU_*.csv")))
    
    print(f"Discovered {len(flat_files)} flat reference files to parse.")
    
    # Unified maps compounding all generations of geographies
    master_historical_map = {}
    master_ced_map = {}
    authority_name_map = {}
    
    for file_path in flat_files:
        f_name = os.path.basename(file_path)
        try:
            # Dynamically detect columns since ONS changes headers by year (WD22CD, WD19CD, WD21CD)
            df_sample = pd.read_csv(file_path, nrows=2)
            cols = df_sample.columns.tolist()
            
            wd_col = [c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'][0]
            lad_col = [c for c in cols if re.match(r'LAD\d+CD', c) or c == 'LADCD'][0]
            
            df = pd.read_csv(file_path, usecols=[wd_col, lad_col], low_memory=False)
            
            # Layer the values into our master dictionary
            for _, row in df.iterrows():
                if pd.notna(row[wd_col]):
                    master_historical_map[str(row[wd_col]).strip()] = str(row[lad_col]).strip()
            print(f" -> Successfully ingested structures from: {f_name}")
        except Exception as e:
            print(f" -> ⚠️ Skipping file format anomaly in {f_name}: {e}")

    # 1b. Gather composite Ward/CED lookup files to backfill county-division-era codes
    composite_files = glob.glob(
        os.path.join(lookups_folder, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv")
    )
    print(f"Discovered {len(composite_files)} composite lookup files to parse.")

    for file_path in composite_files:
        f_name = os.path.basename(file_path)
        try:
            df_sample = pd.read_csv(file_path, nrows=2)
            cols = df_sample.columns.tolist()

            wd_col = next((c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'), None)
            ced_col = next((c for c in cols if re.match(r'CED\d+CD', c) or c == 'CEDCD'), None)
            lad_col = next((c for c in cols if re.match(r'LAD\d+CD', c) or c == 'LADCD'), None)
            lad_nm_col = next((c for c in cols if re.match(r'LAD\d+NM', c) or c == 'LADNM'), None)
            cty_col = next((c for c in cols if re.match(r'CTY\d+CD', c) or c == 'CTYCD'), None)
            cty_nm_col = next((c for c in cols if re.match(r'CTY\d+NM', c) or c == 'CTYNM'), None)

            use_cols = [c for c in [wd_col, ced_col, lad_col, lad_nm_col, cty_col, cty_nm_col] if c is not None]
            if not use_cols:
                print(f" -> ⚠️ Skipping composite file with no recognized columns: {f_name}")
                continue

            df = pd.read_csv(file_path, usecols=use_cols, low_memory=False)

            for _, row in df.iterrows():
                lad_code = str(row[lad_col]).strip() if lad_col and pd.notna(row[lad_col]) else ""
                cty_code = str(row[cty_col]).strip() if cty_col and pd.notna(row[cty_col]) else ""
                preferred_code = cty_code if cty_code and cty_code.lower() != "nan" else lad_code

                if wd_col and pd.notna(row.get(wd_col)) and preferred_code and preferred_code.lower() != "nan":
                    master_historical_map[str(row[wd_col]).strip()] = preferred_code

                if ced_col and pd.notna(row.get(ced_col)) and preferred_code and preferred_code.lower() != "nan":
                    master_ced_map[str(row[ced_col]).strip()] = preferred_code

                if lad_code and lad_code.lower() != "nan" and lad_nm_col and pd.notna(row.get(lad_nm_col)):
                    authority_name_map[lad_code] = str(row[lad_nm_col]).strip()
                if cty_code and cty_code.lower() != "nan" and cty_nm_col and pd.notna(row.get(cty_nm_col)):
                    authority_name_map[cty_code] = f"{str(row[cty_nm_col]).strip()} County Council"

            print(f" -> Successfully ingested structures from: {f_name}")
        except Exception as e:
            print(f" -> ⚠️ Skipping composite file format anomaly in {f_name}: {e}")

    print(f"\nCompiled ward->authority map entries: {len(master_historical_map):,}")
    print(f"Compiled CED->authority map entries: {len(master_ced_map):,}")

    # 2. Extract unresolved database records
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # Ensure we do not mix code systems in one field.
    # Canonical scheme: cc_code stores full authority code (e.g. E06000047/E10000032).
    # lad_code keeps the same full authority value for easier diagnostics.
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = 'electoral_wards'
          AND column_name = 'lad_code';
        """,
        (db_config['database'],)
    )
    lad_col_exists = cursor.fetchone()[0] > 0
    if not lad_col_exists:
        cursor.execute(
            """
            ALTER TABLE electoral_wards
            ADD COLUMN lad_code VARCHAR(20) NULL AFTER cc_code;
            """
        )
        conn.commit()
    
    cursor.execute("SELECT wd_code FROM electoral_wards;")
    all_wards = [row[0] for row in cursor.fetchall() if row[0] is not None]
    print(f"Database contains {len(all_wards):,} total ward records.")

    # 3. Match keys across generations
    update_payload = []
    for wd in all_wards:
        clean_wd = str(wd).strip()
        mapped_code = master_historical_map.get(clean_wd) or master_ced_map.get(clean_wd)
        if mapped_code:
            update_payload.append((mapped_code, mapped_code, clean_wd))

    print(f"Matched {len(update_payload)} rows across all historical vintages.")

    # 4. Bulk stream corrections to your MySQL grid
    if update_payload:
        print("Streaming updates to database table grid...")
        cursor.execute("SET SQL_SAFE_UPDATES = 0;")
        
        batch_size = 5000
        for i in range(0, len(update_payload), batch_size):
            cursor.executemany(
                "UPDATE electoral_wards SET cc_code = %s, lad_code = %s WHERE wd_code = %s;", 
                update_payload[i:i + batch_size]
            )

        for i in range(0, len(update_payload), batch_size):
            cursor.executemany(
                "UPDATE electoral_wards_history SET cc_code = %s WHERE wd_code = %s;",
                [(code, wd_code) for code, _, wd_code in update_payload[i:i + batch_size]],
            )

        # Keep county_codes synchronized with mapped authority codes.
        county_sync_rows = []
        for code, _, _ in update_payload:
            if code in authority_name_map and authority_name_map[code]:
                county_sync_rows.append((code, authority_name_map[code]))
        if county_sync_rows:
            cursor.executemany(
                """
                INSERT INTO county_codes (cc_code, council_name)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE council_name = VALUES(council_name);
                """,
                list(set(county_sync_rows)),
            )

        # Hard guarantee: every electoral_wards.cc_code must exist in county_codes.
        cursor.execute(
            """
            SELECT DISTINCT ew.cc_code
            FROM electoral_wards ew
            LEFT JOIN county_codes cc ON ew.cc_code = cc.cc_code
            WHERE ew.cc_code IS NOT NULL
              AND TRIM(ew.cc_code) <> ''
              AND cc.cc_code IS NULL;
            """
        )
        missing_codes = [str(row[0]).strip() for row in cursor.fetchall()]
        if missing_codes:
            fallback_rows = []
            for code in missing_codes:
                fallback_name = authority_name_map.get(code, f"Authority {code}")
                fallback_rows.append((code, fallback_name))
            cursor.executemany(
                """
                INSERT IGNORE INTO county_codes (cc_code, council_name)
                VALUES (%s, %s);
                """,
                fallback_rows,
            )
            
        cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        conn.commit()
        
        # Final Verification Check
        cursor.execute("SELECT COUNT(*) FROM electoral_wards WHERE cc_code IS NULL OR TRIM(cc_code) = '';")
        blanks_left = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM electoral_wards WHERE lad_code IS NULL OR TRIM(lad_code) = '';")
        lad_missing = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM electoral_wards ew
            LEFT JOIN county_codes cc ON ew.cc_code = cc.cc_code
            WHERE cc.cc_code IS NULL;
            """
        )
        unmatched_cc = cursor.fetchone()[0]

        print(f"\n🎯 [SUCCESS] Ingestion pass complete! Remaining NULL cc_code rows: {blanks_left}")
        print(f"   LAD backfill coverage pending rows (no match found): {lad_missing}")
        print(f"   electoral_wards cc_code values missing in county_codes: {unmatched_cc}")
    else:
        print("\n⚠️ No intersecting rows found between lookup dictionaries and database contents.")

except Exception as e:
    print(f"\n❌ [CRITICAL COMPILER ERROR] Execution halted: {e}")
    if 'conn' in locals() and conn.is_connected():
        conn.rollback()
finally:
    if 'conn' in locals() and conn.is_connected():
        cursor.close()
        conn.close()
        print("Database connection successfully disconnected.")