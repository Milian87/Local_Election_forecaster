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
    
    # Unified master map compounding all generations of codes
    master_historical_map = {}
    
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

    print(f"\nCompiled a master dictionary of {len(master_historical_map):,} historical mapping entries.")

    # 2. Extract unresolved database records
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    cursor.execute("SELECT wd_code FROM electoral_wards;")
    all_wards = [row[0] for row in cursor.fetchall() if row[0] is not None]
    print(f"Database contains {len(all_wards):,} total ward records.")

    # 3. Match keys across generations
    update_payload = []
    for wd in all_wards:
        clean_wd = str(wd).strip()
        if clean_wd in master_historical_map:
            update_payload.append((master_historical_map[clean_wd], clean_wd))

    print(f"Matched {len(update_payload)} rows across all historical vintages.")

    # 4. Bulk stream corrections to your MySQL grid
    if update_payload:
        print("Streaming updates to database table grid...")
        cursor.execute("SET SQL_SAFE_UPDATES = 0;")
        
        batch_size = 5000
        for i in range(0, len(update_payload), batch_size):
            cursor.executemany(
                "UPDATE electoral_wards SET cc_code = %s WHERE wd_code = %s;", 
                update_payload[i:i + batch_size]
            )
            
        cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        conn.commit()
        
        # Final Verification Check
        cursor.execute("SELECT COUNT(*) FROM electoral_wards WHERE cc_code IS NULL OR TRIM(cc_code) = '';")
        blanks_left = cursor.fetchone()[0]
        print(f"\n🎯 [SUCCESS] Ingestion pass complete! Remaining NULL rows: {blanks_left}")
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