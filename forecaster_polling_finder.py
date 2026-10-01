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
from datetime import date

from forecaster_data import get_database


_POLL_TABLE_REQUIRED_COLUMNS = {
    "datesconducted",
    "pollster",
    "area",
    "samplesize",
    "lab",
    "con",
}


def _flatten_poll_columns(columns) -> list[str]:
    return [
        str(column[0] if isinstance(column, tuple) else column).strip()
        for column in columns
    ]


def _is_annual_poll_table(table: pd.DataFrame) -> bool:
    normalized = {
        re.sub(r"[^a-z0-9]", "", column.casefold())
        for column in _flatten_poll_columns(table.columns)
    }
    return _POLL_TABLE_REQUIRED_COLUMNS.issubset(normalized)


def _extract_poll_end_date(dates_conducted: str, poll_year: int) -> str:
    date_text = re.sub(r"\[.*?\]", "", str(dates_conducted)).strip()
    date_text = re.sub(r"[–—−�]", "-", date_text)
    date_part = re.split(r"\s*-\s*", date_text)[-1].strip()
    explicit_year = re.search(r"\b20\d{2}\b", date_part)
    if explicit_year:
        return date_part
    year = int(poll_year)
    return f"{date_part} {year}"


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
                current_year = date.today().year
                annual_tables = [
                    table for table in tables if _is_annual_poll_table(table)
                ]
                years = range(current_year, 2023, -1)
                annual_polls = []
                for year, table in zip(years, annual_tables):
                    annual_table = table.copy()
                    annual_table.columns = _flatten_poll_columns(table.columns)
                    annual_polls.append(annual_table.assign(poll_year=year))

                if not annual_polls:
                    raise ValueError("No annual national polling tables were found.")
                recent_polls = pd.concat(
                    annual_polls,
                    ignore_index=True,
                    sort=False,
                )
                covered_years = list(recent_polls["poll_year"].drop_duplicates())
                print(
                    "[POLL FINDER] Parsed annual polling tables for "
                    + ", ".join(map(str, covered_years))
                    + "."
                )
                
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
        
        df.columns = _flatten_poll_columns(df.columns)
        column_names = {
            "datesconducted": "dates_conducted",
            "dateconducted": "dates_conducted",
            "samplesize": "sample_size",
        }
        df = df.rename(
            columns={
                column: column_names.get(
                    re.sub(r"[^a-z0-9]", "", column.casefold()), column
                )
                for column in df.columns
            }
        )
        
        if "dates_conducted" in df.columns and "Lab" in df.columns:
            df = df.dropna(subset=["dates_conducted", "Lab"])
            
        # Clean percentage strings to numeric floats
        party_cols = [col for col in ["Lab", "Con", "Ref", "LD", "Grn", "SNP", "PC", "RB", "Others"] if col in df.columns]
        for col in party_cols:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        for col in ["Lab", "Con", "Ref", "LD", "Grn", "RB", "Others"]:
            if col not in df.columns:
                df[col] = 0.0
            
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

        if "poll_year" not in df.columns:
            df["poll_year"] = date.today().year
        df["poll_year"] = pd.to_numeric(df["poll_year"], errors="coerce")
        df["poll_date"] = pd.to_datetime(
            df.apply(
                lambda poll: _extract_poll_end_date(
                    poll["dates_conducted"], poll["poll_year"]
                ),
                axis=1,
            ),
            errors="coerce",
        )
        df = df.dropna(subset=["poll_date"])

        # Filter to keep only polls from January 1, 2024 onwards
        df = df[df["poll_date"] >= pd.Timestamp("2024-01-01")]
        
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
        
        print(f"Generated {len(smoothed_weekly):,} smoothed timeline records from 2024 onwards ready for database storage.")
        
        # Safe export for smoothed CSV
        csv_path = Path(__file__).parent / "smoothed_national_polls.csv"
        try:
            smoothed_weekly.to_csv(csv_path, index=False)
        except PermissionError:
            print(f"[WARNING] Could not overwrite {csv_path.name}. Please close it if open in Excel.")
            
        return smoothed_weekly

    def upload_to_database(self, smoothed_polls: pd.DataFrame) -> int:
        """Replaces the national_polls table with the latest smoothed daily poll shares."""
        if smoothed_polls is None or smoothed_polls.empty:
            print("[POLL FINDER] No smoothed poll records to upload; skipping database write.")
            return 0

        rename_map = {
            "Lab": "labour",
            "Con": "conservative",
            "Ref": "reform_uk",
            "LD": "liberal_democrats",
            "Grn": "green_party",
            "RB": "restore_britain",
            "Others": "others",
        }
        df = smoothed_polls.rename(columns={k: v for k, v in rename_map.items() if k in smoothed_polls.columns})

        database = get_database()
        df.to_sql("national_polls", database.engine, if_exists="replace", index=False)
        print(f"[POLL FINDER] Uploaded {len(df):,} daily poll records to {type(database).__name__}.")
        return len(df)

    def run_pipeline(self) -> pd.DataFrame:
        """Fetches, cleans, smooths, and uploads the latest polls in one call."""
        self.update_latest_polls()
        latest_polls = self.cleaned_latest_polls()
        smoothed_polls = self.process_polls_for_database(latest_polls)
        self.upload_to_database(smoothed_polls)
        return smoothed_polls

if __name__ == "__main__":
    pf = PollFetcher()
    pf.run_pipeline()
    print("Polling pipeline completed successfully!")