import pandas as pd
import mysql.connector

# Connect to DB
conn = mysql.connector.connect(host='localhost', user='root', password='Xabp74yb%', database='irp_election_forecasting')
cursor = conn.cursor()

# Load all rows from the 2025 ONS lookup sheet
df_ced = pd.read_csv(r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\csv\Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2025)_Lookup_for_EN.csv")

# Pull unique wards across England
df_wards_all = df_ced[['WD25CD', 'WD25NM', 'CTY25CD']].drop_duplicates().dropna()
ward_records = list(df_wards_all.itertuples(index=False, name=None))

# Insert them all into your master wards table
ward_insert_sql = """
    INSERT IGNORE INTO electoral_wards (wd_code, ward_name, cc_code) 
    VALUES (%s, %s, %s)
"""
batch_size = 5000
for i in range(0, len(ward_records), batch_size):
    cursor.executemany(ward_insert_sql, ward_records[i:i + batch_size])

conn.commit()
print(f"[SUCCESS] Loaded {len(ward_records)} national wards into electoral_wards!")
cursor.close()
conn.close()