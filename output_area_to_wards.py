# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# Created: 21/05/2026
# Updated: 31/05/2026 - Configured for Upper-Tier County Council Divisions (E58)

# =========================================================================
# IRP Election Forecasting Program - Geographic Alignment Layer
# Bridges ONS Census Output Areas cleanly to Upper-Tier County Divisions (E58)
# Author: Ian Milburn
# Date: 2026-07-04
# =========================================================================

import os
import re
import pandas as pd
import mysql.connector

def run_geographic_alignment_pipeline():
    print("=============================================================")
    print("🚀 Starting Output Area to County Division Mapping Process...")
    print("=============================================================\n")

    # 1. Establish path resolution dynamically relative to project structure
    project_root = os.path.abspath(os.path.dirname(__file__))
    base_csv_dir = os.path.join(project_root, "data", "csv")
    
    oa_to_lsoa_path = os.path.join(base_csv_dir, "Output_Areas_2021_EW_BGC_V2_2501415973521800973.csv")
    lsoa_to_ward_path = os.path.join(base_csv_dir, "LSOA_(2021)_to_Electoral_Ward_(2025)_to_LAD_(2025)_Best_Fit_Lookup_in_EW_v2.csv")
    ward_to_ced_path = os.path.join(base_csv_dir, "Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2025)_Lookup_for_England.csv")

    # Verify input data availability safely before starting transaction steps
    for file_path in [oa_to_lsoa_path, lsoa_to_ward_path, ward_to_ced_path]:
        if not os.path.exists(file_path):
            print(f"❌ [CRITICAL ERROR] Missing master source file: {os.path.basename(file_path)}")
            print("Please ensure the ONS lookup files are saved inside your data/csv folder.")
            return

    # 2. Local database connection config 
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Xabp74yb%',
        'database': 'irp_election_forecasting'
    }

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        print("📊 [SUCCESS] Connected to local MySQL forecasting engine database.")
    except mysql.connector.Error as err:
        print(f"❌ [ERROR] Database connection failed: {err}")
        return

    # 3. Pull valid targets currently registered in your electoral_wards table (E58 division targets)
    try:
        cursor.execute("SELECT wd_code FROM electoral_wards")
        valid_divisions = set([str(row).strip() for row in cursor.fetchall()])
        print(f"🎯 Found {len(valid_divisions)} active upper-tier division codes (E58) loaded in database.")
    except mysql.connector.Error as err:
        print(f"❌ [ERROR] Failed to fetch active tracking divisions: {err}")
        cursor.close()
        conn.close()
        return

    # 4. Load the ONS master source files into memory frames
    print("📈 Ingesting ONS structural lookup data packets...")
    df_oa = pd.read_csv(oa_to_lsoa_path, usecols=['OA21CD', 'LSOA21CD'])
    df_lsoa_to_ward = pd.read_csv(lsoa_to_ward_path, usecols=['LSOA21CD', 'WD25CD'])
    df_ward_to_ced = pd.read_csv(ward_to_ced_path, usecols=['WD25CD', 'CED25CD'])

    print("🔗 Bridging OAs across structural hierarchies down to boundary lanes...")
    # Clean merge cascades to bridge Census Output Areas directly to May 2025 County Divisions
    df_merged = pd.merge(df_oa, df_lsoa_to_ward, on='LSOA21CD', how='inner')
    df_master_bridge = pd.merge(df_merged, df_ward_to_ced, on='WD25CD', how='inner')

    # Defensive formatting cleanup to eliminate white spaces or serialization variances
    df_master_bridge['OA21CD'] = df_master_bridge['OA21CD'].astype(str).str.strip()
    df_master_bridge['CED25CD'] = df_master_bridge['CED25CD'].astype(str).str.strip()

    # 5. Filter lookups to match your project's active council definitions
    target_version_year = 2025  # The active ONS boundary cycle definition year

    if len(valid_divisions) == 0:
        print("⚠️ [WARNING] electoral_wards dataset empty. Processing all national rows for staging pass.")
        df_filtered = df_master_bridge
    else:
        # Keep only the assignments where the CED matches an active council code under inspection
        df_filtered = df_master_bridge[df_master_bridge['CED25CD'].isin(valid_divisions)]

    # format structure cleanly to map directly into our geographic_lookup table fields
    df_lookup_final = pd.DataFrame({
        'oa_code': df_filtered['OA21CD'],
        'wd_code': df_filtered['CED25CD'],  # Map the official CED key straight to our generic wd_code tracking field
        'lookup_version_year': target_version_year
    }).drop_duplicates()

    insert_payload = list(df_lookup_final.itertuples(index=False, name=None))
    print(f"Staged {len(insert_payload):,} optimized boundary rows for lookup injection.")

    # 6. Stream assignments into the database using chunked executions
    if len(insert_payload) == 0:
        print("❌ [Bypass] zero rows passed the geography target filters. Ingestion halted.")
        cursor.close()
        conn.close()
        return

    insert_query = """
        INSERT IGNORE INTO geographic_lookup (oa_code, wd_code, lookup_version_year)
        VALUES (%s, %s, %s);
    """

    try:
        print("Streaming sorted assignments to table 'geographic_lookup'...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        
        # Wipe out old structural traces to guarantee a clean, uncorrupted cross-council pass
        cursor.execute("TRUNCATE TABLE geographic_lookup;")
        
        batch_size = 10000
        for i in range(0, len(insert_payload), batch_size):
            batch = insert_payload[i:i + batch_size]
            cursor.executemany(insert_query, batch)
            
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        print(f"🎉 [SUCCESS] 'geographic_lookup' completely synced! {len(insert_payload):,} entries saved.")

    except mysql.connector.Error as err:
        print(f"❌ [Database Error] Bulk alignment stream transaction failed: {err}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("Database session safely uncoupled and offline.\n")


if __name__ == "__main__":
    run_geographic_alignment_pipeline()