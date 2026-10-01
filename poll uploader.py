import pandas as pd
from sqlalchemy import create_engine
import os

def upload_daily_polls():
    postgres_config = {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "database": os.getenv("POSTGRES_DB", "irp_election_forecasting"),
    }
    engine = create_engine(
        f"postgresql+psycopg2://{postgres_config['user']}:{postgres_config['password']}@"
        f"{postgres_config['host']}:{postgres_config['port']}/{postgres_config['database']}"
    )

    # Load your smoothed daily polls CSV file
    df = pd.read_csv("smoothed_national_polls.csv")
    
    # Rename columns to match database schema if needed
    # Assuming columns like poll_date, Lab, Con, etc.
    rename_map = {
        "poll_date": "poll_date",
        "Lab": "labour",
        "Con": "conservative",
        "Ref": "reform_uk",
        "LD": "liberal_democrats",
        "Grn": "green_party",
        "RB": "restore_britain",
        "Others": "others"
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    df.to_sql("national_polls", engine, if_exists="replace", index=False)
    print(f"Successfully uploaded {len(df):,} daily poll records to PostgreSQL.")

if __name__ == "__main__":
    upload_daily_polls()