import os
import csv
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

print("==========================================================")
print("Initializing 2011 Census Data Ingestion Pipeline...")
print("==========================================================\\n")

# 1. System Folder & Database Configuration
CENSUS_YEAR = 2011
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(BASE_DIR, "data", "2011_census")

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Xabp74yb%',
    'database': 'irp_election_forecasting'
}


def read_nomis_csv(file_path):
    def is_table_header(row):
        lowered = [col.strip().lower() for col in row]
        non_empty_cells = [col for col in lowered if col]
        if len(non_empty_cells) < 3:
            return False

        first_cell = lowered[0]
        if (
            "ons crown copyright" in first_cell
            or first_cell.startswith("population")
            or first_cell.startswith("units")
            or first_cell.startswith("date")
            or first_cell.startswith("rural urban")
        ):
            return False

        return (
            "output area" in first_cell
            or "geography code" in first_cell
            or "all persons" in first_cell
            or any(col == "%" for col in lowered)
        )

    header_row = None
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if row and is_table_header(row):
                header_row = idx
                break

    if header_row is None:
        raise ValueError(f"Could not find Nomis table header in {file_path}")

    df = pd.read_csv(file_path, skiprows=header_row, dtype=str, low_memory=False)
    df = df.dropna(how="all")

    df.rename(columns={df.columns[0]: 'oa_code'}, inplace=True)
    df['oa_code'] = df['oa_code'].astype(str).str.strip()
    return df


def normalize_text(value):
    return str(value).strip().lower()


def find_col_index(df, hint):
    hint = normalize_text(hint)
    for idx, col in enumerate(df.columns):
        if hint in normalize_text(col):
            return idx
    return None


def safe_numeric_col_by_hint(df, hint, default_value=0.0):
    col_idx = find_col_index(df, hint)
    if col_idx is None:
        return pd.Series(default_value, index=df.index, dtype='float64')
    return pd.to_numeric(df.iloc[:, col_idx], errors='coerce').fillna(default_value)


def pct_col_after_label(df, label, default_value=0.0):
    base_idx = find_col_index(df, label)
    if base_idx is None or base_idx + 1 >= df.shape[1]:
        return pd.Series(default_value, index=df.index, dtype='float64')
    return pd.to_numeric(df.iloc[:, base_idx + 1], errors='coerce').fillna(default_value)


def pct_sum_after_labels(df, labels):
    total = pd.Series(0.0, index=df.index, dtype='float64')
    for label in labels:
        total = total + pct_col_after_label(df, label)
    return total


def map_to_master_by_oa(source_df, values, master_oa_codes, default_value=0.0):
    keyed = pd.DataFrame({
        'oa_code': source_df['oa_code'].astype(str).str.strip(),
        'value': pd.to_numeric(values, errors='coerce').fillna(default_value)
    })
    keyed = keyed[keyed['oa_code'].notna() & (keyed['oa_code'] != '') & (keyed['oa_code'].str.lower() != 'nan')]
    mapped = keyed.drop_duplicates(subset='oa_code', keep='first').set_index('oa_code')['value']
    return master_oa_codes.map(mapped).fillna(default_value)


# 2. Extract and load all target files into memory
print("Reading individual files and cleaning Nomis formatting metadata...")
df_age = read_nomis_csv(os.path.join(data_folder, "2011Census_age.csv"))
df_bch = read_nomis_csv(os.path.join(data_folder, "2011census_bch.csv"))
df_fb = read_nomis_csv(os.path.join(data_folder, "2011Census_foreign-born.csv"))
df_sex = read_nomis_csv(os.path.join(data_folder, "2011Census_sex.csv"))
df_soc = read_nomis_csv(os.path.join(data_folder, "2011Census_social_class.csv"))
df_stu = read_nomis_csv(os.path.join(data_folder, "2011Census_students.csv"))
df_ten = read_nomis_csv(os.path.join(data_folder, "2011Census_tenure.csv"))

# 3. Consolidate into a unified wide DataFrame on oa_code
print("Compiling separate fields into single geographic matrix...")
df_master = df_age[['oa_code']].copy()
df_master['oa_code'] = df_master['oa_code'].astype(str).str.strip()

# --- Population & Age ---
ward_pop_age = safe_numeric_col_by_hint(df_age, 'all usual residents')
df_master['ward_pop'] = map_to_master_by_oa(df_age, ward_pop_age, df_master['oa_code']).astype(int)

age_18_29_pct = pct_sum_after_labels(df_age, ['age 18 to 19', 'age 20 to 24', 'age 25 to 29'])
age_30_65_pct = pct_sum_after_labels(df_age, ['age 30 to 44', 'age 45 to 59', 'age 60 to 64'])
age_over_65_pct = pct_sum_after_labels(df_age, ['age 65 to 74', 'age 75 to 84', 'age 85 to 89', 'age 90 and over'])
df_master['pct_age_18_29'] = map_to_master_by_oa(df_age, age_18_29_pct, df_master['oa_code'])
df_master['pct_age_30_65'] = map_to_master_by_oa(df_age, age_30_65_pct, df_master['oa_code'])
df_master['pct_age_over_65'] = map_to_master_by_oa(df_age, age_over_65_pct, df_master['oa_code'])

# --- Gender (Sex file) ---
male_pct = pct_col_after_label(df_sex, 'males')
female_pct = pct_col_after_label(df_sex, 'females')
df_master['pct_male'] = map_to_master_by_oa(df_sex, male_pct, df_master['oa_code'])
df_master['pct_female'] = map_to_master_by_oa(df_sex, female_pct, df_master['oa_code'])

# --- Higher Education (BCH file) ---
bch_total = safe_numeric_col_by_hint(df_bch, 'all categories: highest level of qualification')
bch_level4 = safe_numeric_col_by_hint(df_bch, 'level 4 qualifications and above')
bch_pct = (bch_level4 / bch_total.replace(0, pd.NA) * 100).fillna(0)
df_master['pct_bch'] = map_to_master_by_oa(df_bch, bch_pct, df_master['oa_code'])

# --- Foreign Born (Nativity file) ---
fb_pct = pct_col_after_label(df_fb, 'other countries')
if fb_pct.sum() == 0:
    fb_total = safe_numeric_col_by_hint(df_fb, 'all usual residents')
    fb_other_countries = safe_numeric_col_by_hint(df_fb, 'other countries')
    fb_pct = (fb_other_countries / fb_total.replace(0, pd.NA) * 100).fillna(0)
df_master['pct_fb'] = map_to_master_by_oa(df_fb, fb_pct, df_master['oa_code'])

# --- Students (Students file) ---
stu_active_pct = pct_col_after_label(df_stu, 'economically active: full-time student')
stu_inactive_pct = pct_col_after_label(df_stu, 'economically inactive: student')
stu_pct = stu_active_pct + stu_inactive_pct
if stu_pct.sum() == 0:
    stu_total = safe_numeric_col_by_hint(df_stu, 'all usual residents aged 16 to 74')
    stu_active = safe_numeric_col_by_hint(df_stu, 'economically active: full-time student')
    stu_inactive = safe_numeric_col_by_hint(df_stu, 'economically inactive: student')
    stu_pct = ((stu_active + stu_inactive) / stu_total.replace(0, pd.NA) * 100).fillna(0)
df_master['pct_student'] = map_to_master_by_oa(df_stu, stu_pct, df_master['oa_code'])

# --- Housing Tenure (Tenure file) ---
own_hme_pct = pct_col_after_label(df_ten, 'owned')
rent_pct = pct_col_after_label(df_ten, 'private rented')
if own_hme_pct.sum() == 0 and rent_pct.sum() == 0:
    ten_total = safe_numeric_col_by_hint(df_ten, 'all households')
    ten_owned = safe_numeric_col_by_hint(df_ten, 'owned')
    ten_private = safe_numeric_col_by_hint(df_ten, 'private rented')
    own_hme_pct = (ten_owned / ten_total.replace(0, pd.NA) * 100).fillna(0)
    rent_pct = (ten_private / ten_total.replace(0, pd.NA) * 100).fillna(0)
df_master['pct_own_hme'] = map_to_master_by_oa(df_ten, own_hme_pct, df_master['oa_code'])
df_master['pct_rent'] = map_to_master_by_oa(df_ten, rent_pct, df_master['oa_code'])

# --- Social Class (NS-SeC Approximations) ---
mid_class_pct = pct_sum_after_labels(df_soc, [
    'higher managerial, administrative and professional occupations',
    'lower managerial, administrative and professional occupations'
])
wk_class_pct = pct_sum_after_labels(df_soc, [
    'semi-routine occupations',
    'routine occupations'
])
if mid_class_pct.sum() == 0 and wk_class_pct.sum() == 0:
    print("[WARN] Social class extract lacks detailed categories. Setting class percentages to 0.")
    mid_class_pct = pd.Series(0.0, index=df_soc.index)
    wk_class_pct = pd.Series(0.0, index=df_soc.index)
df_master['pct_mid_class'] = map_to_master_by_oa(df_soc, mid_class_pct, df_master['oa_code'])
df_master['pct_wk_class'] = map_to_master_by_oa(df_soc, wk_class_pct, df_master['oa_code'])

# --- Density Stand-in ---
df_master['pop_den'] = 0.00
df_master['vote_shr'] = 0.00
df_master['census_year'] = CENSUS_YEAR

# 4. Finalize database schema formatting structure
df_final = df_master[[
    'oa_code', 'census_year', 'ward_pop', 'pop_den', 'vote_shr',
    'pct_age_18_29', 'pct_age_30_65', 'pct_age_over_65', 'pct_male', 'pct_female',
    'pct_student', 'pct_bch', 'pct_wk_class', 'pct_mid_class', 'pct_own_hme', 'pct_rent', 'pct_fb'
]].copy()

df_final['oa_code'] = df_final['oa_code'].astype(str).str.strip()
df_final = df_final[
    df_final['oa_code'].notna()
    & (df_final['oa_code'] != '')
    & (df_final['oa_code'].str.lower() != 'nan')
].copy()

float_cols = df_final.select_dtypes(include=['float']).columns
df_final[float_cols] = df_final[float_cols].round(2)

insert_df = df_final[[
    'oa_code', 'census_year',
    'pct_age_18_29', 'pct_age_30_65', 'pct_age_over_65', 'pct_male', 'pct_female',
    'pct_student', 'pct_bch', 'pct_wk_class', 'pct_mid_class', 'pct_own_hme', 'pct_rent', 'pct_fb'
]].copy()

insert_records = list(insert_df.itertuples(index=False, name=None))
print(f"-> Formatted {len(insert_records):,} Output Area records ready for db submission.")

# 5. Connect and stream data to MySQL via SQLAlchemy
try:
    print("\\nConnecting to MySQL Server...")
    engine = create_engine(
        f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    )
    conn = engine.raw_connection()
    cursor = conn.cursor()

    print("[CONFIG] Disabling database foreign key verification constraints...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

    insert_query = """
        INSERT INTO census (
            oa_code, census_year,
            pct_age_18_29, pct_age_30_65, pct_age_over_65, pct_male, pct_female,
            pct_student, pct_bch, pct_wk_class, pct_mid_class, pct_own_hme, pct_rent, pct_fb
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            pct_age_18_29=VALUES(pct_age_18_29),
            pct_age_30_65=VALUES(pct_age_30_65),
            pct_age_over_65=VALUES(pct_age_over_65),
            pct_male=VALUES(pct_male),
            pct_female=VALUES(pct_female),
            pct_student=VALUES(pct_student),
            pct_bch=VALUES(pct_bch),
            pct_wk_class=VALUES(pct_wk_class),
            pct_mid_class=VALUES(pct_mid_class),
            pct_own_hme=VALUES(pct_own_hme),
            pct_rent=VALUES(pct_rent),
            pct_fb=VALUES(pct_fb);
    """

    print("Writing bulk batches to your database table...")
    batch_size = 10000
    for i in range(0, len(insert_records), batch_size):
        cursor.executemany(insert_query, insert_records[i:i + batch_size])

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    conn.commit()
    print("[SUCCESS] Census upload complete! Effectively loaded your baseline rows.")

except (SQLAlchemyError, ValueError, Exception) as err:
    print(f"[ERROR] Transaction rolled back automatically: {err}")
    if 'conn' in locals():
        conn.rollback()

finally:
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()
    print("Database connection securely closed.")
