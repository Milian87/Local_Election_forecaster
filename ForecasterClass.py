# =========================================================================
# IRP Election Forecasting Program - Advanced Predictive Engine Layer
# Class wrapper implementing Tactical Voting Models & Surge Extrapolation
# Author: Ian Milburn
# Date: 2026-07-10
# =========================================================================

import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
import shap

# Machine Learning framework dependencies
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split, GridSearchCV

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBRegressor = None
    XGBOOST_AVAILABLE = False


class Forecaster:
    """
    Advanced predictive engine that transforms targets to change-in-share (Δ)
    and engineers tactical metrics (top_2 margins, wasted_vote flags, left_right indexes)
    to model volatile electoral surge mechanics and voter coordination.
    """
    def __init__(self, db_config=None, use_xgboost=True):
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
        
        # Upgraded feature array (continuous floats and binary flags)
        self.census_features = [
            'pct_student', 'pct_own_hme', 'pct_rent', 'pct_age_18_29', 
            'pct_age_30_65', 'pct_age_over_65', 'pct_wk_class', 'pct_mid_class', 
            'pct_bch', 'pct_female', 'pct_male', 'ward_population_density', 
            'historical_party_ward_mean', 'candidate_personal_historical_mean',
            'national_poll_share',
            'top_2', 'left_right', 'wasted_vote'  # Tactical Voting Features
        ]
        
        # Select architecture paradigm based on surge volatility configuration
        if use_xgboost and XGBOOST_AVAILABLE:
            print("🚀 Initializing Sequential Gradient Boosting Architecture (XGBoost)...")
            self.model = XGBRegressor(
                n_estimators=300,
                max_depth=3,
                learning_rate=0.03,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42
            )
        else:
            if use_xgboost:
                print("⚠️ [WARNING] XGBoost package not found. Falling back to Random Forest Optimization.")
            self.model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
            
        self.df_raw = None
        self.future_data = None
        self.ward_name_map = {}
        self.available_wards = []
        
        # Calibrated bounding limits & downstream shrinkage metrics
        self.lower_bound = -23.0
        self.upper_bound = 15.0
        self.delta_shrink_factor = 0.85
        
        # Storage slots for SHAP execution
        self.X_train_features = None  
        self.explainer = None
        self.shap_values = None

        # Optional council filter for targeted views; None means all councils.
        self.cc_code = "E10000020"

    def tune_hyperparameters(self):
        """
        Executes a 5-fold cross-validation GridSearch to find the optimal 
        XGBoost hyperparameters that minimize RMSE on historical training data.
        """
        if self.df_raw is None:
            self.extract_and_prepare_data()

        # Ensure party_label exists prior to feature matrix generation
        self.df_raw['party_label'] = self.df_raw['party_name']
        df_encoded = pd.get_dummies(self.df_raw, columns=['party_name'], drop_first=False)

        historical_data = df_encoded[df_encoded['election_year'] < 2026].copy()
        historical_data = historical_data.dropna(subset=['diff_vote_share'] + self.census_features)

        # Build columns_to_drop safely by filtering only existing columns
        candidate_drops = [
            'party_vote_share', 'prior_vote_share', 'current_ward_rank', 'prior_ward_rank',
            'diff_vote_share', 'election_year', 'wd_code', 'cc_code', 'party_label', 
            'candidate_id', 'candidate_name'
        ]
        columns_to_drop = [col for col in candidate_drops if col in historical_data.columns]
        
        X_train = historical_data.drop(columns=columns_to_drop).astype(float)
        y_train = historical_data['diff_vote_share']

        print("\n🔍 STARTING AUTOMATED HYPERPARAMETER TUNING (GridSearchCV)...")
        
        # Focused search grid targeting tree depth and regularization
        param_grid = {
            'n_estimators': [150, 300, 450],
            'max_depth': [2, 3, 4],
            'learning_rate': [0.01, 0.03, 0.05],
            'subsample': [0.7, 0.8],
            'colsample_bytree': [0.7, 0.8],
            'reg_alpha': [0.0, 0.1],
            'reg_lambda': [0.5, 1.0]
        }

        xgb_base = XGBRegressor(random_state=42)

        grid_search = GridSearchCV(
            estimator=xgb_base,
            param_grid=param_grid,
            scoring='neg_root_mean_squared_error',
            cv=5,
            verbose=1,
            n_jobs=-1
        )

        grid_search.fit(X_train, y_train)

        print("\n====================================================")
        print("🏆 OPTIMAL HYPERPARAMETERS FOUND")
        print("====================================================")
        for param, val in grid_search.best_params_.items():
            print(f"  • {param:<20}: {val}")
        print(f"  • Best 5-Fold CV RMSE: {-grid_search.best_score_:.4f}%")
        print("====================================================\n")

        # Dynamically assign winning estimator to active model
        self.model = grid_search.best_estimator_
        return grid_search.best_params_

    def get_summary(self, cc_code=None) -> pd.DataFrame:
        """
        UI Contract Layer: Dynamically calculates actual current seats vs. 
        2026 machine learning plurality projections.
        """
        if self.future_data is None or self.future_data.empty:
            return pd.DataFrame(columns=["party", "seats_forecast", "seats_current", "seat_difference"])

        target_cc_code = cc_code if cc_code is not None else None
        if target_cc_code:
            target_future = self.future_data[self.future_data['cc_code'] == target_cc_code].copy()
        else:
            target_future = self.future_data.copy()

        if target_future.empty:
            return pd.DataFrame(columns=["party", "seats_forecast", "seats_current", "seat_difference"])
        
        # Extract live predicted winners per division boundary
        idx_pred_winners = target_future.groupby('wd_code')['final_forecast_share'].idxmax()
        pred_winners = target_future.loc[idx_pred_winners, 'party_label'].value_counts()
        
        # Extract baseline current winners using maximum starting party vote shares
        idx_curr_winners = target_future.groupby('wd_code')['party_vote_share'].idxmax()
        curr_winners = target_future.loc[idx_curr_winners, 'party_label'].value_counts()
        
        # Merge data metrics into a structured summary table matching the GUI schema
        all_parties = sorted(list(set(pred_winners.index) | set(curr_winners.index)))
        summary_rows = []
        
        for party in all_parties:
            forecasted = int(pred_winners.get(party, 0))
            current = int(curr_winners.get(party, 0))
            diff = forecasted - current
            summary_rows.append({
                "party": party,
                "seats_forecast": forecasted,
                "seats_current": current,
                "seat_difference": f"+{diff}" if diff > 0 else str(diff)
            })
            
        return pd.DataFrame(summary_rows)

    def map_ideology(self, party_name):
        """Maps categorical party text to a continuous scale (-1.0 Left to +1.0 Right)."""
        mapping = {
            'Conservative': 0.6,
            'Reform UK': 0.75,
            'Labour': -0.36,
            'Green Party': -0.55,
            'Liberal Democrats': -0.23,
            'Communist Party of Britain': -1.0,
            'Independent': 0.0,
            'Restore Britain': 1.0,
        }
        return mapping.get(party_name, 0.0)

    def calculate_prior_top2_margin(self, group):
        """Calculates the distance between 1st and 2nd place in the previous cycle."""
        group = group.sort_values(by=['election_year', 'party_vote_share'], ascending=[True, False])
        unique_years = sorted(group['election_year'].unique())
        margin_mapping = {}
        
        for i, year in enumerate(unique_years):
            if i == 0:
                margin_mapping[year] = np.nan
                continue
            prior_year = unique_years[i - 1]
            prior_data = group[group['election_year'] == prior_year]
            if len(prior_data) >= 2:
                shares = prior_data['party_vote_share'].values
                margin_mapping[year] = shares[0] - shares[1]
            else:
                margin_mapping[year] = np.nan
                
        group['top_2'] = group['election_year'].map(margin_mapping)
        return group

    def extract_and_prepare_data(self):
        """Queries database and executes advanced custom pandas preprocessing loops."""
        print("🚀 Extracting demographics and base party results matrices...")
        try:
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

            query = """
                SELECT 
                    er.wd_code, ew.cc_code AS cc_code, cand.registered_party AS party_name, cand.candidate_name,
                    er.election_year, er.candidate_id, AVG(er.vote_share) AS party_vote_share, 
                    MAX(er.is_incumbent_cllr) AS has_incumbent_boost,
                    AVG(er.{poll_col}) AS national_poll_share,
                    (SUM(c.oa_pop) / SUM(c.oa_pop / NULLIF(c.pop_den, 0))) AS ward_population_density,
                    AVG(c.pct_student) AS pct_student, AVG(c.pct_own_hme) AS pct_own_hme, AVG(c.pct_rent) AS pct_rent, 
                    AVG(c.pct_age_18_29) AS pct_age_18_29, AVG(c.pct_age_30_65) AS pct_age_30_65, 
                    AVG(c.pct_age_over_65) AS pct_age_over_65, AVG(c.pct_wk_class) AS pct_wk_class, 
                    AVG(c.pct_mid_class) AS pct_mid_class, AVG(c.pct_bch) AS pct_bch, 
                    AVG(c.pct_female) AS pct_female, AVG(c.pct_male) AS pct_male
                FROM election_results er
                JOIN candidates cand ON er.candidate_id = cand.candidate_id
                LEFT JOIN electoral_wards ew ON er.wd_code = ew.wd_code
                LEFT JOIN geographic_lookup gl ON er.wd_code = gl.wd_code
                LEFT JOIN census c ON gl.oa_code = c.oa_code
                WHERE er.is_uncontested = 0
                GROUP BY er.wd_code, ew.cc_code, cand.registered_party, cand.candidate_name, er.election_year, er.candidate_id;
            """.format(poll_col=poll_col)
            self.df_raw = pd.read_sql(query, con=self.engine)

            try:
                ward_name_query = """
                    SELECT wd_code, ward_name
                    FROM electoral_wards
                    UNION ALL
                    SELECT wd_code, ward_name
                    FROM electoral_wards_history
                """
                df_wards = pd.read_sql(ward_name_query, con=self.engine)
            except Exception:
                df_wards = pd.read_sql("SELECT wd_code, ward_name FROM electoral_wards;", con=self.engine)

            df_wards['wd_code'] = df_wards['wd_code'].astype(str)
            df_wards['ward_name'] = df_wards['ward_name'].astype(str)
            df_wards = (
                df_wards[df_wards['ward_name'].str.strip() != ""]
                .drop_duplicates(subset=['wd_code'], keep='first')
            )
            self.ward_name_map = dict(zip(df_wards['wd_code'], df_wards['ward_name']))
        except Exception as e:
            print(f"❌ Database query operation failed: {e}")
            raise

        print("📈 Processing localized historical party baseline frameworks...")
        historical_averages = (
            self.df_raw[self.df_raw['election_year'] < 2026]
            .groupby(['wd_code', 'party_name'], group_keys=False)['party_vote_share']
            .mean().reset_index().rename(columns={'party_vote_share': 'historical_party_ward_mean'})
        )
        self.df_raw = pd.merge(self.df_raw, historical_averages, on=['wd_code', 'party_name'], how='left')
        self.df_raw['historical_party_ward_mean'] = self.df_raw['historical_party_ward_mean'].fillna(15.0)

        self.df_raw['candidate_personal_historical_mean'] = self.df_raw['party_vote_share']

        print("🛠️ Generating tactical voting features downstream via vector loops...")
        
        # 1. Ideological continuous index map (-1.0 to 1.0)
        self.df_raw['left_right'] = self.df_raw['party_name'].apply(self.map_ideology)
        
        # 2. Chronological sort for rank calculation and shift execution
        self.df_raw = self.df_raw.sort_values(by=['wd_code', 'party_name', 'election_year'])
        
        # 3. Dynamic row-level ranking function within cycles
        self.df_raw['current_ward_rank'] = self.df_raw.groupby(['wd_code', 'election_year'], group_keys=False)['party_vote_share'].rank(ascending=False, method='min')
        
        # 4. Generate prior-cycle shifted attributes
        self.df_raw['prior_vote_share'] = self.df_raw.groupby(['wd_code', 'party_name'], group_keys=False)['party_vote_share'].shift(1)
        self.df_raw['prior_ward_rank'] = self.df_raw.groupby(['wd_code', 'party_name'], group_keys=False)['current_ward_rank'].shift(1)
        
        # 5. Define target shift variable (y = Δ change in vote share)
        self.df_raw['diff_vote_share'] = self.df_raw['party_vote_share'] - self.df_raw['prior_vote_share']
        
        # 6. Binary flag mapping for tactical wasted vote compression
        self.df_raw['wasted_vote'] = np.where(
            (self.df_raw['prior_ward_rank'] >= 3) & (self.df_raw['prior_vote_share'] < 15.0), 1, 0
        )
        
        # 7. Multi-candidate top_2 margin execution
        ward_groups = []
        for wd_code, group in self.df_raw.groupby('wd_code', sort=False):
            processed_group = self.calculate_prior_top2_margin(group)
            processed_group = processed_group.copy()
            processed_group['wd_code'] = wd_code
            ward_groups.append(processed_group)
        self.df_raw = pd.concat(ward_groups, ignore_index=True)
        
        # Complete missing initial metrics by mapping broad local footprints
        self.df_raw['top_2'] = self.df_raw['top_2'].fillna(15.0)

    def train_and_evaluate(self):
        """Executes delta-target training and registers verification metrics."""
        if 'wd_code' not in self.df_raw.columns:
            index_names = [name for name in getattr(self.df_raw.index, 'names', []) if name]
            if 'wd_code' in index_names or self.df_raw.index.name == 'wd_code':
                self.df_raw = self.df_raw.reset_index()
            else:
                raise KeyError("Missing required column 'wd_code' after preprocessing.")

        self.df_raw['party_label'] = self.df_raw['party_name']
        df_encoded = pd.get_dummies(self.df_raw, columns=['party_name'], drop_first=False)

        historical_data = df_encoded[df_encoded['election_year'] < 2026].copy()
        self.future_data = df_encoded[df_encoded['election_year'] == 2026].copy()

        historical_data = historical_data.dropna(subset=['diff_vote_share'] + self.census_features)
        self.available_wards = sorted(self.future_data['wd_code'].unique())

        print("*************** TRUE SURGE PROJECTION PIPELINE ***************")
        print(f"📈 Active Training Matrix: {len(historical_data):,} records.")
        
        columns_to_drop = [
            'party_vote_share', 'prior_vote_share', 'current_ward_rank', 'prior_ward_rank',
            'diff_vote_share', 'election_year', 'wd_code', 'cc_code', 'party_label', 
            'candidate_id', 'candidate_name'
        ]
        
        X_train = historical_data.drop(columns=[col for col in columns_to_drop if col in historical_data.columns]).astype(float)
        y_train = historical_data['diff_vote_share'] 
        X_future = self.future_data.drop(columns=[col for col in columns_to_drop if col in self.future_data.columns]).astype(float)

        # Preserve exact training feature names matrix for SHAP
        self.X_train_features = X_train

        # 80/20 Train-Test Partition
        X_tr, X_te, y_tr, y_te = train_test_split(X_train, y_train, test_size=0.2, random_state=42)
        
        # 1. Train Linear Baseline (Control Group for H1)
        linear_model = LinearRegression()
        linear_model.fit(X_tr, y_tr)
        y_pred_linear = linear_model.predict(X_te)
        
        linear_rmse = np.sqrt(mean_squared_error(y_te, y_pred_linear))
        linear_r2 = r2_score(y_te, y_pred_linear)

        # 2. Train Non-Linear Ensemble
        self.model.fit(X_tr, y_tr)
        y_pred_ensemble = self.model.predict(X_te)
        
        ensemble_rmse = np.sqrt(mean_squared_error(y_te, y_pred_ensemble))
        ensemble_r2 = r2_score(y_te, y_pred_ensemble)

        # 3. Comparative Logging Output
        print("\n====================================================")
        print("📈 HISTORICAL BACKTESTING PERFORMANCE COMPARISON")
        print("====================================================")
        print(f"🔹 Linear Baseline (Linear Regression):")
        print(f"   - RMSE: {linear_rmse:.2f}%")
        print(f"   - R² Score: {linear_r2:.4f} ({linear_r2*100:.2f}% variance explained)")
        print("-" * 52)
        print(f"🚀 Non-Linear Ensemble ({self.model.__class__.__name__}):")
        print(f"   - RMSE: {ensemble_rmse:.2f}%")
        print(f"   - R² Score: {ensemble_r2:.4f} ({ensemble_r2*100:.2f}% variance explained)")
        print("====================================================\n")

        # Train model on full context framework to forecast 2026 slots
        self.model.fit(X_train, y_train)
        
        print("🔮 Initializing TreeExplainer for SHAP...")
        self.explainer = shap.TreeExplainer(self.model)

        # Apply forecast extrapolations to target dataframe
        self.future_data['predicted_delta'] = self.model.predict(X_future)
        self.future_data['predicted_delta_bounded'] = self.future_data['predicted_delta'].clip(
            lower=self.lower_bound, upper=self.upper_bound
        )
        self.future_data['predicted_delta_adjusted'] = (
            self.future_data['predicted_delta_bounded'] * self.delta_shrink_factor
        )
        self.future_data['predicted_party_share_unclipped'] = (
            self.future_data['party_vote_share'] + self.future_data['predicted_delta_adjusted']
        )
        self.future_data['predicted_party_share'] = self.future_data['predicted_party_share_unclipped'].clip(0.0, 100.0)
        self.future_data['final_forecast_share'] = self.future_data['predicted_party_share']

    def generate_shap_analysis(self, primary_interaction_feature: str = "top_2"):
        """Calculates TreeSHAP values path-dependently and outputs diagnostic plots."""
        if self.X_train_features is None:
            raise RuntimeError("⚠️ Model must be trained before generating SHAP analysis.")
        
        print("\n🔮 Computing SHAP values via Path-Dependent TreeExplainer Model...")
        
        self.explainer = shap.TreeExplainer(
            self.model,
            feature_perturbation="tree_path_dependent"
        )
        raw_shap_values = self.explainer.shap_values(self.X_train_features)
        
        self.shap_values = shap.Explanation(
            values=raw_shap_values,
            base_values=self.explainer.expected_value,
            data=self.X_train_features.values,
            feature_names=self.X_train_features.columns
        )
        
        # Plot 1: Modern Global Feature Importance Bar Plot
        shap.plots.bar(self.shap_values, show=False)
        plt.title("SHAP Global Feature Importance\n(Mean Absolute Impact on Δ Vote Share)", fontsize=12, pad=15)
        fig1 = plt.gcf()
        fig1.set_size_inches(10, 5)
        plt.tight_layout()

        # Plot 2: Dependence Scatter Plot
        if primary_interaction_feature in self.X_train_features.columns:
            shap.plots.scatter(self.shap_values[:, primary_interaction_feature], color=self.shap_values, show=False)
            plt.title(f"Δ Target Dependence Scatter: '{primary_interaction_feature}' Feature Scaling & Interaction", fontsize=12, pad=15)
            plt.ylabel(f"SHAP Value for {primary_interaction_feature} (Δ Vote Share Impact)")
            plt.grid(True, alpha=0.25)
            
            fig2 = plt.gcf()
            fig2.set_size_inches(10, 6)
            plt.tight_layout()
            plt.show()
        else:
            print(f"⚠️ Skipping dependence plot: '{primary_interaction_feature}' not found in training dataset features.")
            plt.show()

    def verify_winners_loop(self):
        """Winner Verification Loop for Norfolk CC."""
        if self.future_data is None or self.future_data.empty:
            print("⚠️ No prediction data found for winner verification.")
            return

        print("\n====================================================")
        print("👑 WINNER VERIFICATION METRIC MATRIX (NORFOLK 2026)")
        print("====================================================")
        
        norfolk_future = self.future_data[self.future_data['cc_code'] == self.cc_code]
        if norfolk_future.empty:
            norfolk_future = self.future_data 

        idx_winners = norfolk_future.groupby('wd_code')['final_forecast_share'].idxmax()
        winners_df = norfolk_future.loc[idx_winners]
        
        seat_counts = winners_df['party_label'].value_counts()
        total_seats = seat_counts.sum()
        
        print(f"Total Unique Divisions/Wards Calculated: {total_seats}")
        print("-" * 52)
        print(f"{'Party Name':<30} | {'Seats Won':>10}")
        print("-" * 52)
        for party, seats in seat_counts.items():
            print(f"{party:<30} | {seats:>10}")
        print("====================================================\n")

    @property
    def forecast(self):
        """GUI Data Contract Compatibility Layer."""
        if self.future_data is None:
            return pd.DataFrame()
        forecast_df = self.future_data.copy()
        forecast_df['ward_name'] = forecast_df['wd_code'].map(self.ward_name_map)
        return forecast_df


# Dynamic Map Engine Imports
import geopandas as gpd
from MapOrchestrator import MapOrchestrator

def _resolve_division_boundary_path(project_root: Path) -> Path:
    """Resolve an England-wide divisions layer first, then fall back safely."""
    data_root = project_root / "data"

    for year in ("2026", "2025"):
        official_candidate = (
            data_root
            / f"County Electoral Division (May {year}) Boundaries EN BFE"
            / f"CED_MAY_{year}_EN_BFC.shp"
        )
        if official_candidate.is_file():
            print(f"[MAP ENGINE] Using official England-wide CED boundary layer: {official_candidate.name}")
            return official_candidate

    all_shapefiles = list(data_root.rglob("*.shp"))
    england_candidates = []
    for path in all_shapefiles:
        path_lower = str(path).lower()
        name_lower = path.name.lower()
        if "england" in path_lower and any(tok in name_lower for tok in ["ced", "division", "county"]):
            england_candidates.append(path)
    if england_candidates:
        chosen = sorted(england_candidates)[0]
        print(f"[MAP ENGINE] Fallback to England-wide discovered layer: {chosen.name}")
        return chosen

    for path in all_shapefiles:
        if "ced" in path.name.lower():
            print(f"[MAP ENGINE] Fallback to generic CED layer: {path.name}")
            return path

    return project_root / "county_divisions.geojson"


boundary_path = _resolve_division_boundary_path(Path(__file__).parent)
map_orchestrator = MapOrchestrator(boundary_path)


def get_ward_shap_explanation(ward_name_input, forecaster_instance, orchestrator, feature_to_plot):
    print(f"*******🔍 Generating SHAP explanation for: {ward_name_input}********")
    gdf = orchestrator.gdf 
    
    def normalize(s):
        import re
        s = str(s).lower().replace("&", "and")
        s = re.sub(r'\s+ed\b', '', s)
        return re.sub(r'[^a-z0-9]', '', s)
    
    gdf['norm_name'] = gdf['Name'].apply(normalize)
    normalized_map = {normalize(name): code for code, name in forecaster_instance.ward_name_map.items()}
    target_norm = normalize(ward_name_input)
    matched_code = normalized_map.get(target_norm)
            
    if not matched_code:
        print(f"❌ ERROR: Could not find '{ward_name_input}' (norm: {target_norm}) in forecast data.")
        return None
        
    ward_rows = forecaster_instance.future_data[
        forecaster_instance.future_data['wd_code'].astype(str) == matched_code
    ].copy()

    ward_features = ward_rows[forecaster_instance.X_train_features.columns]
    shap_results = forecaster_instance.explainer.shap_values(ward_features.astype(float))
    shap_values = shap_results[0] if isinstance(shap_results, list) else shap_results
    if shap_values.ndim > 1: shap_values = shap_values.flatten()
    training_cols = forecaster_instance.X_train_features.columns
    shap_dict = dict(zip(training_cols, shap_values))
    
    ward_geo = gdf[gdf['norm_name'] == target_norm].copy()
    
    for feat, val in shap_dict.items():
        if feat == feature_to_plot:
            ward_geo[f'shap_{feat}'] = val
        
    return ward_geo


def interactive_forecast_lookup(forecaster):
    """Simple CLI loop to inspect forecast outputs by ward code."""
    if forecaster.future_data is None or forecaster.future_data.empty:
        print("⚠️ No forecast data available. Run training first.")
        return

    available_codes = set(forecaster.future_data['wd_code'].astype(str))

    print("\n====================================================")
    print("🔍 INTERACTIVE FORECAST LOOKUP")
    print("====================================================")

    while True:
        user_input = input("\nEnter a ward code (e.g., E05004023) or type 'exit':\n👉 ").strip()
        if user_input.lower() == 'exit':
            print("Goodbye!")
            break

        ward_code = user_input.upper()

        if ward_code not in available_codes:
            query = user_input.casefold()
            name_matches = []
            for code, name in forecaster.ward_name_map.items():
                if code not in available_codes:
                    continue
                if query in str(name).casefold():
                    name_matches.append((code, name))

            if not name_matches:
                print(f"❌ No ward match found for '{user_input}'. Try a ward code or name.")
                continue

            name_matches = sorted(name_matches, key=lambda item: str(item[1]))
            if len(name_matches) == 1:
                ward_code = name_matches[0][0]
            else:
                print(f"\nFound {len(name_matches)} matches:")
                preview = name_matches[:10]
                for idx, (code, name) in enumerate(preview, start=1):
                    print(f"  {idx}. {name} ({code})")

                selection = input("Select a number, type a ward code, or press Enter to cancel:\n👉 ").strip()
                if not selection:
                    continue

                if selection.isdigit():
                    choice_idx = int(selection) - 1
                    if 0 <= choice_idx < len(preview):
                        ward_code = preview[choice_idx][0]
                    else:
                        print("❌ Invalid selection number.")
                        continue
                else:
                    candidate_code = selection.upper()
                    if candidate_code in available_codes:
                        ward_code = candidate_code
                    else:
                        print(f"❌ '{selection}' is not a valid ward code.")
                        continue

        ward_rows = forecaster.future_data[forecaster.future_data['wd_code'] == ward_code].copy()
        if ward_rows.empty:
            print(f"❌ Ward code '{ward_code}' not found in 2026 forecast slots.")
            continue

        ward_rows = ward_rows.sort_values('final_forecast_share', ascending=False)
        total_share = ward_rows['final_forecast_share'].sum()
        ward_rows['normalized_share'] = (ward_rows['final_forecast_share'] / total_share * 100.0) if total_share > 0 else 0.0

        ward_name = forecaster.ward_name_map.get(ward_code, "Unknown Ward")
        print(f"\n🔮 Forecast for {ward_name} ({ward_code})")
        print(f"{'Party':<35} | {'Projected %':>12} | {'Clipped %':>10} | {'Normalized %':>12}")
        print("-" * 79)

        for _, row in ward_rows.iterrows():
            print(
                f"{str(row['party_label']):<35} | "
                f"{float(row['predicted_party_share_unclipped']):>12.4f} | "
                f"{float(row['final_forecast_share']):>10.2f} | "
                f"{float(row['normalized_share']):>12.2f}"
            )


# =========================================================================
# Single Main Orchestration Block
# =========================================================================
if __name__ == "__main__":
    ward_code = "Gaywood North & Central ED"
    features_to_plot = ['wasted_vote', 'candidate_personal_historical_mean']
    
    # 1. Initialize forecasting pipeline
    forecaster = Forecaster(use_xgboost=True)
    forecaster.extract_and_prepare_data()
    
    # 2. Run 5-fold cross-validation grid search to optimize XGBoost
    best_params = forecaster.tune_hyperparameters()
    
    # 3. Train tuned model and log performance metrics vs Linear Baseline
    forecaster.train_and_evaluate()
    
    # 4. Generate SHAP visual maps for thesis figures
    for feat in features_to_plot:
        gdf_with_shap = get_ward_shap_explanation(ward_code, forecaster, map_orchestrator, feat)
        
        if gdf_with_shap is not None:
            fig, ax = plt.subplots(figsize=(8, 6))
            gdf_with_shap.plot(
                column=f'shap_{feat}', 
                cmap='coolwarm', 
                legend=True, 
                ax=ax,
                legend_kwds={'label': f"SHAP Impact: {feat}"}
            )
            ax.set_title(f"Figure: SHAP Spatial Impact of\n{feat}")
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            
            plt.savefig(f"Figure_{feat}.png", dpi=300)
            print(f"✅ Saved visualization: Figure_{feat}.png")
            plt.show()
            
    # 5. Launch CLI forecast lookup
    interactive_forecast_lookup(forecaster)