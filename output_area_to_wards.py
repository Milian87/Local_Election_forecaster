# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# Created: 21/05/2026
# Updated: 31/05/2026 - Configured for Upper-Tier County Council Divisions (E58)

import os
import pandas as pd
import mysql.connector

print("=============================================")
print("Starting Output Area to Division Mapping Process...")
print("=============================================\n")

# 1. Connect to your active local MySQL database
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Xabp74yb%',
    'database': 'irp_election_forecasting'
}

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print("[SUCCESS] Connected to MySQL database.")
except mysql.connector.Error as err:
    print(f"[ERROR] Database connection failed: {err}")
    exit()

print("==============================================")

# 2. Define explicit paths to your raw ONS files
base_dir = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\csv"
oa_to_lsoa_path = os.path.join(base_dir, "Output_Areas_2021_EW_BGC_V2_2501415973521800973.csv")
print("loaded OA file")
lsoa_to_ward_path = os.path.join(base_dir, "LSOA_(2021)_to_Electoral_Ward_(2025)_to_LAD_(2025)_Best_Fit_Lookup_in_EW_v2.csv")
print("loaded LSOA to Ward file")
ward_to_ced_path = os.path.join(base_dir, "Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2025)_Lookup_for_EN.csv")
print("loaded Ward to County Electoral Division file")
print("Loading ONS master source tables into memory...")
df_oa = pd.read_csv(oa_to_lsoa_path, usecols=['OA21CD', 'LSOA21CD'])
df_lsoa_to_ward = pd.read_csv(lsoa_to_ward_path, usecols=['LSOA21CD', 'WD25CD'])
df_ward_to_ced = pd.read_csv(ward_to_ced_path, usecols=['WD25CD', 'CED25CD'])

print("Bridging Output Areas through LSOAs to County Divisions...")
# Multi-stage merge to resolve geographic hierarchy down to the absolute base unit
df_merged = pd.merge(df_oa, df_lsoa_to_ward, on='LSOA21CD', how='inner')
df_master_bridge = pd.merge(df_merged, df_ward_to_ced, on='WD25CD', how='inner')

# Force remove any trailing formatting whitespace 
df_master_bridge['OA21CD'] = df_master_bridge['OA21CD'].astype(str).str.strip()
df_master_bridge['CED25CD'] = df_master_bridge['CED25CD'].astype(str).str.strip()

# 3. Pull valid targets currently registered in your MySQL electoral_wards table (Your E58 Codes)
cursor.execute("SELECT wd_code FROM electoral_wards")
valid_divisions = set([str(row[0]).strip() for row in cursor.fetchall()])
print(f"Found {len(valid_divisions)} active division targets (E58) in database.")

# 4. Filter the merged records to match your specific target councils
version_year = 2025 # The active boundary definition cycle for this layout

if len(valid_divisions) == 0:
    print("[WARNING] electoral_wards table is empty! Processing all available rows for structural validation.")
    df_filtered = df_master_bridge
else:
    # Keep only the rows where the County Division matches your target footprint
    df_filtered = df_master_bridge[df_master_bridge['CED25CD'].isin(valid_divisions)]

# Reformat structure cleanly to match your schema columns: (oa_code, wd_code, lookup_version_year)
df_lookup_final = pd.DataFrame({
    'oa_code': df_filtered['OA21CD'],
    'wd_code': df_filtered['CED25CD'],  # Maps your E58 key to the database column
    'lookup_version_year': version_year
}).drop_duplicates()

insert_records = list(df_lookup_final.itertuples(index=False, name=None))
print(f"Filtered {len(insert_records):,} unique Output Area assignments matching your target councils.")

# 5. Execute bulk database insertion safely
insert_query = """
    INSERT IGNORE INTO geographic_lookup (oa_code, wd_code, lookup_version_year)
    VALUES (%s, %s, %s)
"""

try:
    if len(insert_records) > 0:
        print("Writing sorted assignments to geographic_lookup table...")
        # Executing in batches ensures high speed without overloading memory
        batch_size = 5000
        for i in range(0, len(insert_records), batch_size):
            batch = insert_records[i:i + batch_size]
            cursor.executemany(insert_query, batch)
        
        conn.commit()
        print(f"[SUCCESS] Sorting complete! All relevant OAs successfully assigned.")
    else:
        print("[WARNING] Ingestion bypassed because zero matching records passed the filter.")

except mysql.connector.Error as err:
    print(f"[ERROR] Bulk insertion failed: {err}")
    conn.rollback()

finally:
    cursor.close()
    conn.close()
    print("\n=============================================")
    print("Pipeline Execution Completed.")
    print("=============================================")