from forecaster_data import get_database
from sqlalchemy import text
import pandas as pd

db = get_database()
with db.engine.connect() as conn:
    codes = conn.execute(text("SELECT DISTINCT wd_code FROM election_results")).fetchall()

codes_df = pd.DataFrame(codes, columns=["wd_code"])
codes_df["prefix"] = codes_df["wd_code"].astype(str).str.slice(0, 3)
print("wd_code prefix counts in election_results:")
print(codes_df["prefix"].value_counts())
print("\nSample E58 codes:", codes_df[codes_df["prefix"] == "E58"]["wd_code"].head(10).tolist())
print("Sample E05 codes:", codes_df[codes_df["prefix"] == "E05"]["wd_code"].head(10).tolist())
