"""One-off MySQL -> PostgreSQL data copy for irp_election_forecasting.

Copies every table in schema_postgres.sql from the existing MySQL database into the
newly created PostgreSQL database, in dependency order, converting MySQL tinyint(1)
columns to real booleans so PostgreSQL's BOOLEAN columns accept them.
"""

import os
from sqlalchemy import create_engine
import pandas as pd

MYSQL_URL = (
    f"mysql+pymysql://{os.environ['MYSQL_USER']}:{os.environ['MYSQL_PASSWORD']}"
    f"@{os.environ['MYSQL_HOST']}:{os.environ['MYSQL_PORT']}/irp_election_forecasting"
)
POSTGRES_URL = "postgresql+psycopg2://postgres@127.0.0.1:5432/irp_election_forecasting"

# (table, boolean_columns) in FK-safe insert order.
# Only geographic_lookup remains: every earlier table already matches MySQL's row count.
TABLES = [
    ("geographic_lookup", []),
]

CHUNK_SIZE = 5000


def copy_table(mysql_engine, postgres_engine, table: str, bool_columns: list[str]) -> int:
    total_rows = 0
    for chunk in pd.read_sql_table(table, mysql_engine, chunksize=CHUNK_SIZE):
        for column in bool_columns:
            if column in chunk.columns:
                chunk[column] = chunk[column].astype("Int64").astype("boolean")
        chunk.to_sql(table, postgres_engine, if_exists="append", index=False, method="multi", chunksize=1000)
        total_rows += len(chunk)
    return total_rows


def main() -> None:
    mysql_engine = create_engine(MYSQL_URL)
    postgres_engine = create_engine(POSTGRES_URL)

    for table, bool_columns in TABLES:
        copied = copy_table(mysql_engine, postgres_engine, table, bool_columns)
        print(f"{table}: copied {copied:,} rows")


if __name__ == "__main__":
    main()
