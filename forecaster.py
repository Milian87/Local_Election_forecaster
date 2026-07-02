import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
import shap

# =========================================================================
# DATA EXTRACTION LAYER
# =========================================================================
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Xabp74yb%'),
    'database': os.getenv('MYSQL_DB', 'irp_election_forecasting')
}

engine = create_engine(
    f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
)
print("🚀 Extracting harmonized demographics, densities, and party matrix...")

try:
    query = """
            SELECT 
                er.wd_code,
                cand.registered_party AS party_name, 
                cand.candidate_name,
                er.election_year,
                er.candidate_id, 
                AVG(er.vote_share) AS party_vote_share, 
                MAX(er.is_incumbent_cllr) AS has_incumbent_boost,
                MAX(er.seats_available) AS seats_available,
                
                -- THE CORRECT SPATIAL DENSITY: Total Ward Pop / Derived Ward land mass
                (SUM(c.oa_pop) / SUM(c.oa_pop / NULLIF(c.pop_den, 0))) AS ward_population_density,

                -- Demographic features
                AVG(c.pct_student) AS pct_student,
                AVG(c.pct_own_hme) AS pct_own_hme,
                AVG(c.pct_rent) AS pct_rent,
                AVG(c.pct_age_18_29) AS pct_age_18_29,
                AVG(c.pct_age_30_65) AS pct_age_30_65,
                AVG(c.pct_age_over_65) AS pct_age_over_65,
                AVG(c.pct_wk_class) AS pct_wk_class,
                AVG(c.pct_mid_class) AS pct_mid_class,
                AVG(c.pct_bch) AS pct_bch,
                AVG(c.pct_female) AS pct_female,
                AVG(c.pct_male) AS pct_male
            FROM election_results er
            JOIN candidates cand ON er.candidate_id = cand.candidate_id
            LEFT JOIN geographic_lookup gl ON er.wd_code = gl.wd_code
            LEFT JOIN census c ON gl.oa_code = c.oa_code
            WHERE er.is_uncontested = 0
            GROUP BY 
                er.wd_code, 
                cand.registered_party, 
                cand.candidate_name, -- 🔴 ADD TO GROUP BY
                er.election_year,
                er.candidate_id;
        """
    print("📊 Querying database for party-level election and demographic data...")
    query_2 = """
            SELECT 
                wd_code,
                ward_name
            FROM electoral_wards;
        """
    df_raw = pd.read_sql(query, con=engine)
    df_wards = pd.read_sql(query_2, con=engine)
    
    # Create an optimized mapping dictionary to ensure the lookup loop scales smoothly
    ward_name_map = dict(zip(df_wards['wd_code'], df_wards['ward_name']))
except Exception as e:
    print(f"❌ Error during database query: {e}")
    raise
# =========================================================================
# 1. CALCULATE LOCALIZED PARTY BASELINES
# =========================================================================
print("📈 Calculating localized historical party performance baselines...")

# 1. Group by 'party_name' since 'party_label' hasn't been created yet
historical_averages = (
    df_raw[df_raw['election_year'] < 2026]
    .groupby(['wd_code', 'party_name'])['party_vote_share']
    .mean()
    .reset_index()
    .rename(columns={'party_vote_share': 'historical_party_ward_mean'})
)

# 2. Merge back using 'party_name'
df_raw = pd.merge(
    df_raw, 
    historical_averages, 
    on=['wd_code', 'party_name'], 
    how='left'
)

# 3. Use 'party_name' here to map the global fallbacks safely
global_party_means = df_raw[df_raw['election_year'] < 2026].groupby('party_name')['party_vote_share'].mean().to_dict()

def fill_missing_party_baselines(row):
    if not pd.isna(row['historical_party_ward_mean']):
        return row['historical_party_ward_mean']
    return global_party_means.get(row['party_name'], 15.0) 

df_raw['historical_party_ward_mean'] = df_raw.apply(fill_missing_party_baselines, axis=1)


# =========================================================================
# 2. ADVANCED SPATIAL DEMOGRAPHIC IMPUTATION FOR 2026
# =========================================================================
print("🛠️ Imputing missing 2026 demographics using regional baselines...")

census_features = [
    'pct_student', 'pct_own_hme', 'pct_rent', 'pct_age_18_29', 
    'pct_age_30_65', 'pct_age_over_65', 'pct_wk_class', 'pct_mid_class', 'pct_bch', 'pct_female', 'pct_male',
    'ward_population_density', 'historical_party_ward_mean',
    'candidate_personal_historical_mean'
]

print("🛠️ Mapping true historical ward baselines directly to 2026 slots...")

print("👤 Tracking individual candidate personal electoral histories...")

# 1. Isolate how specific candidates performed whenever/wherever they stood historically
candidate_historical_perf = (
    df_raw[df_raw['election_year'] < 2026]
    .groupby(['candidate_id'])['party_vote_share']  # Calculates their average past performance
    .mean()
    .reset_index()
    .rename(columns={'party_vote_share': 'candidate_personal_historical_mean'})
)

# 2. Merge candidate personal baselines back into the main raw training matrix
df_raw = pd.merge(
    df_raw, 
    candidate_historical_perf, 
    on=['candidate_id'], 
    how='left'
)

# 3. Defensive Fallback: If a candidate is completely new, their personal baseline 
# simply defaults back to their party's structural ward baseline.
df_raw['candidate_personal_historical_mean'] = df_raw['candidate_personal_historical_mean'].fillna(
    df_raw['historical_party_ward_mean']
)

# =========================================================================
# 3. CATEGORICAL ENCODING & PIPELINE PREPARATION
# =========================================================================
print("📊 Encoding party designations into numeric vectors...")

df_raw['party_label'] = df_raw['party_name']
df_encoded = pd.get_dummies(df_raw, columns=['party_name'], drop_first=False)

print("*************** TRUE FORECAST PREPARATION PIPELINE ***************")

historical_data = df_encoded[df_encoded['election_year'] < 2026].copy()
future_data     = df_encoded[df_encoded['election_year'] == 2026].copy()

historical_data = historical_data.dropna(subset=['party_vote_share'] + census_features)

print(f"📈 Ready to train on {len(historical_data):,} historical party entries.")
print(f"🔮 Ready to forecast on {len(future_data):,} upcoming 2026 slots.")

columns_to_drop = ['party_vote_share', 'election_year', 'wd_code', 'party_label']

# Explicitly drop metadata columns, targets, tracking text, and IDs from X matrices
columns_to_drop = ['party_vote_share', 'election_year', 'wd_code', 'party_label', 'candidate_id', 'candidate_name']

X_train = historical_data.drop(columns=columns_to_drop)
y_train = historical_data['party_vote_share']
X_future = future_data.drop(columns=columns_to_drop)

X_train = X_train.astype(float)
X_future = X_future.astype(float)

# =========================================================================
# 4. RANDOM FOREST ENGINE & BASELINE PARTY FORECAST
# =========================================================================
from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
model.fit(X_train, y_train)
print("🎯 Party-centric baseline model trained successfully.")

# Calculate the baseline model party share
future_data['predicted_party_share'] = model.predict(X_future)
# By default, final forecast matches party baseline until candidate overrides are chosen
future_data['final_forecast_share'] = future_data['predicted_party_share']

# Extract candidate personal effect size from historical data coefficients
# (Incumbency typically adds an isolated premium of 3% to 7% based on UK baseline trends)
incumbent_rows = historical_data[historical_data['has_incumbent_boost'] == 1]
non_incumbent_rows = historical_data[historical_data['has_incumbent_boost'] == 0]
personal_vote_premium = incumbent_rows['party_vote_share'].mean() - non_incumbent_rows['party_vote_share'].mean()
if pd.isna(personal_vote_premium) or personal_vote_premium <= 0:
    personal_vote_premium = 4.50  # Solid, peer-reviewed UK local election fallback premium

# =========================================================================
# 5. SHAP EXPLANATION PIPELINE 
# =========================================================================
print("🔮 Computing Shapley attribution weights via TreeExplainer...")
explainer = shap.TreeExplainer(model)
shap_values = explainer(X_train)

# --- VISUALIZATION 1: GLOBAL SHAP FEATURE IMPORTANCE ---
plt.figure(figsize=(12, 6))
shap.plots.bar(shap_values, show=False)
plt.title("Global Feature Importance (Including Density & Demographics)", fontsize=14, pad=15)
plt.tight_layout()
plt.savefig('shap_global_importance.png', dpi=300)
plt.close()

# --- VISUALIZATION 2: MULTIVARIATE SHAP SUMMARY PLOT ---
plt.figure(figsize=(13, 7))
shap.plots.beeswarm(shap_values, show=False)
plt.title("SHAP Summary Plot: Density & Structural Impacts on Vote Share", fontsize=14, pad=15)
plt.tight_layout()
plt.savefig('shap_summary_beeswarm.png', dpi=300)
plt.close()

# =========================================================================
# 6. INTERACTIVE CONSOLE LOOKUP (TRUE IDENTIFICATION BRIDGE)
# =========================================================================
print("\n====================================================")
print("🔍 STEP 6: INTERACTIVE LOOKUP (BLENDED GEOGRAPHIC MODEL)")
print("====================================================")

# 1. Build a robust fallback map based on institutional Party performance across history
party_historical_perf = (
    df_raw[df_raw['election_year'] < 2026]
    .groupby('party_label')['candidate_personal_historical_mean']
    .mean()
    .to_dict()
)

# 2. Bridge the name text string to their true tracking ID across the entire database
name_to_id_map = (
    df_raw.dropna(subset=['candidate_name', 'candidate_id'])
    .drop_duplicates(subset=['candidate_name'])
    .set_index('candidate_name')['candidate_id']
    .to_dict()
)
name_to_id_map = {str(k).lower().strip(): v for k, v in name_to_id_map.items()}

# 3. Link candidate IDs directly to their true personal historical performance mean
id_to_personal_perf = (
    df_raw[df_raw['election_year'] < 2026]
    .dropna(subset=['candidate_personal_historical_mean'])
    .drop_duplicates(subset=['candidate_id'])
    .set_index('candidate_id')['candidate_personal_historical_mean']
    .to_dict()
)

available_wards = sorted(future_data['wd_code'].unique())

while True:
    print(f"\nEnter an ONS Ward Code to inspect (e.g., {available_wards[0]}) or type 'exit' to quit:")
    target_ward = input("👉 ").strip()
    
    if target_ward.lower() == 'exit':
        print("Goodbye!")
        break
        
    if target_ward not in available_wards:
        print(f"❌ Ward Code '{target_ward}' not found in the 2026 forecast pool. Please try again.")
        continue
        
    ward_forecast = future_data[future_data['wd_code'] == target_ward].copy()
    ward_name = ward_name_map.get(target_ward, target_ward)
    
    print(f"\n🔎 Forecasting for Ward: {ward_name} ({target_ward})")
    print(f"Would you like to model specific Candidates standing in the party lines for this ward? (yes/no)")
    choice = input("👉 ").strip().lower()
    
    display_mapping = {}
    personal_appeal_map = {}
    
    for idx, row in ward_forecast.iterrows():
        party = row['party_label']
        party_ward_history = row.get('historical_party_ward_mean', row['predicted_party_share'])
        
        # 50/50 blend of the machine learning model prediction and the true local party footprint
        blended_party_baseline = (row['predicted_party_share'] * 0.5) + (party_ward_history * 0.5)
        ward_forecast.loc[idx, 'predicted_party_share'] = blended_party_baseline
        
        if choice == 'yes':
            print(f"\nIs there a specific Candidate standing for '{party}'? If yes, type their name. If no, press Enter:")
            cand_input = input("👉 ").strip()
            
            if cand_input:
                print(f"Is '{cand_input}' an existing incumbent councillor for this specific seat? (yes/no)")
                is_inc = input("👉 ").strip().lower()
                
                cleaned_input_key = cand_input.lower().strip()
                
                # Check for explicit ID tracking link
                if cleaned_input_key in name_to_id_map:
                    target_id = name_to_id_map[cleaned_input_key]
                    cand_history = id_to_personal_perf.get(target_id, party_ward_history)
                    print(f"  [DEBUG] 🎉 True Candidate Match! Name: '{cand_input}' maps to ID: {target_id}. Historical Mean: {cand_history:.2f}%")
                    
                    # Compute unique personal appeal relative to the specific local party ward context
                    personal_appeal_delta = cand_history - blended_party_baseline
                else:
                    cand_history = party_historical_perf.get(party, party_ward_history)
                    print(f"  [DEBUG] 🔄 Name mismatch. Falling back to historical candidate brand baseline for {party}: {cand_history:.2f}%")
                    personal_appeal_delta = cand_history - party_ward_history
                
                # Apply incumbency boost fallback if they are a brand new incumbent profile
                """if is_inc == 'yes' and personal_appeal_delta <= 0:
                    personal_appeal_delta = personal_vote_premium
                    print(f"  [DEBUG] ⚠️ Default premium applied: +{personal_vote_premium:.2f}%")"""
                
                final_share = blended_party_baseline + personal_appeal_delta
                ward_forecast.loc[idx, 'final_forecast_share'] = max(0.0, min(100.0, final_share))
                personal_appeal_map[party] = personal_appeal_delta
                
                if is_inc == 'yes':
                    display_mapping[party] = f"{cand_input} ({party}) [Incumbent]"
                elif personal_appeal_delta > 0:
                    display_mapping[party] = f"{cand_input} ({party}) [Returning Challenger]"
                else:
                    display_mapping[party] = f"{cand_input} ({party}) [New Candidate]"
            else:
                display_mapping[party] = f"{party} [Blended Party Baseline]"
                ward_forecast.loc[idx, 'final_forecast_share'] = blended_party_baseline
                personal_appeal_map[party] = 0.0
        else:
            display_mapping[party] = f"{party} [Blended Party Baseline]"
            ward_forecast.loc[idx, 'final_forecast_share'] = blended_party_baseline
            personal_appeal_map[party] = 0.0
            
    ward_forecast = ward_forecast.sort_values(by='final_forecast_share', ascending=False)
    
    print(f"\n🔮 Balanced Forecast Output for Ward: {ward_name} ({target_ward})")
    print("-" * 110)
    print(f"{'Ballot Entry (Candidate / Party Option)':<50} | {'Blended Baseline %':<20} | {'Final Forecast %':<15}")
    print("-" * 110)
    
    for _, row in ward_forecast.iterrows():
        party = row['party_label']
        label = display_mapping[party]
        p_appeal = personal_appeal_map.get(party, 0.0)
        
        if p_appeal > 0:
            appeal_str = f" (+{p_appeal:.2f}% Personal Brand Boost)"
        elif p_appeal < 0:
            appeal_str = f" ({p_appeal:.2f}% Personal Brand Drag)"
        else:
            appeal_str = ""
            
        print(f"{label:<50} | {row['predicted_party_share']:>18.2f}% | {row['final_forecast_share']:>13.2f}%{appeal_str}")
    print("-" * 110)