import os
import glob
import re
import pandas as pd
import mysql.connector

print("==========================================================")
print("Initializing Batch Council Code Ingestion Pipeline...")
print("==========================================================\n")

# 1. System Paths & Database Setup
lookups_folder = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\Lookups"

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Xabp74yb%',
    'database': 'irp_election_forecasting'
}

# Collect all matching ONS Lookup CSV files in the directory
lookup_files = glob.glob(os.path.join(lookups_folder, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv"))
print(f"Found {len(lookup_files)} ONS lookup files to process.")

# Master sets to accumulate unique entities across all files
master_council_data = set()

# 2. Dynamic Processing Loop
for file_path in sorted(lookup_files):
    file_name = os.path.basename(file_path)
    print(f"\nProcessing File: {file_name}")
    
    try:
        df_sample = pd.read_csv(file_path, nrows=2)
        columns = df_sample.columns.tolist()
        
        # Dynamically isolate the prefix pattern using regex
        lad_cd_col = [c for c in columns if re.match(r'LAD\d+CD', c)]
        lad_nm_col = [c for c in columns if re.match(r'LAD\d+NM', c)]
        cty_cd_col = [c for c in columns if re.match(r'CTY\d+CD', c)]
        cty_nm_col = [c for c in columns if re.match(r'CTY\d+NM', c)]
        
        if not lad_cd_col or not cty_cd_col:
            print(f"   ⚠️ Skipping: Could not locate standardized ONS column structure in {file_name}")
            continue
            
        l_cd, l_nm = lad_cd_col[0], lad_nm_col[0]
        c_cd, c_nm = cty_cd_col[0], cty_nm_col[0]
        
        df = pd.read_csv(file_path, usecols=[l_cd, l_nm, c_cd, c_nm], low_memory=False)
        
        # --- A. Extract Upper-Tier Counties ---
        df_counties = df[[c_cd, c_nm]].dropna().drop_duplicates()
        for _, row in df_counties.iterrows():
            code = str(row[c_cd]).strip()
            name = f"{str(row[c_nm]).strip()} County Council"
            master_council_data.add((code, name))
            
        # --- B. Extract Unitary Authorities ---
        # FIX: Appended .str before .lower() to handle the pandas string Series properly
        df_unitaries = df[df[c_cd].isna() | (df[c_cd].astype(str).str.strip().str.lower() == 'nan')]
        df_unitaries = df_unitaries[[l_cd, l_nm]].dropna().drop_duplicates()
        for _, row in df_unitaries.iterrows():
            code = str(row[l_cd]).strip()
            name = str(row[l_nm]).strip()
            if "Council" not in name and "Borough" not in name and "City" not in name:
                name = f"{name} Council"
            master_council_data.add((code, name))
            
        print(f"   Successfully parsed. Accumulated {len(master_council_data)} unique codes total.")
        
    except Exception as e:
        print(f"   ❌ Error reading {file_name}: {e}")

# 3. Stream Final Inventory to database table
insert_records = sorted(list(master_council_data))
print(f"\nTotal structural inventory size: {len(insert_records)} unique authorities ready for seeding.")

try:
    print("Connecting to MySQL Database...")
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # FIX: Explicitly match 'council_code' column name schema targeting your database structure
    insert_query = """
        INSERT IGNORE INTO county_codes (cc_code, council_name)
        VALUES (%s, %s);
    """
    
    print("Executing bulk database submission...")
    cursor.executemany(insert_query, insert_records)
    
    conn.commit()
    print(f"\n🎯 [SUCCESS] Batch run complete! All unique council structures successfully written to 'county_codes'.")

except mysql.connector.Error as err:
    print(f"\n[ERROR] Ingestion transaction aborted: {err}")
    conn.rollback()

finally:
    if 'conn' in locals() and conn.is_connected():
        cursor.close()
        conn.close()
        print("Database connection closed cleanly.")