# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the automated logic for finding the polling data used in the election forecast.

import pandas as pd
import requests
from io import StringIO
from pathlib import Path
import re

class PollFetcher:
    def __init__(self):
        self.latest_polls = None

    def update_latest_polls(self):
        self.latest_polls = self.fetch_latest_polls()

    def cleaned_latest_polls(self):
        if self.latest_polls is None:
            csv_path = Path(__file__).parent / "latest_polls.csv"
            if csv_path.is_file():
                self.latest_polls = pd.read_csv(csv_path)
            else:
                raise RuntimeError("No latest polls available and no local cache found.")
        return self.clean_and_smooth_polls(self.latest_polls)

    @staticmethod
    def fetch_latest_polls():
        url = "https://en.wikipedia.org/wiki/Opinion_polling_for_the_next_United_Kingdom_general_election"
        headers = {
            "User-Agent": "LocalElectionForecaster/1.0 (Educational Desktop App; contact@ianmilburn.dev) Python-requests"
        }
        
        print(f"[POLL FINDER] Requesting page from Wikipedia...")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                tables = pd.read_html(StringIO(response.text))
                recent_polls = tables[1] 
                print("[POLL FINDER] Successfully parsed live polling table!")
                
                csv_path = Path(__file__).parent / "latest_polls.csv"
                recent_polls.to_csv(csv_path, index=False)
                return recent_polls
        except Exception as e:
            print(f"[POLL FINDER] Live fetch encountered an issue: {e}")

        print("[POLL FINDER] Falling back to local 'latest_polls.csv' cache...")
        csv_path = Path(__file__).parent / "latest_polls.csv"
        if csv_path.is_file():
            return pd.read_csv(csv_path)
        else:
            raise RuntimeError("Live fetching failed and no local 'latest_polls.csv' file exists.")

    def clean_and_smooth_polls(self, latest_polls):
        df = latest_polls.copy()
        
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(str(col).strip() for col in tup if 'Unnamed' not in str(col)) for tup in df.columns]
        
        if len(df.columns) >= 15:
            df.columns = [
                "dates_conducted", "pollster", "client", "area", "sample_size",
                "Lab", "Con", "Ref", "LD", "Grn", "SNP", "PC", "RB", "Others", "Lead"
            ] + list(df.columns[15:])
        
        if "dates_conducted" in df.columns and "Lab" in df.columns:
            df = df.dropna(subset=["dates_conducted", "Lab"])
            
        # Clean percentage strings to numeric floats
        party_cols = [col for col in ["Lab", "Con", "Ref", "LD", "Grn", "SNP", "PC", "RB", "Others"] if col in df.columns]
        for col in party_cols:
            df[col] = df[col].astype(str).str.replace("%", "", regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            
        # England-Only Scope Adjustment: Fold regional parties (SNP, PC) into "Others"
        regional_parties = [p for p in ["SNP", "PC"] if p in df.columns]
        if regional_parties and "Others" in df.columns:
            df["Others"] = df["Others"] + df[regional_parties].sum(axis=1)
            df = df.drop(columns=regional_parties)
            
        print(f"Successfully cleaned and scoped {len(df):,} poll records for England.")
        
        # Safe CSV export with permission error catch
        csv_path = Path(__file__).parent / "cleaned_latest_polls.csv"
        try:
            df.to_csv(csv_path, index=False)
        except PermissionError:
            print(f"[WARNING] Could not overwrite {csv_path.name}. Please close it if it's open in Excel.")
            
        return df

    def process_polls_for_database(self, latest_polls):
        df = latest_polls.copy()
        
        # Ensure sample size is numeric
        if "sample_size" in df.columns:
            df["sample_size"] = pd.to_numeric(
                df["sample_size"].astype(str).str.replace(",", "", regex=False), 
                errors="coerce"
            ).fillna(1000)
        else:
            df["sample_size"] = 1000

        active_parties = [col for col in ["Lab", "Con", "Ref", "LD", "Grn", "RB", "Others"] if col in df.columns]
        
        # Clean dates by removing citation brackets like [2] and parsing end dates
        def extract_end_date(text):
            cleaned_text = re.sub(r'\[.*?\]', '', str(text))
            date_part = cleaned_text.split("–")[-1].strip()
            return f"{date_part} 2026"

        df["poll_date"] = pd.to_datetime(df["dates_conducted"].apply(extract_end_date), errors="coerce")
        df = df.dropna(subset=["poll_date"])
        
        # Calculate Sample-Size Weighted Mean per Exact Date
        weighted_records = []
        for date, group in df.groupby("poll_date"):
            total_weight = group["sample_size"].sum()
            if total_weight == 0:
                continue
            
            row = {"poll_date": date.strftime("%Y-%m-%d")}
            for col in active_parties:
                weighted_avg = (group[col] * group["sample_size"]).sum() / total_weight
                row[col] = round(weighted_avg, 2)
            weighted_records.append(row)
            
        daily_aggregated = pd.DataFrame(weighted_records).sort_values("poll_date")
        
        if daily_aggregated.empty:
            print("[WARNING] No valid daily aggregated poll records found.")
            return daily_aggregated

        # Apply a 7-Day Rolling Average (Weekly Smoothing)
        daily_aggregated["poll_date"] = pd.to_datetime(daily_aggregated["poll_date"])
        daily_aggregated = daily_aggregated.set_index("poll_date")
        
        smoothed_weekly = daily_aggregated.resample("D").mean().interpolate(method="linear").rolling(window=7, min_periods=1).mean().reset_index()
        smoothed_weekly["poll_date"] = smoothed_weekly["poll_date"].dt.strftime("%Y-%m-%d")
        
        print(f"Generated {len(smoothed_weekly):,} smoothed timeline records ready for database storage.")
        
        # Safe export for smoothed CSV
        csv_path = Path(__file__).parent / "smoothed_national_polls.csv"
        try:
            smoothed_weekly.to_csv(csv_path, index=False)
        except PermissionError:
            print(f"[WARNING] Could not overwrite {csv_path.name}. Please close it if open in Excel.")
            
        return smoothed_weekly
    
if __name__ == "__main__":
    pf = PollFetcher()
    pf.update_latest_polls()
    latest_polls = pf.cleaned_latest_polls()
    smoothed_polls = pf.process_polls_for_database(latest_polls)
    print("Polling pipeline completed successfully!")