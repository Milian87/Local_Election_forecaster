import os
import glob
import re
import pandas as pd
import mysql.connector

# Points to your Geographic_lookups folder containing the 8 new best-fit files
lookups_folder = r"c:/Users/ianmi/Computer Programs/Local_Election_forecaster/data/Geographic_lookups"

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Xabp74yb%',
    'database': 'irp_election_forecasting'
}

print("==========================================================")
print("Initializing Census Output Area to Ward Population Pass...")
print("==========================================================\n")

# Dictionary to ensure completely unique rows before hitting database:
# { (wd_code, oa_code, version_year): (wd_code, oa_code, version_year) }
staged_records = {}

# Target files that contain Output Area to Ward transitions
oa_files = glob.glob(os.path.join(lookups_folder, "*Output_Area*to_Ward*.csv"))
# Also grab any files matching the extended formatting style
oa_files.extend(glob.glob(os.path.join(lookups_folder, "*Output_Area*to_WD*.csv")))
oa_files = list(set(oa_files)) # Remove potential duplicates

print(f"Found {len(oa_files)} best-fit files to parse.")

for file_path in sorted(oa_files):
    f_name = os.path.basename(file_path)
    try:
        # 1. Dynamically find the lookup version year via file name structure
        year_match = re.search(r'\(.*?(20\d{2}).*?\)', f_name)
        if not year_match:
            year_match = re.search(r'(20\d{2})', f_name)
        
        file_year = int(year_match.group(1)) if year_match else 2021
        
        # 2. Extract column headers to map dynamically (skips year-naming differences)
        df_sample = pd.read_csv(file_path, nrows=2)
        cols = df_sample.columns.tolist()
        
        oa_col = [c for c in cols if re.match(r'OA\d+CD', c) or c == 'OACD'][0]
        wd_col = [c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'][0]
        
        # 3. Read specific columns into memory frame
        df = pd.read_csv(file_path, usecols=[oa_col, wd_col], low_memory=False).dropna()
        
        for _, row in df.iterrows():
            wd_code = str(row[wd_col]).strip()
            oa_code = str(row[oa_col]).strip()
            
            if wd_code and oa_code:
                record_key = (wd_code, oa_code, file_year)
                staged_records[record_key] = record_key
                
        print(f" -> Ingested {len(df):,} structural rows from: {f_name} ({file_year})")
    except Exception as e:
        print(f" -> ⚠️ Skipping file format variance in {f_name}: {e}")

insert_payload = list(staged_records.values())
print(f"\nStaging Complete: {len(insert_payload):,} total records uniquely indexed.")

# 4. Execute Transaction to Database
try:
    print("Connecting to MySQL Database...")
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    # Empty out any previous bad-state rows if you want a clean pass
    cursor.execute("TRUNCATE TABLE geographic_lookup;")
    
    insert_query = """
        INSERT IGNORE INTO geographic_lookup (wd_code, oa_code, lookup_version_year)
        VALUES (%s, %s, %s);
    """
    
    print("Streaming bulk data packets to table 'geographic_lookup'...")
    batch_size = 20000
    for i in range(0, len(insert_payload), batch_size):
        cursor.executemany(insert_query, insert_payload[i:i + batch_size])
        
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    print(f"\n🎯 [SUCCESS] 'geographic_lookup' table successfully populated with {len(insert_payload):,} entries!")

except mysql.connector.Error as err:
    print(f"\n❌ Database error encountered: {err}")
    if 'conn' in locals() and conn.is_connected():
        conn.rollback()
finally:
    if 'conn' in locals() and conn.is_connected():
        cursor.close()
        conn.close()
        print("Database session securely offline.")