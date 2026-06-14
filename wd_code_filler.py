import os
import re
import pandas as pd

# 1. System Directory Configuration
results_dir = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\election_results\processed"
lookups_dir = r"C:\Users\ianmi\Computer Programs\IRP-computer_program\data\Lookups"
output_dir = r"C:\Users\ianmi\OneDrive\3 Masters Degree\Module 11 - Independant Research Project\Data\election results\clean_historical"

os.makedirs(output_dir, exist_ok=True)

# 2. Structural Synonym Dictionary for Historical County Anomalies
structural_synonyms = {
    ("Essex County Council", "Billericay North"): "E58000406",
    ("Essex County Council", "Burstead"): "E58000406",
    ("Essex County Council", "Castledon & Crouch"): "E58000468",
    ("Essex County Council", "Burnham & Southminster"): "E58000460",
    ("Essex County Council", "Chelmsford Springfield"): "E58000458",
    ("Essex County Council", "Chigwell & Buckhurst Hill East"): "E58000412",
    ("Essex County Council", "Clacton South"): "E58000438",
    ("Essex County Council", "Clacton West & St Osyth"): "E58000439",
    ("Essex County Council", "Great Baddow & Galleywood"): "E58000416",
    ("Norfolk County Council", "Coltishall & Spixworth"): "E58000971",
    ("Norfolk County Council", "Dereham North & Scarning"): "E58000969",
    ("Norfolk County Council", "Fakenham & The Raynhams"): "E58000995",
    ("Suffolk County Council", "Abbeygate & Minden"): "E58001252",
    ("Suffolk County Council", "Barrow & Thingoe"): "E58001254",
    ("Suffolk County Council", "Beccles & Kessingland"): "E58001264",
    ("Suffolk County Council", "St Margaret's"): "E58001247",
    ("Suffolk County Council", "Westgate"): "E58001247",
    # Add any historical town variances encountered in your 2016-2020 loops here
    ("Cambridgeshire County Council", "St Neots Eaton Socon and Eynesbury"): "E58000097",
    ("Hampshire County Council", "Headley"): "E58000571",
    ("Gloucestershire County Council", "St Mark's and St Peter's"): "E58000488",
    ("Gloucestershire County Council", "St Paul's and Swindon"): "E58000489",
    ("Hampshire County Council", "Emsworth & St Faiths"): "E58000552",
    ("Norfolk County Council", "Gorleston St Andrews"): "E58000979",
    ("Oxfordshire County Council", "St Clement's and Cowley Marsh"): "E58001275",
    ("Suffolk County Council", "Kesgrave and Rushmere St Andrew"): "E58001259",
    ("Suffolk County Council", "St Helen's"): "E58001244",
    ("Suffolk County Council", "St John's"): "E58001244",
    ("Suffolk County Council", "St Margaret's and Westgate"): "E58001247",

    # North Yorkshire County Council - 2022 structural remap synonyms
    ("North Yorkshire County Council", "Appleton Roebuck & Church Fenton"): "E58001047",
    ("North Yorkshire County Council", "Barlby & Riccall"): "E58001070",
    ("North Yorkshire County Council", "Bilton Grange & New Park"): "E58001056",
    ("North Yorkshire County Council", "Camblesforth & Carlton"): "E58001078",
    ("North Yorkshire County Council", "Cliffe & North Duffield"): "E58001051",
    ("North Yorkshire County Council", "Coppice Valley & Duchy"): "E58001057",
    ("North Yorkshire County Council", "Danby & Mulgrave"): "E58001053",
    ("North Yorkshire County Council", "Harlow & St. Georges"): "E58001058",
    ("North Yorkshire County Council", "Helmsley & Sinnington"): "E58001035",
    ("North Yorkshire County Council", "High Harrogate & Kingsley"): "E58001089",
    ("North Yorkshire County Council", "Hillside & Raskelf"): "E58001068",
    ("North Yorkshire County Council", "Huby & Tollerton"): "E58001024",
    ("North Yorkshire County Council", "Hunmanby & Sherburn"): "E58001081",
    ("North Yorkshire County Council", "Hutton Rudby & Osmotherley"): "E58001046",
    ("North Yorkshire County Council", "Killinghall, Hampsthwaite & Saltergate"): "E58001059",
    ("North Yorkshire County Council", "Leyburn & Middleham"): "E58001042",
    ("North Yorkshire County Council", "Monk Fryston & South Milford"): "E58001075",
    ("North Yorkshire County Council", "Oatlands & Pannal"): "E58001060",
    ("North Yorkshire County Council", "Ripon Minster & Moorside"): "E58001054",
    ("North Yorkshire County Council", "Scotton & Lower Wensleydale"): "E58001074",
    ("North Yorkshire County Council", "Skipton North & Embsay-with-Eastby"): "E58001066",
    ("North Yorkshire County Council", "Spofforth with Lower Wharfedale & Tockwith"): "E58001006",
    ("North Yorkshire County Council", "Thorpe Willoughby & Hambleton"): "E58001064",
    ("North Yorkshire County Council", "Valley Gardens & Central Harrogate"): "E58001057",
    ("North Yorkshire County Council", "Washburn & Birstwith"): "E58001041"
}

# 2b. North Yorkshire 2022 targeted synonym matrix from Gemini guidance
# Maps (Normalized Council Label, Democracy Club Ward Name) -> Official ONS CED code
north_yorkshire_synonyms = {
    ("North Yorkshire", "Aiskew & Leeming"): "E58001006",
    ("North Yorkshire", "Amotherby & Ampleforth"): "E58001007",
    ("North Yorkshire", "Boroughbridge"): "E58001013",
    ("North Yorkshire", "Catterick Village & Brompton-on-Swale"): "E58001017",
    ("North Yorkshire", "Filey"): "E58001026",
    ("North Yorkshire", "Glusburn, Cross Hills & Sutton-in-Craven"): "E58001028",
    ("North Yorkshire", "Kirkbymoorside"): "E58001037",
    ("North Yorkshire", "Mid Craven"): "E58001043",
    ("North Yorkshire", "North Richmondshire"): "E58001045",
    ("North Yorkshire", "Ouseburn"): "E58001048",
    ("North Yorkshire", "Pateley Bridge & Lower Nidderdale"): "E58001049",
    ("North Yorkshire", "Pickering"): "E58001050",
    ("North Yorkshire", "Richmond"): "E58001053",
    ("North Yorkshire", "Romaldkirk"): "E58001073",
    ("North Yorkshire", "Scarborough Castle"): "E58001056",
    ("North Yorkshire", "Settle & Penyghent"): "E58001061",
    ("North Yorkshire", "Sheriff Hutton & Derwent"): "E58001063",
    ("North Yorkshire", "Skipton East"): "E58001064",
    ("North Yorkshire", "Skipton West & West Craven"): "E58001065",
    ("North Yorkshire", "Stakesby"): "E58001077",
    ("North Yorkshire", "Thirsk"): "E58001071",
}

def normalize_string(val):
    if pd.isna(val): return ""
    s = str(val).lower()
    s = s.replace("&", "and")
    s = s.replace(".", "")  # <-- CRITICAL: Strips out full stops so 'st.' matches 'st'
    s = s.replace("county council", "")
    s = s.replace(" ed", "")
    return "".join(s.split())

# 3. Scan directories and inventory what files we have
results_files = [f for f in os.listdir(results_dir) if f.startswith("target_council_results_") and f.endswith(".csv")]
lookup_files = [f for f in os.listdir(lookups_dir) if f.startswith("Ward_to_LAD_to_County_") and f.endswith(".csv")]

print(f"Found {len(results_files)} results data tables to clean.")
print(f"Found {len(lookup_files)} boundary reference lookups.")

# 4. Ingestion Loop
for r_file in sorted(results_files):
    # Extract the target year from the results filename using regex
    year_match = re.search(r"\d{4}", r_file)
    if not year_match:
        continue
    file_year = int(year_match.group())
    
    print(f"\n[Processing Year {file_year}] --> File: {r_file}")
    
    # Locate the best available ONS lookup match for this file's year
    best_lookup = None
    # Strategy: Find exact year match first
    for l_file in lookup_files:
        if f"({file_year})" in l_file or f"_{file_year}_" in l_file:
            best_lookup = l_file
            break
            
    # Fallback rules if exact match isn't present
    if not best_lookup:
        if file_year == 2022:
            # North Yorkshire 2022 Unitary data lives in the Ward-to-LAD files
            # Look for a 2022, 2023, or 2024 Ward_to_LAD lookup file in your folder
            lad_options = [f for f in os.listdir(lookups_dir) if "Ward_to_LAD_" in f and f.endswith(".csv")]
            if lad_options:
                best_lookup = sorted(lad_options)[-1]  # Grabs the newest available Ward-to-LAD layout
            else:
                best_lookup = [f for f in lookup_files if "2018" in f or "2023" in f][0]
        elif file_year in [2016, 2017]:
            # Use 2017 for 2016 files as boundaries are contiguous
            best_lookup = [f for f in lookup_files if "2017" in f][0]
        elif file_year in [2019, 2020]:
            # Use 2018 framework for intermediate cycles prior to post-2021 reorganizations
            best_lookup = [f for f in lookup_files if "2018" in f][0]
        else:
            # Absolute baseline fallback: Use the closest chronological option available
            best_lookup = sorted(lookup_files)[0]
            
    print(f"   Linking with Reference Matrix: {best_lookup}")
    
    # 5. Load Dataframes
    df_res = pd.read_csv(os.path.join(results_dir, r_file), low_memory=False)
    df_ons = pd.read_csv(os.path.join(lookups_dir, best_lookup), low_memory=False)
    
    # 6. Dynamically locate structural headers inside the ONS file based on year shifts
    col_list = df_ons.columns.tolist()
    cty_col = [c for c in col_list if "CTY" in c and "NM" in c][0]   # Dynamic County Name column
    ced_code_col = [c for c in col_list if "CED" in c and "CD" in c][0] # Dynamic ED Code column
    ced_name_col = [c for c in col_list if "CED" in c and "NM" in c][0] # Dynamic ED Name column
    
    # 7. Compile Translation Dictionaries Natively
    df_ons['match_county'] = df_ons[cty_col].apply(normalize_string)
    df_ons['match_division'] = df_ons[ced_name_col].apply(normalize_string)
    ons_clean_map = df_ons.drop_duplicates(subset=['match_county', 'match_division'])
    ons_dict = dict(zip(zip(ons_clean_map['match_county'], ons_clean_map['match_division']), ons_clean_map[ced_code_col]))
    
    df_res['match_county'] = df_res['council_name'].apply(normalize_string)
    df_res['match_division'] = df_res['ward_name'].apply(normalize_string)
    
    # 8. Gap Filling Loop Execution
    def resolve_code_batch(row):
        council_raw = str(row['council_name'])
        council = "North Yorkshire" if "yorkshire" in council_raw.lower() else council_raw

        # 1) North Yorkshire LGR-specific synonym override
        north_yorkshire_key = (council, row['ward_name'])
        if north_yorkshire_key in north_yorkshire_synonyms:
            return north_yorkshire_synonyms[north_yorkshire_key]

        # 2) Existing hardcoded structural synonym override
        hardcoded_key = (row['council_name'], row['ward_name'])
        if hardcoded_key in structural_synonyms:
            return structural_synonyms[hardcoded_key]

        # 3) Standardized ONS lookup fallback
        if pd.isna(row['wd_code']) or str(row['wd_code']).strip() == "" or str(row['wd_code']).lower() == "nan":
            lookup_key = (normalize_string(council), row['match_division'])
            return ons_dict.get(lookup_key, row['wd_code'])
        return row['wd_code']
        
    initial_blanks = df_res['wd_code'].isna().sum()
    df_res['wd_code'] = df_res.apply(resolve_code_batch, axis=1)
    remaining_blanks = df_res['wd_code'].isna().sum()
    
    # 9. Clean up and Housekeeping
    df_res = df_res.drop(columns=['match_county', 'match_division'])
    df_res['election_year'] = pd.to_numeric(df_res['election_year'], errors='coerce').fillna(file_year).astype(int)
    
    # 10. Save Output back out
    clean_out_name = f"target_council_results_{file_year}_clean.csv"
    df_res.to_csv(os.path.join(output_dir, clean_out_name), index=False)
    # Also overwrite a local duplicate directly to your staging folder for immediate database upload use
    df_res.to_csv(os.path.join(results_dir, clean_out_name), index=False)
    
    print(f"   Success! Filled {initial_blanks - remaining_blanks} missing entries. Unresolved rows left: {remaining_blanks}")

print("\n🎯 Complete historical batch cleaning sequence executed successfully!")