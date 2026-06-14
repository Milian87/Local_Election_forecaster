# Python code to extract election results from a csv file and save to a new csv file
import csv
import pandas as pd

# List of target councils to extract data for
target_councils = [
    "Norfolk County Council",
    "Suffolk County Council",
    "Essex County Council",
    "Central Bedfordshire Council",
    "Cambridgeshire County Council",
    "Cornwall Council",
    "Cumberland County Council",
    "Devon County Council",
    "Dorset Council",
    "Derbyshire County Council",
    "Durham County Council",
    "Gloucestershire County Council",
    "Hampshire County Council",
    "Herefordshire Council",
    "Kent County Council",
    "Lincolnshire County Council",
    "North Yorkshire County Council",
    "Oxfordshire County Council",
    "Shropshire Council",
    "Staffordshire County Council",
    "Surrey County Council",
    "Warwickshire County Council",
    "West Sussex County Council",
    "Worestshire County Council"
]
# Read the input CSV file
input_file = r"\\?\C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results\dc-candidates-results_true__election_date_2016-__election_id___extra_fields_by_election-by_election_reason-gss-post_id-candidates_locked-nuts1-organisation_name-party_description_text-sopn_last_name-sopn_first_name.csv"
df_massive = pd.read_csv(input_file)
print("CSV file read successfully.")
# Filter the DataFrame to include only rows for the target councils
print(f"Filtering data for {len(target_councils)} target councils...")
df_filtered = df_massive[df_massive['organisation_name'].isin(target_councils)]
print(f"Data filtered successfully. Number of rows after filtering: {len(df_filtered)}")
#clean and format the values for database compatibility
print("Cleaning and formatting data...")
# convert votes_cast to safe integer values, replacing non-numeric entries with 0 (for uncontested seats)
df_filtered['votes_cast'] = pd.to_numeric(df_filtered['votes_cast'], errors='coerce').fillna(0).astype(int)

# convert a clean numeric year from the election_date column
df_filtered['election_year'] = pd.to_datetime(df_filtered['election_date'], errors='coerce').dt.year

# Convert boolean election flags from text ('t'/'f') to standard database bits (1/0)
df_filtered['is_elected'] = df_filtered['elected'].map({'t': 1, 'f': 0}).fillna(0).astype(int)
df_filtered['is_uncontested'] = df_filtered['by_election'].map({'t': 1, 'f': 0}).fillna(0).astype(int) # Adjust if using a dedicated column
df_filtered['by_election'] = df_filtered['by_election'].map({'t': 1, 'f': 0}).fillna(0).astype(int) # If you want to keep this as a separate flag
# 5. Calculate Vote Share (%) natively in Python to avoid division-by-zero breaks
print("Calculating precise vote shares...")
ward_totals = df_filtered.groupby(['election_year', 'post_label'])['votes_cast'].transform('sum') # Get total votes cast per ward per election year
print("ward_totals are:")
print(ward_totals)
df_filtered['vote_share'] = (df_filtered['votes_cast'] / ward_totals * 100).round(2).fillna(0) # Calculate vote share and handle division by zero


# 7. Select and rename only the columns required by your schema
df_final_table = pd.DataFrame({
    'wd_code': df_filtered['gss'],
    'ward_name': df_filtered['post_label'],
    'council_name': df_filtered['organisation_name'],
    'election_year': df_filtered['election_year'],
    'candidate_id': df_filtered['person_id'],
    'candidate_name': df_filtered['person_name'],
    'party_name': df_filtered['party_name'],
    'seats_available': df_filtered['seats_contested'],
    'is_uncontested': df_filtered['is_uncontested'],
    'by_election': df_filtered['by_election'],
    'votes_received': df_filtered['votes_cast'],
    'vote_share_pc': df_filtered['vote_share'],
    'is_elected': df_filtered['is_elected'],
    'is_incumbent_cllr': 0  # Ready for your historical lookup logic later
})
# set 2 folder paths for the output file
output_folder_1 = r"C:\Users\ianmi\OneDrive\3 Masters Degree\Module 11 - Independant Research Project\Data\election results"
output_folder_2 = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results"
# 7. Save to another clean CSV file using the election  year in the filename for clarity, and also save a copy to the computer programs folder for use in the database import step
output_file = f"{output_folder_1}\\target_council_results_{df_filtered['election_year'].iloc[0]}.csv"
print(f"Saving cleaned data to '{output_file}'...")
output_file_2 = f"{output_folder_2}\\target_council_results_{df_filtered['election_year'].iloc[0]}.csv"
df_final_table.to_csv(output_file, index=False)
df_final_table.to_csv(output_file_2, index=False)

print(f"🎯 Success! Saved {len(df_final_table)} relevant candidate rows to '{output_file}' and '{output_file_2}'.")