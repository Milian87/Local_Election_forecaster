import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
import shap
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

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
    with engine.connect() as conn:
        poll_col = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = :schema_name
                  AND TABLE_NAME = 'election_results'
                  AND COLUMN_NAME IN ('national_poll_party_share', 'national_poll_share')
                ORDER BY CASE COLUMN_NAME WHEN 'national_poll_party_share' THEN 1 ELSE 2 END
                LIMIT 1
                """
            ),
            {"schema_name": db_config['database']},
        ).scalar()

    if not poll_col:
        raise RuntimeError(
            "Missing national poll share column in election_results. "
            "Expected one of: national_poll_party_share, national_poll_share"
        )

    query = f"""
                SELECT 
                    er.wd_code,
                    cand.registered_party AS party_name, 
                    cand.candidate_name,
                    er.election_year,
                    er.candidate_id, 
                    AVG(er.vote_share) AS party_vote_share, 
                    MAX(er.is_incumbent_cllr) AS has_incumbent_boost,
                    MAX(er.seats_available) AS seats_available,
                    
                    -- 🔴 ADD NATIONAL POLL TIMELINE FEATURE
                    AVG(er.{poll_col}) AS national_poll_share,
                    
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
                    cand.candidate_name,
                    er.election_year,
                    er.candidate_id;
            """
    print("📊 Querying database for party-level election and demographic data...")
    query_2 = """
            SELECT 
                wd_code,
                ward_name,
                cc_code
            FROM electoral_wards;
        """
    df_raw = pd.read_sql(query, con=engine)
    df_wards = pd.read_sql(query_2, con=engine)
    
    # Create an optimized mapping dictionary to ensure the lookup loop scales smoothly
    ward_name_map = dict(zip(df_wards['wd_code'], df_wards['ward_name']))
    ward_cc_map = dict(zip(df_wards['wd_code'], df_wards['cc_code']))
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
    'candidate_personal_historical_mean',
    'national_poll_share'  # 🔴 Added to the training feature matrix
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


# Explicitly drop metadata columns, targets, tracking text, and IDs from X matrices
columns_to_drop = ['party_vote_share', 'election_year', 'wd_code', 'party_label', 'candidate_id', 'candidate_name']

X_train = historical_data.drop(columns=columns_to_drop)
y_train = historical_data['party_vote_share']
X_future = future_data.drop(columns=columns_to_drop)

X_train = X_train.astype(float)
X_future = X_future.astype(float)

# =========================================================================
# 4. RANDOM FOREST ENGINE & ACCURACY METRICS
# =========================================================================

# 1. Split historical data to properly evaluate predictive performance
X_train_split, X_test_split, y_train_split, y_test_split = train_test_split(
    X_train, y_train, test_size=0.2, random_state=42
)

# 2. Train the Random Forest Engine
model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
model.fit(X_train_split, y_train_split)
print("🎯 Party-centric baseline model trained successfully.")

# 3. Evaluate Predictions on the Hidden Test Set
y_pred = model.predict(X_test_split)

# 4. Compute R² and RMSE
model_rmse = np.sqrt(mean_squared_error(y_test_split, y_pred))
model_r2 = r2_score(y_test_split, y_pred)

print("\n====================================================")
print("📈 HISTORICAL BACKTESTING PERFORMANCE METRICS")
print("====================================================")
print(f"📊 Root Mean Squared Error (RMSE): {model_rmse:.2f}% (Average prediction drift)")
print(f"📉 Coefficient of Determination (R²): {model_r2:.4f} ({model_r2*100:.2f}% of variance explained)")
print("====================================================\n")

# Re-fit the model on the full historical dataset for maximum 2026 forecast accuracy
model.fit(X_train, y_train)
future_data['predicted_party_share'] = model.predict(X_future)
future_data['final_forecast_share'] = future_data['predicted_party_share']

# =========================================================================
# 5. SHAP EXPLANATION PIPELINE 
# =========================================================================
print("🔮 Computing Shapley attribution weights via TreeExplainer...")
explainer = shap.TreeExplainer(model)
shap_values = explainer(X_train)

# --- VISUALIZATION 1: GLOBAL SHAP FEATURE IMPORTANCE ---
plt.figure(figsize=(12, 6))
shap.plots.bar(shap_values, show=False)
plt.title("Global Feature Importance\n(Including Density & Demographics)", fontsize=14, pad=15)
plt.tight_layout()
plt.savefig('shap_global_importance.png', dpi=300)
# show the plot in a window without blocking the script execution
plt.show()
plt.close()

# --- VISUALIZATION 2: MULTIVARIATE SHAP SUMMARY PLOT ---
plt.figure(figsize=(13, 7))
shap.plots.beeswarm(shap_values, show=False)
plt.title("SHAP Summary Plot: Density & Structural\nImpacts on Vote Share", fontsize=14, pad=15)
plt.tight_layout()
plt.savefig('shap_summary_beeswarm.png', dpi=300)
plt.show()
plt.close()
# =========================================================================
# 5.5: look up Norfolk County Council 2026 Results
# =========================================================================

print("\n====================================================")
print("📊 AUTOMATED COUNCIL-WIDE SUMMARY: NORFOLK COUNTY COUNCIL")
print("====================================================")

NORFOLK_CC_CODE = 'E10000020'

# 1. Rebuild lookup tracking structures from historical context data arrays
party_historical_perf = (
    df_raw[df_raw['election_year'] < 2026]
    .groupby('party_label')['candidate_personal_historical_mean']
    .mean()
    .to_dict()
)

# 2. Isolate 2026 seats belonging to Norfolk County Council specifically.
norfolk_future = future_data[
    future_data['wd_code'].map(ward_cc_map).eq(NORFOLK_CC_CODE)
].copy()

if norfolk_future.empty:
    print(f"⚠️ [WARNING] No future 2026 slots found for Norfolk County Council ({NORFOLK_CC_CODE}).")
    # Fallback to evaluating all available division slots if filtered subset is empty
    norfolk_future = future_data.copy()

# 3. Initialize bulk council tracking states
seats_won = {}
total_council_projections = []
unique_norfolk_divisions = sorted(norfolk_future['wd_code'].unique())

print(f"📈 Automating predictions across {len(unique_norfolk_divisions)} County Council Divisions...")

# 4. Process every division automatically without waiting for user input parameters
for target_division in unique_norfolk_divisions:
    div_forecast = norfolk_future[norfolk_future['wd_code'] == target_division].copy()
    div_name = ward_name_map.get(target_division, target_division)
    
    # Execute the 50/50 baseline blenders array calculations
    for idx, row in div_forecast.iterrows():
        party = row['party_label']
        party_ward_history = row.get('historical_party_ward_mean', row['predicted_party_share'])
        
        # Balance out model metrics against real long-term regional performance anchors
        blended_share = (row['predicted_party_share'] * 0.5) + (party_ward_history * 0.5)
        div_forecast.loc[idx, 'final_forecast_share'] = blended_share

    # Normalize division-level numbers so probability vectors sum to 100% cleanly
    raw_total = div_forecast['final_forecast_share'].sum()
    if raw_total > 0:
        div_forecast['normalized_forecast_share'] = (div_forecast['final_forecast_share'] / raw_total) * 100.0
    else:
        div_forecast['normalized_forecast_share'] = 0.0

    # Determine the seat winner based on plurality vote share (First-Past-The-Post system)
    winner_row = div_forecast.sort_values(by='normalized_forecast_share', ascending=False).iloc[0]
    winning_party = winner_row['party_label']
    winning_margin = winner_row['normalized_forecast_share']
    
    seats_won[winning_party] = seats_won.get(winning_party, 0) + 1
    
    # Store clean row metrics for council-wide reporting
    total_council_projections.append({
        'code': target_division,
        'name': div_name,
        'winner': winning_party,
        'share': winning_margin
    })

# =========================================================================
# 📊 CONSOLE SUMMARY REPORT GENERATION
# =========================================================================
df_summary = pd.DataFrame(total_council_projections).sort_values(by='name')

print("\n🔮 INDIVIDUAL DIVISION PROJECTIONS (NORFOLK COUNTY COUNCIL 2026)")
print("-" * 90)
print(f"{'Division Code':<15} | {'Division Name':<35} | {'Predicted Winner':<20} | {'Margin %':<10}")
print("-" * 90)
for _, row in df_summary.iterrows():
    print(f"{row['code']:<15} | {row['name']:<35} | {row['winner']:<20} | {row['share']:>8.2f}%")
print("-" * 90)

print("\n🏛️ FINAL SEAT PROJECTIONS SUMMARY MATRIX")
print("-" * 45)
print(f"{'Political Party Option Designation':<30} | {'Seats Won':<10}")
print("-" * 45)
for party, seats in sorted(seats_won.items(), key=lambda item: item[1], reverse=True):
    print(f"{party:<30} | {seats:>9}")
print("-" * 45)
print(f"{'Total Projected Seats Checked':<30} | {sum(seats_won.values()):>9}")
print("-" * 45)

# Clear execution prompt lock allowing clean programmatic exit patterns
while True:
    print("\nProcessing complete. Type 'exit' to cleanly close the program pipeline:")
    user_quit = input("👉 ").strip().lower()
    if user_quit == 'exit':
        print("Goodbye!")
        break

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
            
    # Normalize ward-level forecasts so displayed vote shares sum to 100%
    raw_total = ward_forecast['final_forecast_share'].sum()
    if raw_total > 0:
        ward_forecast['normalized_forecast_share'] = (
            ward_forecast['final_forecast_share'] / raw_total
        ) * 100.0
    else:
        ward_forecast['normalized_forecast_share'] = 0.0

    ward_forecast = ward_forecast.sort_values(by='final_forecast_share', ascending=False)
    
    print(f"\n🔮 Balanced Forecast Output for Ward: {ward_name} ({target_ward})")
    print("-" * 134)
    print(
        f"{'Ballot Entry (Candidate / Party Option)':<50} | {'Blended Baseline %':<20} | {'Raw Forecast %':<15} | {'Vote Share %':<12}"
    )
    print("-" * 134)
    
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
            
        print(
            f"{label:<50} | {row['predicted_party_share']:>18.2f}% | {row['final_forecast_share']:>13.2f}% | {row['normalized_forecast_share']:>10.2f}%{appeal_str}"
        )
    print("-" * 134)
    print(
        f"{'Ward Totals':<50} | {'':<20} | {ward_forecast['final_forecast_share'].sum():>13.2f}% | {ward_forecast['normalized_forecast_share'].sum():>10.2f}%"
    )
    print("-" * 134)

