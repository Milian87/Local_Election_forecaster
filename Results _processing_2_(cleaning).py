import os
import pandas as pd

# =========================================================================
# CONFIGURATION SETTINGS
# =========================================================================
clean_data_dir = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results\processed"
diagnostic_output_path = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results\unmatched_wards_report.csv"

# Verify the target processed directory exists before attempting to scan
if not os.path.exists(clean_data_dir):
    print(f"[ERROR] Processed data directory not found: {clean_data_dir}")
    print("Please run your data extraction script first.")
    exit()

# Scan folder for all cleaned historical files matching the signature
target_files = [f for f in os.listdir(clean_data_dir) if f.startswith("target_council_results_") and f.endswith("_clean.csv")]

print(f"Scanning {len(target_files)} cleaned dataset file(s) for missing ONS keys...")
unmatched_records = []

# =========================================================================
# CORE DATA AUDIT LOOP
# =========================================================================
for file_name in sorted(target_files):
    file_path = os.path.join(clean_data_dir, file_name)
    
    try:
        df = pd.read_csv(file_path, low_memory=False)
    except Exception as e:
        print(f"   [SKIP ERROR] Failed to open {file_name}: {e}")
        continue
        
    # Safety feature: Ensure the schema actually contains a ward identifier column
    if 'wd_code' not in df.columns:
        print(f"   [WARNING] Column 'wd_code' is entirely missing from schema profile in: {file_name}")
        continue
    
    # Standardize string representations to thoroughly flag empty fields
    # Catches: true null values, empty spaces, and text literals like 'nan' / 'NaN'
    is_blank = (
        df['wd_code'].isna() | 
        (df['wd_code'].astype(str).str.strip().str.lower() == 'nan') |
        (df['wd_code'].astype(str).str.strip() == '')
    )
    df_blanks = df[is_blank]
    
    if len(df_blanks) > 0:
        # Pull optional display fallback metrics safely if source keys are missing
        council_col = 'council_name' if 'council_name' in df.columns else 'organisation_name'
        ward_col = 'ward_name' if 'ward_name' in df.columns else 'post_label'
        year_col = 'election_year' if 'election_year' in df.columns else 'row_election_year'
        
        # Group missing keys together to pinpoint specific geographic problem areas
        grouped = df_blanks.groupby([council_col, ward_col, year_col], dropna=False).size().reset_index(name='blank_row_count')
        
        for _, row in grouped.iterrows():
            unmatched_records.append({
                "Source_File": file_name,
                "Election_Year": row[year_col],
                "Council_Name": row[council_col],
                "Unmatched_Ward_Name": row[ward_col],
                "Affected_Candidate_Rows": row['blank_row_count']
            })

# =========================================================================
# DIAGNOSTIC REPORT GENERATION
# =========================================================================
if unmatched_records:
    df_report = pd.DataFrame(unmatched_records)
    # Sort logically by year, council, and name for easy manual debugging sheets
    df_report = df_report.sort_values(by=['Election_Year', 'Council_Name', 'Unmatched_Ward_Name'])
    
    df_report.to_csv(diagnostic_output_path, index=False)
    print(f"\n--> ⚠️ Diagnostic report compiled! Found ONS code gaps across {len(df_report)} unique ward cycles.")
    print(f"--> Summary exported to: {diagnostic_output_path}")
else:
    print("\n🎉 Perfection! All files show 100% data completion with no missing ONS ward codes.")