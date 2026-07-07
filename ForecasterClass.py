# =========================================================================
# IRP Election Forecasting Program - Predictive Engine Layer
# Class wrapper for Random Forest baseline estimation and Shapley weights
# Author: Ian Milburn
# Date: 2026-07-04
# =========================================================================

import os
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
class Forecaster:
    """
    Predictive engine that trains a hybrid Random Forest pipeline on hyper-local 
    demographics and national polling trends, outputting ONS ward level predictions.
    """
    def __init__(self, db_config=None):
        # 1. Fallback connection environment mappings
        self.db_config = db_config or {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', '3306')),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', 'Xabp74yb%'),
            'database': os.getenv('MYSQL_DB', 'irp_election_forecasting')
        }
        
        self.engine = create_engine(
            f"mysql+pymysql://{self.db_config['user']}:{self.db_config['password']}@"
            f"{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        )
        
        # Define foundational tracking features used by the machine learning matrix
        self.census_features = [
            'pct_student', 'pct_own_hme', 'pct_rent', 'pct_age_18_29', 
            'pct_age_30_65', 'pct_age_over_65', 'pct_wk_class', 'pct_mid_class', 
            'pct_bch', 'pct_female', 'pct_male', 'ward_population_density', 
            'historical_party_ward_mean', 'candidate_personal_historical_mean',
            'national_poll_share'
        ]
        
        # Internal placeholders for models and data matrices
        self.model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        self.df_raw = None
        self.future_data = None
        self.ward_name_map = {}
        self.party_historical_perf = {}
        self.name_to_id_map = {}
        self.id_to_personal_perf = {}
        self.available_wards = []

    def extract_and_prepare_data(self):
        """Connects to the database and builds the baseline geographic matrices."""
        print("🚀 Extracting harmonized demographics, densities, and party matrix...")
        try:
            # Dynamically identify the polling column based on schema setup
            with self.engine.connect() as conn:
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
                    {"schema_name": self.db_config['database']},
                ).scalar()

            if not poll_col:
                raise RuntimeError(
                    "Missing national poll share column in election_results. "
                    "Expected one of: national_poll_party_share, national_poll_share"
                )

            query = f"""
                SELECT 
                    er.wd_code, cand.registered_party AS party_name, cand.candidate_name,
                    er.election_year, er.candidate_id, AVG(er.vote_share) AS party_vote_share, 
                    MAX(er.is_incumbent_cllr) AS has_incumbent_boost, MAX(er.seats_available) AS seats_available,
                    AVG(er.{poll_col}) AS national_poll_share,
                    (SUM(c.oa_pop) / SUM(c.oa_pop / NULLIF(c.pop_den, 0))) AS ward_population_density,
                    AVG(c.pct_student) AS pct_student, AVG(c.pct_own_hme) AS pct_own_hme, AVG(c.pct_rent) AS pct_rent, 
                    AVG(c.pct_age_18_29) AS pct_age_18_29, AVG(c.pct_age_30_65) AS pct_age_30_65, 
                    AVG(c.pct_age_over_65) AS pct_age_over_65, AVG(c.pct_wk_class) AS pct_wk_class, 
                    AVG(c.pct_mid_class) AS pct_mid_class, AVG(c.pct_bch) AS pct_bch, 
                    AVG(c.pct_female) AS pct_female, AVG(c.pct_male) AS pct_male
                FROM election_results er
                JOIN candidates cand ON er.candidate_id = cand.candidate_id
                LEFT JOIN geographic_lookup gl ON er.wd_code = gl.wd_code
                LEFT JOIN census c ON gl.oa_code = c.oa_code
                WHERE er.is_uncontested = 0
                GROUP BY er.wd_code, cand.registered_party, cand.candidate_name, er.election_year, er.candidate_id;
            """
            
            print("📊 Querying database for party-level election and demographic data...")
            query_wards = "SELECT wd_code, ward_name FROM electoral_wards;"
            
            self.df_raw = pd.read_sql(query, con=self.engine)
            df_wards = pd.read_sql(query_wards, con=self.engine)
            self.ward_name_map = dict(zip(df_wards['wd_code'], df_wards['ward_name']))
            
        except Exception as e:
            print(f"❌ Error during data extraction layout query: {e}")
            raise

        # Calculate localized historical baseline aggregates
        print("📈 Calculating localized historical party performance baselines...")
        historical_averages = (
            self.df_raw[self.df_raw['election_year'] < 2026]
            .groupby(['wd_code', 'party_name'])['party_vote_share']
            .mean()
            .reset_index()
            .rename(columns={'party_vote_share': 'historical_party_ward_mean'})
        )
        self.df_raw = pd.merge(self.df_raw, historical_averages, on=['wd_code', 'party_name'], how='left')

        # Map global fallbacks for new parties standing in unfamiliar patches
        global_party_means = self.df_raw[self.df_raw['election_year'] < 2026].groupby('party_name')['party_vote_share'].mean().to_dict()
        self.df_raw['historical_party_ward_mean'] = self.df_raw.apply(
            lambda r: r['historical_party_ward_mean'] if not pd.isna(r['historical_party_ward_mean']) else global_party_means.get(r['party_name'], 15.0),
            axis=1
        )

        # Candidate personal historic brand delta tracking
        print("👤 Tracking individual candidate personal electoral histories...")
        candidate_historical_perf = (
            self.df_raw[self.df_raw['election_year'] < 2026]
            .groupby(['candidate_id'])['party_vote_share']
            .mean()
            .reset_index()
            .rename(columns={'party_vote_share': 'candidate_personal_historical_mean'})
        )
        self.df_raw = pd.merge(self.df_raw, candidate_historical_perf, on=['candidate_id'], how='left')
        self.df_raw['candidate_personal_historical_mean'] = self.df_raw['candidate_personal_historical_mean'].fillna(
            self.df_raw['historical_party_ward_mean']
        )

        # Build lookup optimization maps for step 6 interactive loop structures
        self.party_historical_perf = (
            self.df_raw[self.df_raw['election_year'] < 2026]
            .groupby('party_name')['candidate_personal_historical_mean']
            .mean()
            .to_dict()
        )
        name_to_id = (
            self.df_raw.dropna(subset=['candidate_name', 'candidate_id'])
            .drop_duplicates(subset=['candidate_name'])
            .set_index('candidate_name')['candidate_id']
            .to_dict()
        )
        self.name_to_id_map = {str(k).lower().strip(): v for k, v in name_to_id.items()}
        self.id_to_personal_perf = (
            self.df_raw[self.df_raw['election_year'] < 2026]
            .dropna(subset=['candidate_personal_historical_mean'])
            .drop_duplicates(subset=['candidate_id'])
            .set_index('candidate_id')['candidate_personal_historical_mean']
            .to_dict()
        )

    def train_and_evaluate(self):
        """Prepares input vectors, executes validation train splits, and prints metrics."""
        print("📊 Encoding party designations into numeric vectors...")
        self.df_raw['party_label'] = self.df_raw['party_name']
        df_encoded = pd.get_dummies(self.df_raw, columns=['party_name'], drop_first=False)

        historical_data = df_encoded[df_encoded['election_year'] < 2026].copy()
        self.future_data = df_encoded[df_encoded['election_year'] == 2026].copy()

        historical_data = historical_data.dropna(subset=['party_vote_share'] + self.census_features)
        self.available_wards = sorted(self.future_data['wd_code'].unique())

        print("*************** TRUE FORECAST PREPARATION PIPELINE ***************")
        print(f"📈 Ready to train on {len(historical_data):,} historical party entries.")
        print(f"🔮 Ready to forecast on {len(self.future_data):,} upcoming 2026 slots.")

        columns_to_drop = ['party_vote_share', 'election_year', 'wd_code', 'party_label', 'candidate_id', 'candidate_name']
        X_train = historical_data.drop(columns=columns_to_drop).astype(float)
        y_train = historical_data['party_vote_share']
        X_future = self.future_data.drop(columns=columns_to_drop).astype(float)

        # Split historical segments for test-set verification
        X_tr, X_te, y_tr, y_te = train_test_split(X_train, y_train, test_size=0.2, random_state=42)
        self.model.fit(X_tr, y_tr)
        
        # Out-of-set Backtesting validation evaluation metrics calculations
        y_pred = self.model.predict(X_te)
        model_rmse = np.sqrt(mean_squared_error(y_te, y_pred))
        model_r2 = r2_score(y_te, y_pred)

        print("\n====================================================")
        print("📈 HISTORICAL BACKTESTING PERFORMANCE METRICS")
        print("====================================================")
        print(f"📊 Root Mean Squared Error (RMSE): {model_rmse:.2f}% (Average prediction drift)")
        print(f"📉 Coefficient of Determination (R²): {model_r2:.4f} ({model_r2*100:.2f}% of variance explained)")
        print("====================================================\n")

        # Refit on absolute master footprint dataset for real 2026 deployment estimation
        self.model.fit(X_train, y_train)
        self.future_data['predicted_party_share'] = self.model.predict(X_future)
        self.future_data['final_forecast_share'] = self.future_data['predicted_party_share']

    def generate_shap_explanations(self):
        """Calculates Shapley weights and saves vector visual outputs to storage."""
        print("🔮 Computing Shapley attribution weights via TreeExplainer...")
        columns_to_drop = ['party_vote_share', 'election_year', 'wd_code', 'party_label', 'candidate_id', 'candidate_name']
        historical_data = self.df_raw[self.df_raw['election_year'] < 2026].dropna(subset=['party_vote_share'] + self.census_features)
        df_encoded = pd.get_dummies(self.df_raw, columns=['party_name'], drop_first=False)
        X_train = df_encoded[df_encoded['election_year'] < 2026].dropna(subset=['party_vote_share'] + self.census_features).drop(columns=columns_to_drop).astype(float)

        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer(X_train)

        plt.figure(figsize=(12, 6))
        shap.plots.bar(shap_values, show=False)
        plt.title("Global Feature Importance (Including Density & Demographics)", fontsize=14, pad=15)
        plt.tight_layout()
        plt.savefig('shap_global_importance.png', dpi=300)
        plt.close()

        plt.figure(figsize=(13, 7))
        shap.plots.beeswarm(shap_values, show=False)
        plt.title("SHAP Summary Plot: Density & Structural Impacts on Vote Share", fontsize=14, pad=15)
        plt.tight_layout()
        plt.savefig('shap_summary_beeswarm.png', dpi=300)
        plt.close()
        print("💾 SHAP explanation graphics exported cleanly as local image files.")

    def inspect_ward_interactively(self, target_ward, choose_modeling='no', candidate_inputs=None):
        """
        Processes a single ward forecast given localized interactive user selections.
        Accepts dictionary configurations for automated GUI bindings.
        """
        if target_ward not in self.available_wards:
            return None

        ward_forecast = self.future_data[self.future_data['wd_code'] == target_ward].copy()
        display_mapping = {}
        personal_appeal_map = {}
        candidate_inputs = candidate_inputs or {}

        for idx, row in ward_forecast.iterrows():
            party = row['party_label']
            party_ward_history = row.get('historical_party_ward_mean', row['predicted_party_share'])
            
            blended_party_baseline = (row['predicted_party_share'] * 0.5) + (party_ward_history * 0.5)
            ward_forecast.loc[idx, 'predicted_party_share'] = blended_party_baseline
            
            if choose_modeling == 'yes' and party in candidate_inputs:
                cand_data = candidate_inputs[party]
                cand_input = cand_data.get('name', '').strip()
                is_inc = cand_data.get('is_incumbent', 'no').strip().lower()
                
                if cand_input:
                    cleaned_input_key = cand_input.lower().strip()
                    if cleaned_input_key in self.name_to_id_map:
                        target_id = self.name_to_id_map[cleaned_input_key]
                        cand_history = self.id_to_personal_perf.get(target_id, party_ward_history)
                        personal_appeal_delta = cand_history - blended_party_baseline
                    else:
                        cand_history = self.party_historical_perf.get(party, party_ward_history)
                        personal_appeal_delta = cand_history - party_ward_history
                    
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

        # Normalization verification step so shares scale to 100% cleanly
        raw_total = ward_forecast['final_forecast_share'].sum()
        ward_forecast['normalized_forecast_share'] = (ward_forecast['final_forecast_share'] / raw_total * 100.0) if raw_total > 0 else 0.0
        return ward_forecast.sort_values(by='final_forecast_share', ascending=False), display_mapping, personal_appeal_map

    def start_console_loop(self):
        """Traditional terminal execution loop for standalone local operations."""
        print("\n====================================================")
        print("🔍 STEP 6: INTERACTIVE LOOKUP (BLENDED GEOGRAPHIC MODEL)")
        print("====================================================")
        
        while True:
            print(f"\nEnter an ONS Ward Code to inspect (e.g., {self.available_wards[0]}) or type 'exit' to quit:")
            target_ward = input("👉 ").strip()
            if target_ward.lower() == 'exit':
                print("Goodbye!")
                break
            if target_ward not in self.available_wards:
                print(f"❌ Ward Code '{target_ward}' not found in the pool.")
                continue

            ward_name = self.ward_name_map.get(target_ward, target_ward)
            print(f"\n🔎 Forecasting for Ward: {ward_name} ({target_ward})")
            print("Would you like to model specific Candidates standing in the party lines? (yes/no)")
            choice = input("👉 ").strip().lower()

            candidate_inputs = {}
            if choice == 'yes':
                # Isolate parties currently contesting this precise ward asset frame
                contesting_parties = self.future_data[self.future_data['wd_code'] == target_ward]['party_label'].unique()
                for party in contesting_parties:
                    print(f"\nIs there a specific Candidate standing for '{party}'? If yes, type name. If no, Enter:")
                    name = input("👉 ").strip()
                    if name:
                        print(f"Is '{name}' an existing incumbent councillor for this specific seat? (yes/no)")
                        is_inc = input("👉 ").strip().lower()
                        candidate_inputs[party] = {'name': name, 'is_incumbent': is_inc}

            result_df, display_mapping, personal_appeal_map = self.inspect_ward_interactively(target_ward, choice, candidate_inputs)
            
            print(f"\n🔮 Balanced Forecast Output for Ward: {ward_name} ({target_ward})")
            print("-" * 134)
            print(f"{'Ballot Entry (Candidate / Party Option)':<50} | {'Blended Baseline %':<20} | {'Raw Forecast %':<15} | {'Vote Share %':<12}")
            print("-" * 134)
            
            for _, row in result_df.iterrows():
                party = row['party_label']
                label = display_mapping[party]
                p_appeal = personal_appeal_map.get(party, 0.0)
                appeal_str = f" (+{p_appeal:.2f}% Personal Brand Boost)" if p_appeal > 0 else (f" ({p_appeal:.2f}% Personal Brand Drag)" if p_appeal < 0 else "")
                print(f"{label:<50} | {row['predicted_party_share']:>18.2f}% | {row['final_forecast_share']:>13.2f}% | {row['normalized_forecast_share']:>10.2f}%{appeal_str}")
            print("-" * 134)
            print(f"{'Ward Totals':<50} | {'':<20} | {result_df['final_forecast_share'].sum():>13.2f}% | {result_df['normalized_forecast_share'].sum():>10.2f}%")
            print("-" * 134)
"""
if __name__ == "__main__":
    # Test script initialization loop
    forecaster = Forecaster()
    print("****************** Running from the class *******************")
    forecaster.extract_and_prepare_data()
    forecaster.train_and_evaluate()
    forecaster.generate_shap_explanations()
    forecaster.start_console_loop()"""