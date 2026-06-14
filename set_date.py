import os
import pandas as pd

# 1. System Directory Configurations
dc_folder = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\democracy club"
results_folder = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results\processed"

print("====================================================")
print("Starting Master Democracy Club Date Linker Pipeline...")
print("====================================================\n")

# 2. Step 1: Scan and Ingest all raw Democracy Club Files to build a master Date Map
dc_files = [f for f in os.listdir(dc_folder) if f.startswith("dc-candidates-") and f.endswith(".csv")]
print(f"Found {len(dc_files)} raw Democracy Club bulk files to parse.")

master_date_map = {}

for dc_file in dc_files:
    print(f"--> Parsing date signatures from: {dc_file}")
    file_path = os.path.join(dc_folder, dc_file)
    
    # Read only the columns required to build our unique mapping key to save system memory
    # person_id -> candidate_id, gss -> wd_code, election_date -> target date
    df_dc = pd.read_csv(file_path, usecols=['person_id', 'gss', 'election_date'], low_memory=False)
    
    # Clean keys for perfect alignment
    df_dc['person_id'] = df_dc['person_id'].astype(str).str.strip()
    df_dc['gss'] = df_dc['gss'].astype(str).str.strip()
    df_dc['election_date'] = df_dc['election_date'].astype(str).str.strip()
    
    # Populate the cross-reference dictionary: (candidate_id, wd_code) -> election_date
    for _, row in df_dc.iterrows():
        key = (row['person_id'], row['gss'])
        master_date_map[key] = row['election_date']

print(f"\n[SUCCESS] Master Date Lookup built with {len(master_date_map):,} unique candidate-ward intersections.")
print("----------------------------------------------------")

# 3. Step 2: Loop through and update your clean results files
results_files = [f for f in os.listdir(results_folder) if f.startswith("target_council_results_") and f.endswith("_clean.csv")]
print(f"Found {len(results_files)} cleaned tables awaiting election_date injection.\n")

for r_file in sorted(results_files):
    print(f"Processing File: {r_file}")
    r_path = os.path.join(results_folder, r_file)
    
    df_res = pd.read_csv(r_path, low_memory=False)
    
    # Ensure join columns are pure strings for character comparison matching
    df_res['candidate_id'] = df_res['candidate_id'].astype(str).str.strip()
    df_res['wd_code'] = df_res['wd_code'].astype(str).str.strip()
    
    # 4. Apply the mapping translation layer
    def match_date(row):
        lookup_key = (row['candidate_id'], row['wd_code'])
        # If it finds a direct match in Democracy Club files, use it. 
        # Fallback to standard May 1st template if completely missing.
        return master_date_map.get(lookup_key, f"{int(row['election_year'])}-05-01")
    
    df_res['election_date'] = df_res.apply(match_date, axis=1)
    
    # 5. Coordinate Column Layout to place election_date next to election_year
    cols = list(df_res.columns)
    if 'election_date' in cols and 'election_year' in cols:
        cols.remove('election_date')
        year_idx = cols.index('election_year')
        cols.insert(year_idx + 1, 'election_date') # Places it right after the year column
        df_res = df_res[cols]
    
    # Save the updated date-aware file back over itself
    df_res.to_csv(r_path, index=False)
    
    # Verify execution by checking if any rows fell back to defaults
    mismatches = df_res['election_date'].str.endswith('-05-01').sum()
    print(f"   Success! Injected election_date vector into {len(df_res):,} candidate rows.")
    if mismatches > 0:
        print(f"   Note: {mismatches} rows defaulted to standard scheduled May formatting loops.")

print("\n=============================================")
print("Pipeline Closed. All historical tables synced.")
print("=============================================")