# IRP Computer Program
# Multi-File Geographic Ingestion Pipeline
# Ian Milburn

import pandas as pd
import mysql.connector

print("==========================================================")
print("Populating Versioned Associative Bridge Table...")
print("==========================================================\n")

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

VERSION_YEAR = 2025

# 2. File paths (Update names if using a different numerical suffix in your directory)
oa_to_lsoa_path = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\csv\Output_Areas_2021_EW_BGC_V2_2501415973521800973.csv"
lsoa_to_ward_path = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\csv\LSOA_(2021)_to_Electoral_Ward_(2025)_to_LAD_(2025)_Best_Fit_Lookup_in_EW_v2.csv"

# 3. Pull the valid keys currently existing in your database tables to respect foreign keys
cursor.execute("SELECT wd_code FROM electoral_wards")
db_wards = set([str(row[0]).strip() for row in cursor.fetchall()])

cursor.execute("SELECT oa_code FROM output_areas")
db_output_areas = set([str(row[0]).strip() for row in cursor.fetchall()])

print(f"-> Database Status: {len(db_wards)} wards and {len(db_output_areas):,} output areas loaded.")

if len(db_wards) == 0 or len(db_output_areas) == 0:
    print("[CRITICAL ERROR] One of your primary tables is empty. Populate them before creating the bridge.")
    cursor.close()
    conn.close()
    exit()

print("\nLoading ONS lookup keys into memory...")
df_oa = pd.read_csv(oa_to_lsoa_path, usecols=['OA21CD', 'LSOA21CD'])
df_lsoa_to_ward = pd.read_csv(lsoa_to_ward_path, usecols=['LSOA21CD', 'WD25CD'])

print("Building direct spatial relationships...")
# Merge tables to link OA directly to WD25CD (E05 Ward Codes)
df_master_bridge = pd.merge(df_oa, df_lsoa_to_ward, on='LSOA21CD', how='inner')

# Clean columns for perfect string evaluation
df_master_bridge['OA21CD'] = df_master_bridge['OA21CD'].astype(str).str.strip()
df_master_bridge['WD25CD'] = df_master_bridge['WD25CD'].astype(str).str.strip()

print("Filtering rows to strictly match existing database records...")
# Keep rows ONLY where the ward code exists in your DB AND the output area code exists in your DB
df_filtered_lookup = df_master_bridge[
    (df_master_bridge['WD25CD'].isin(db_wards)) & 
    (df_master_bridge['OA21CD'].isin(db_output_areas))
].copy()

# Structure to match: geographic_lookup (oa_code, wd_code, lookup_version_year)
df_filtered_lookup['lookup_version_year'] = VERSION_YEAR
df_final = df_filtered_lookup[['OA21CD', 'WD25CD', 'lookup_version_year']].drop_duplicates()

lookup_records = list(df_final.itertuples(index=False, name=None))
print(f"-> Found {len(lookup_records):,} precise matching intersections for your study boundaries.")

# 4. Bulk Insert Execution
insert_query = """
    INSERT IGNORE INTO geographic_lookup (oa_code, wd_code, lookup_version_year)
    VALUES (%s, %s, %s)
"""

try:
    if len(lookup_records) > 0:
        print("Writing validated assignments to geographic_lookup table...")
        batch_size = 5000
        for i in range(0, len(lookup_records), batch_size):
            cursor.executemany(insert_query, lookup_records[i:i + batch_size])
        conn.commit()
        print(f"[SUCCESS] {len(lookup_records):,} rows successfully inserted into geographic_lookup!")
    else:
        print("[WARNING] Zero matching relational rows passed the foreign key pre-filter.")
except mysql.connector.Error as err:
    print(f"[ERROR] Bulk insertion failed: {err}")
    conn.rollback()

finally:
    cursor.close()
    conn.close()
    print("\n=============================================")
    print("Pipeline Execution Closed.")
    print("=============================================")