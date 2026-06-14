import os
import pandas as pd

# Define your directory locations
clean_data_dir = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results\processed"
diagnostic_output_path = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results\unmatched_wards_report.csv"

# Scan folder for all cleaned historical files
target_files = [f for f in os.listdir(clean_data_dir) if f.startswith("target_council_results_") and f.endswith("_clean.csv")]

unmatched_records = []

print("Scanning files for missing ONS keys...")
for file_name in sorted(target_files):
    df = pd.read_csv(os.path.join(clean_data_dir, file_name), low_memory=False)
    
    # Identify rows where the ward code is missing or a string literal 'nan'
    is_blank = df['wd_code'].isna() | (df['wd_code'].astype(str).str.strip().str.lower() == 'nan')
    df_blanks = df[is_blank]
    
    if len(df_blanks) > 0:
        # Group by council and ward to extract unique names needing correction
        grouped = df_blanks.groupby(['council_name', 'ward_name', 'election_year']).size().reset_index(name='blank_row_count')
        for _, row in grouped.iterrows():
            unmatched_records.append({
                "Source_File": file_name,
                "Election_Year": row['election_year'],
                "Council_Name": row['council_name'],
                "Unmatched_Ward_Name": row['ward_name'],
                "Affected_Candidate_Rows": row['blank_row_count']
            })

# Combine and export to a review sheet
if unmatched_records:
    df_report = pd.DataFrame(unmatched_records)
    df_report.to_csv(diagnostic_output_path, index=False)
    print(f"--> Diagnostic report compiled! Found gaps across {len(df_report)} unique wards.")
    print(f"--> Summary exported to: {diagnostic_output_path}")
else:
    print("🎉 Perfection! All files show 100% data completion with no missing ward codes.")