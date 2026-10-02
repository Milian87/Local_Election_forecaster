# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the data management and database connection logic for the election forecaster application.
import os
import csv
import glob
import re

import pandas as pd
from sqlalchemy import create_engine, text

from forecaster_interfaces import Data_Uploader_Interface, iDatabaseInterface

class MySQLDatabase(iDatabaseInterface):
    def __init__(self, connection_string):
        self.db_config = connection_string or {
            'host': os.getenv('MYSQL_HOST'),
            'port': os.getenv('MYSQL_PORT', '3306'),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DB', 'irp_election_forecasting')
        }
        self.connection_string = connection_string
        self.connection = None

        self.engine = create_engine(
            f"mysql+pymysql://{self.db_config['user']}:{self.db_config['password']}@"
            f"{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        )
        
    def connect(self): 
        # Implement database connection logic here
        self.connection = self.engine.connect()
        print("Connected to MySQL database.")

    def disconnect(self):
        # Implement database disconnection logic here
        if self.connection:
            self.connection.close()
            self.connection = None
            print("Disconnected from MySQL database.")

    def fetch_dataframe(self, query: str) -> pd.DataFrame:
        # Implement logic to fetch data as a DataFrame
        if self.connection:
            return pd.read_sql(query, self.connection)
        else:
            raise ConnectionError("Database connection is not established.")

    def execute_many(self, statement: str, parameters: list[dict]) -> None:
        if not parameters:
            return
        with self.engine.begin() as connection:
            connection.execute(text(statement), parameters)

class PostgreSQLDatabase(iDatabaseInterface):
    def __init__(self, connection_string):
        self.db_config = connection_string or {
            'host': os.getenv('POSTGRES_HOST'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD'),
            'database': os.getenv('POSTGRES_DB')
        }
        self.connection_string = connection_string
        self.connection = None

        self.engine = create_engine(
            f"postgresql+psycopg2://{self.db_config['user']}:{self.db_config['password']}@"
            f"{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        )

    def connect(self):
        self.connection = self.engine.connect()
        print("Connected to PostgreSQL database.")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            print("Disconnected from PostgreSQL database.")

    def fetch_dataframe(self, query: str) -> pd.DataFrame:
        if self.connection:
            return pd.read_sql(query, self.connection)
        else:
            raise ConnectionError("Database connection is not established.")

    def execute_many(self, statement: str, parameters: list[dict]) -> None:
        if not parameters:
            return
        with self.engine.begin() as connection:
            connection.execute(text(statement), parameters)

def get_database(db_config=None) -> iDatabaseInterface:
    """Returns the app's configured database backend. Defaults to PostgreSQL;
    set DB_BACKEND=mysql to use MySQL instead."""
    backend = os.getenv("DB_BACKEND", "postgres").strip().lower()
    if backend == "mysql":
        return MySQLDatabase(db_config)
    return PostgreSQLDatabase(db_config)

class CSVDataUploader(Data_Uploader_Interface):
    def __init__(self, data_source: str):
        self.data_source = data_source
        self.data: pd.DataFrame | None = None

    def read_data(self) -> pd.DataFrame:
        # Implement CSV data loading logic here
        self.data = pd.read_csv(self.data_source)
        return self.data

    def preprocess_data(self) -> pd.DataFrame:
        # Implement data preprocessing logic here
        if self.data is None:
            raise ValueError("No CSV data has been loaded. Call read_data() first.")
        return self.data

    def send_data(self) -> pd.DataFrame:
        # Implement logic to send data to another destination
        if self.data is None:
            raise ValueError("No CSV data has been loaded. Call read_data() first.")
        return self.data

class DataManager:
    def __init__(self, database: iDatabaseInterface, data_type=None, year=None):
        self.database = database
        self.data_type = ['census', 'election_results', 'polling_data'] if data_type is None else data_type
        self.year = [2011, 2021] if year is None else year
        self.data_uploader: CSVDataUploader | None = None
        self.data: pd.DataFrame | None = None
        self.table_name: str | None = None

    def load_training_data(self, poll_column):
        query = f"""
            SELECT
                er.wd_code,
                ew.cc_code,
                cand.registered_party AS party_name,
                cand.candidate_name,
                er.election_year,
                er.candidate_id,
                AVG(er.vote_share) AS party_vote_share,
                AVG(er.{poll_column}) AS national_poll_share
            FROM election_results er
            JOIN candidates cand
                ON er.candidate_id = cand.candidate_id
            LEFT JOIN electoral_wards ew
                ON er.wd_code = ew.wd_code
            WHERE er.is_uncontested = 0
            GROUP BY
                er.wd_code,
                ew.cc_code,
                cand.registered_party,
                cand.candidate_name,
                er.election_year,
                er.candidate_id
        """
        return self.database.fetch_dataframe(query)

    def get_data(self, csv_path: str, table_name: str) -> pd.DataFrame:
        self.table_name = table_name
        self.data_uploader = CSVDataUploader(data_source=csv_path)
        self.data_uploader.read_data()
        self.data = self.data_uploader.send_data()
        return self.data

    def preprocess_data(self):
        if self.data is None or self.data_uploader is None:
            raise ValueError("No data has been loaded. Call get_data() first.")
        self.data = self.data_uploader.preprocess_data()
        return self.data

    @staticmethod
    def read_nomis_csv(file_path: str) -> pd.DataFrame:
        def is_table_header(row: list[str]) -> bool:
            lowered = [column.strip().lower() for column in row]
            non_empty_cells = [column for column in lowered if column]
            if len(non_empty_cells) < 3:
                return False

            first_cell = lowered[0]
            if (
                "ons crown copyright" in first_cell
                or first_cell.startswith(("population", "units", "date", "rural urban"))
            ):
                return False

            return (
                "output area" in first_cell
                or "geography code" in first_cell
                or "all persons" in first_cell
                or any(column == "%" for column in lowered)
            )

        with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
            header_row = next(
                (index for index, row in enumerate(csv.reader(csv_file)) if row and is_table_header(row)),
                None,
            )
        if header_row is None:
            raise ValueError(f"Could not find a Nomis table header in {file_path}")

        dataframe = pd.read_csv(file_path, skiprows=header_row, dtype=str, low_memory=False).dropna(how="all")
        oa_column = next(
            (
                column for column in dataframe.columns
                if any(marker in str(column).strip().lower() for marker in ("output area", "geography code"))
                or str(column).strip().lower() == "mnemonic"
            ),
            None,
        )
        if oa_column is None:
            oa_pattern = re.compile(r"^[EWNS]\d{8}$", re.IGNORECASE)
            oa_column = max(
                dataframe.columns,
                key=lambda column: dataframe[column].astype(str).str.strip().head(200).str.match(oa_pattern).sum(),
            )
        dataframe["oa_code"] = dataframe[oa_column].astype(str).str.strip()
        return dataframe

    @staticmethod
    def _column_index(dataframe: pd.DataFrame, hint: str) -> int | None:
        normalised_hint = hint.strip().lower()
        return next(
            (index for index, column in enumerate(dataframe.columns) if normalised_hint in str(column).strip().lower()),
            None,
        )

    @classmethod
    def _numeric_column(cls, dataframe: pd.DataFrame, hint: str) -> pd.Series:
        column_index = cls._column_index(dataframe, hint)
        if column_index is None:
            return pd.Series(0.0, index=dataframe.index, dtype="float64")
        return pd.to_numeric(dataframe.iloc[:, column_index], errors="coerce").fillna(0.0)

    @classmethod
    def _percentage_after(cls, dataframe: pd.DataFrame, label: str) -> pd.Series:
        column_index = cls._column_index(dataframe, label)
        if column_index is None or column_index + 1 >= dataframe.shape[1]:
            return pd.Series(0.0, index=dataframe.index, dtype="float64")
        return pd.to_numeric(dataframe.iloc[:, column_index + 1], errors="coerce").fillna(0.0)

    @classmethod
    def _map_by_oa(cls, source: pd.DataFrame, values: pd.Series, oa_codes: pd.Series) -> pd.Series:
        keyed = pd.DataFrame({"oa_code": source["oa_code"].astype(str).str.strip(), "value": values})
        keyed = keyed[keyed["oa_code"].str.match(r"^[EWNS]\d{8}$", na=False)]
        value_by_oa = keyed.drop_duplicates("oa_code").set_index("oa_code")["value"]
        return oa_codes.map(value_by_oa).fillna(0.0)

    def prepare_census_data(self, census_folder: str, census_year: int) -> pd.DataFrame:
        file_names = {
            "age": "Census_age.csv", "bch": "Census_bch.csv", "foreign_born": "Census_foreign-born.csv",
            "sex": "Census_sex.csv", "midclass": "Census_midclass.csv", "working_class": "Census_workingClass.csv",
            "students": "Census_students.csv", "tenure": "Census_tenure.csv",
        }
        datasets = {
            name: self.read_nomis_csv(os.path.join(census_folder, f"{census_year}{file_name}"))
            for name, file_name in file_names.items()
        }
        age = datasets["age"]
        result = pd.DataFrame({"oa_code": age["oa_code"].astype(str).str.strip()})

        def percentage_sum(dataframe: pd.DataFrame, labels: list[str]) -> pd.Series:
            return sum((self._percentage_after(dataframe, label) for label in labels), pd.Series(0.0, index=dataframe.index))

        age_18_29 = percentage_sum(age, ["age 18 to 19", "age 20 to 24", "age 25 to 29"])
        if age_18_29.sum() == 0:
            age_18_29 = sum((self._numeric_column(age, label) for label in ("aged 15 to 19", "aged 20 to 24", "aged 25 to 29")), pd.Series(0.0, index=age.index))
        age_30_65 = percentage_sum(age, ["age 30 to 44", "age 45 to 59", "age 60 to 64"])
        if age_30_65.sum() == 0:
            age_30_65 = sum((self._numeric_column(age, f"aged {start} to {end}") for start, end in ((30, 34), (35, 39), (40, 44), (45, 49), (50, 54), (55, 59), (60, 64))), pd.Series(0.0, index=age.index))
        age_over_65 = percentage_sum(age, ["age 65 to 74", "age 75 to 84", "age 85 to 89", "age 90 and over"])
        if age_over_65.sum() == 0:
            age_over_65 = sum((self._numeric_column(age, label) for label in ("aged 65 to 69", "aged 70 to 74", "aged 75 to 79", "aged 80 to 84", "aged 85 years and over")), pd.Series(0.0, index=age.index))

        sex = datasets["sex"]
        female = self._percentage_after(sex, "females")
        male = self._percentage_after(sex, "males")
        if female.sum() == 0 and male.sum() == 0:
            female = self._percentage_after(sex, "female")
            male = 100 - female

        bch = datasets["bch"]
        bch_total = self._numeric_column(bch, "all categories: highest level of qualification")
        bch_level4 = self._numeric_column(bch, "level 4 qualifications and above")
        if bch_total.sum() == 0:
            bch_total = self._numeric_column(bch, "total: all usual residents aged 16")
            bch_level4 = self._numeric_column(bch, "level 4 qualifications or above")

        foreign_born = datasets["foreign_born"]
        foreign_born_pct = self._percentage_after(foreign_born, "foreign_born")
        if foreign_born_pct.sum() == 0:
            uk_pct = self._percentage_after(foreign_born, "europe: united kingdom")
            foreign_born_pct = 100 - uk_pct if uk_pct.sum() else pd.Series(0.0, index=foreign_born.index)

        students = datasets["students"]
        student_pct = self._percentage_after(students, "economically active: full-time student") + self._percentage_after(students, "economically inactive: student")
        if student_pct.sum() == 0:
            student_pct = self._percentage_after(students, "student")

        tenure = datasets["tenure"]
        own_home = self._percentage_after(tenure, "owned")
        rent = self._percentage_after(tenure, "private rented")
        midclass = datasets["midclass"]
        working_class = datasets["working_class"]
        middle_class_pct = self._percentage_after(midclass, "mid_class")
        working_class_pct = self._percentage_after(working_class, "approximated social grade de")
        if working_class_pct.sum() == 0:
            working_class_pct = self._percentage_after(working_class, "de semi-skilled")

        result["census_year"] = census_year
        result["pct_age_18_29"] = self._map_by_oa(age, age_18_29, result["oa_code"])
        result["pct_age_30_65"] = self._map_by_oa(age, age_30_65, result["oa_code"])
        result["pct_age_over_65"] = self._map_by_oa(age, age_over_65, result["oa_code"])
        result["pct_male"] = self._map_by_oa(sex, male, result["oa_code"])
        result["pct_female"] = self._map_by_oa(sex, female, result["oa_code"])
        result["pct_student"] = self._map_by_oa(students, student_pct, result["oa_code"])
        result["pct_bch"] = self._map_by_oa(bch, bch_level4 / bch_total.replace(0, pd.NA) * 100, result["oa_code"])
        result["pct_wk_class"] = self._map_by_oa(working_class, working_class_pct, result["oa_code"])
        result["pct_mid_class"] = self._map_by_oa(midclass, middle_class_pct, result["oa_code"])
        result["pct_own_hme"] = self._map_by_oa(tenure, own_home, result["oa_code"])
        result["pct_rent"] = self._map_by_oa(tenure, rent, result["oa_code"])
        result["pct_fb"] = self._map_by_oa(foreign_born, foreign_born_pct, result["oa_code"])
        return result[result["oa_code"].str.match(r"^[EWNS]\d{8}$", na=False)].round(2)

    def store_census_data(self, census_data: pd.DataFrame) -> int:
        columns = list(census_data.columns)
        update_columns = [column for column in columns if column not in {"oa_code", "census_year"}]
        statement = f"""
            INSERT INTO census ({", ".join(columns)})
            VALUES ({", ".join(f":{column}" for column in columns)})
            ON DUPLICATE KEY UPDATE
            {", ".join(f"{column} = VALUES({column})" for column in update_columns)}
        """
        self.database.execute_many(statement, census_data.to_dict(orient="records"))
        return len(census_data)

    @staticmethod
    def prepare_county_codes(lookups_folder: str) -> pd.DataFrame:
        lookup_files = glob.glob(
            os.path.join(
                lookups_folder,
                "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv",
            )
        )
        councils: set[tuple[str, str]] = set()

        for file_path in sorted(lookup_files):
            columns = pd.read_csv(file_path, nrows=2).columns.tolist()
            lad_code = next((column for column in columns if re.fullmatch(r"LAD\d+CD", column)), None)
            lad_name = next((column for column in columns if re.fullmatch(r"LAD\d+NM", column)), None)
            county_code = next((column for column in columns if re.fullmatch(r"CTY\d+CD", column)), None)
            county_name = next((column for column in columns if re.fullmatch(r"CTY\d+NM", column)), None)
            if not all((lad_code, lad_name, county_code, county_name)):
                continue

            dataframe = pd.read_csv(
                file_path,
                usecols=[lad_code, lad_name, county_code, county_name],
                low_memory=False,
            )
            for code, name in dataframe[[county_code, county_name]].dropna().drop_duplicates().itertuples(index=False):
                councils.add((str(code).strip(), f"{str(name).strip()} County Council"))

            unitary_rows = dataframe[county_code].isna()
            for code, name in dataframe.loc[unitary_rows, [lad_code, lad_name]].dropna().drop_duplicates().itertuples(index=False):
                council_name = str(name).strip()
                if not any(token in council_name for token in ("Council", "Borough", "City")):
                    council_name = f"{council_name} Council"
                councils.add((str(code).strip(), council_name))

        return pd.DataFrame(sorted(councils), columns=["cc_code", "council_name"])

    def store_county_codes(self, county_codes: pd.DataFrame) -> int:
        required_columns = {"cc_code", "council_name"}
        if not required_columns.issubset(county_codes.columns):
            raise ValueError("County codes require cc_code and council_name columns.")

        statement = """
            INSERT INTO county_codes (cc_code, council_name)
            VALUES (:cc_code, :council_name)
            ON DUPLICATE KEY UPDATE council_name = VALUES(council_name)
        """
        records = county_codes[["cc_code", "council_name"]].drop_duplicates().to_dict(orient="records")
        self.database.execute_many(statement, records)
        return len(records)

    @staticmethod
    def prepare_geographic_lookup(
        oa_to_lsoa_path: str,
        lsoa_to_ward_path: str,
        ward_to_ced_path: str,
        lookup_version_year: int,
        valid_ward_codes: set[str] | None = None,
    ) -> pd.DataFrame:
        output_areas = pd.read_csv(oa_to_lsoa_path, usecols=["OA21CD", "LSOA21CD"])
        wards = pd.read_csv(lsoa_to_ward_path, usecols=["LSOA21CD", "WD25CD"])
        divisions = pd.read_csv(ward_to_ced_path, usecols=["WD25CD", "CED25CD"])

        lookup = output_areas.merge(wards, on="LSOA21CD", how="inner").merge(divisions, on="WD25CD", how="inner")
        lookup["oa_code"] = lookup["OA21CD"].astype(str).str.strip()
        lookup["wd_code"] = lookup["CED25CD"].astype(str).str.strip()
        if valid_ward_codes:
            lookup = lookup[lookup["wd_code"].isin(valid_ward_codes)]
        lookup["lookup_version_year"] = lookup_version_year
        return lookup[["oa_code", "wd_code", "lookup_version_year"]].drop_duplicates()

    def replace_geographic_lookup(self, lookup_data: pd.DataFrame) -> int:
        required_columns = {"oa_code", "wd_code", "lookup_version_year"}
        if not required_columns.issubset(lookup_data.columns):
            raise ValueError("Geographic lookup data is missing required columns.")

        records = lookup_data[["oa_code", "wd_code", "lookup_version_year"]].drop_duplicates().to_dict(orient="records")
        if not records:
            return 0
        self.database.execute_many("TRUNCATE TABLE geographic_lookup", [{}])
        self.database.execute_many(
            """
            INSERT INTO geographic_lookup (oa_code, wd_code, lookup_version_year)
            VALUES (:oa_code, :wd_code, :lookup_version_year)
            """,
            records,
        )
        return len(records)

    @staticmethod
    def normalise_party_name(value: object) -> str:
        if pd.isna(value): # pyright: ignore[reportArgumentType, reportCallIssue]
            return "Independent"
        party_name = str(value).strip().lower()
        party_mappings = {
            "con": "Conservative",
            "lab": "Labour",
            "ld": "Liberal Democrats",
            "ind": "Independent",
        }
        if "conservative" in party_name:
            return "Conservative"
        if "labour" in party_name:
            return "Labour"
        if "liberal democrat" in party_name:
            return "Liberal Democrats"
        if "green party" in party_name or party_name == "green":
            return "Green Party"
        if "reform" in party_name:
            return "Reform UK"
        if "independent" in party_name:
            return "Independent"
        if "ukip" in party_name or "independence party" in party_name:
            return "UK Independence Party (UKIP)"
        return party_mappings.get(party_name, str(value).strip())

    @staticmethod
    def validate_poll_share(value: object) -> float:
        try:
            poll_share = float(value) # pyright: ignore[reportArgumentType]
        except (TypeError, ValueError) as error:
            raise ValueError("Poll share must be a number between 0 and 100.") from error
        if not 0 <= poll_share <= 100:
            raise ValueError("Poll share must be a number between 0 and 100.")
        return poll_share

import os
import glob
import re
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

class ElectionDataExtractor:
    """
    Class 1: Extracts, cleans, normalizes, and resolves geography codes 
    (supporting both county and lower-tier district/borough councils) from Democracy Club CSVs.
    """
    def __init__(self, input_folder: str, output_processed_folder: str, lookups_folder: str):
        self.input_folder = input_folder
        self.output_processed_folder = output_processed_folder
        self.lookups_folder = lookups_folder
        
        os.makedirs(output_processed_folder, exist_ok=True)
        self.lookup_by_council, self.lookup_unique_name = self._build_lookup_geo_maps()

    @staticmethod
    def _norm_council_name(value):
        if pd.isna(value):
            return ""
        text = str(value).strip().lower()
        text = text.replace("&", "and")
        text = re.sub(r"[^a-z0-9 ]", "", text)
        for term in ["county council", "district council", "borough council", "council"]:
            text = text.replace(term, "")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _norm_geo_name(value):
        if pd.isna(value):
            return ""
        text = str(value).strip().lower()
        text = text.replace("&", "and")
        text = re.sub(r"[^a-z0-9 ]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _parse_election_dates(series):
        s = series.astype(str).str.strip()
        s = s.replace({'': pd.NA, 'nan': pd.NA, 'None': pd.NA})
        parsed = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')

        year_first_mask = s.str.match(r'^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$', na=False)
        if year_first_mask.any():
            parsed.loc[year_first_mask] = pd.to_datetime(
                s.loc[year_first_mask], format='mixed', dayfirst=False, errors='coerce'
            )

        remaining_mask = ~year_first_mask
        if remaining_mask.any():
            parsed.loc[remaining_mask] = pd.to_datetime(
                s.loc[remaining_mask], format='mixed', dayfirst=True, errors='coerce'
            )
        return parsed

    def _build_lookup_geo_maps(self):
        by_council = {}
        unique_name_codes = {}
        files = glob.glob(os.path.join(self.lookups_folder, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv"))
        files += glob.glob(os.path.join(self.lookups_folder, "Ward_to_Local_Authority_District_*.csv"))

        for file_path in files:
            try:
                sample = pd.read_csv(file_path, nrows=2, low_memory=False)
                cols = sample.columns.tolist()
                wd_code_col = next((c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'), None)
                wd_name_col = next((c for c in cols if re.match(r'WD\d+NM', c) or c == 'WDNM'), None)
                ced_code_col = next((c for c in cols if re.match(r'CED\d+CD', c) or c == 'CEDCD'), None)
                ced_name_col = next((c for c in cols if re.match(r'CED\d+NM', c) or c == 'CEDNM'), None)
                cty_name_col = next((c for c in cols if re.match(r'CTY\d+NM', c) or c == 'CTYNM'), None)
                lad_name_col = next((c for c in cols if re.match(r'LAD\d+NM', c) or c == 'LADNM'), None)

                use_cols = [c for c in [wd_code_col, wd_name_col, ced_code_col, ced_name_col, cty_name_col, lad_name_col] if c]
                if not use_cols:
                    continue

                df_lookup = pd.read_csv(file_path, usecols=use_cols, low_memory=False)
                for _, row in df_lookup.iterrows():
                    council_name = ""
                    if cty_name_col and pd.notna(row.get(cty_name_col)):
                        council_name = str(row[cty_name_col]).strip()
                    elif lad_name_col and pd.notna(row.get(lad_name_col)):
                        council_name = str(row[lad_name_col]).strip()
                    norm_council = self._norm_council_name(council_name)

                    pairs = []
                    if wd_code_col and wd_name_col and pd.notna(row.get(wd_code_col)) and pd.notna(row.get(wd_name_col)):
                        pairs.append((self._norm_geo_name(row[wd_name_col]), str(row[wd_code_col]).strip()))
                    if ced_code_col and ced_name_col and pd.notna(row.get(ced_code_col)) and pd.notna(row.get(ced_name_col)):
                        pairs.append((self._norm_geo_name(row[ced_name_col]), str(row[ced_code_col]).strip()))

                    for norm_name, code in pairs:
                        if not norm_name or not code or code.lower() == 'nan':
                            continue
                        if norm_council:
                            by_council.setdefault((norm_council, norm_name), code)
                        unique_name_codes.setdefault(norm_name, set()).add(code)
            except Exception:
                continue

        unique_name_map = {name: next(iter(codes)) for name, codes in unique_name_codes.items() if len(codes) == 1}
        return by_council, unique_name_map

    def process_all_files(self):
        democracy_club_files = [f for f in os.listdir(self.input_folder) if f.endswith('.csv')]
        print(f"[EXTRACT] Found {len(democracy_club_files)} CSV source file(s) to process.")
        
        all_processed_rows = []
        for file_name in democracy_club_files:
            file_path = os.path.join(self.input_folder, file_name)
            try:
                df_massive = pd.read_csv(file_path, low_memory=False)
            except Exception as e:
                print(f"    [SKIP ERROR] Failed to read {file_name}: {e}")
                continue
                
            if 'organisation_name' not in df_massive.columns or 'election_date' not in df_massive.columns:
                continue

            df_massive['canonical_council_name'] = df_massive['organisation_name'].fillna("Unknown Authority").astype(str).str.strip()
            df_filtered = df_massive.copy()
            
            parsed_dates = self._parse_election_dates(df_filtered['election_date'])
            df_filtered['clean_election_date'] = parsed_dates.dt.strftime('%Y-%m-%d')
            df_filtered['election_year'] = parsed_dates.dt.year
            df_filtered = df_filtered.dropna(subset=['election_year'])
            df_filtered['election_year'] = df_filtered['election_year'].astype(int)

            df_filtered['votes_cast'] = pd.to_numeric(df_filtered['votes_cast'], errors='coerce').fillna(0).astype(int)
            df_filtered['is_elected'] = df_filtered['elected'].astype(str).str.lower().isin(['t', 'true', '1', 'yes', 'y']).astype(int)
            df_filtered['is_uncontested'] = df_filtered['by_election'].astype(str).str.lower().isin(['t', 'true', '1', 'yes', 'y']).astype(int)
            df_filtered['by_election'] = df_filtered['by_election'].astype(str).str.lower().isin(['t', 'true', '1', 'yes', 'y']).astype(int)

            if 'gss' in df_filtered.columns:
                df_filtered['wd_code_resolved'] = df_filtered['gss'].fillna('').astype(str).str.strip()
            else:
                df_filtered['wd_code_resolved'] = ''

            council_keys = df_filtered['canonical_council_name'].map(self._norm_council_name)
            ward_keys = df_filtered['post_label'].map(self._norm_geo_name)

            blank_mask = df_filtered['wd_code_resolved'].eq('')
            if blank_mask.any():
                council_lookup = [self.lookup_by_council.get((c, w), '') for c, w in zip(council_keys, ward_keys)]
                df_filtered.loc[blank_mask, 'wd_code_resolved'] = pd.Series(council_lookup, index=df_filtered.index).loc[blank_mask]

                still_blank = df_filtered['wd_code_resolved'].eq('')
                if still_blank.any():
                    unique_lookup = ward_keys.map(self.lookup_unique_name).fillna('')
                    df_filtered.loc[still_blank, 'wd_code_resolved'] = unique_lookup.loc[still_blank]

            df_staged = pd.DataFrame({
                'wd_code': df_filtered['wd_code_resolved'],
                'ward_name': df_filtered['post_label'],
                'council_name': df_filtered['canonical_council_name'],
                'election_date': df_filtered['clean_election_date'],
                'election_year': df_filtered['election_year'],
                'candidate_id': df_filtered['person_id'],
                'candidate_name': df_filtered['person_name'],
                'party_name': df_filtered['party_name'],
                'seats_available': pd.to_numeric(df_filtered['seats_contested'], errors='coerce').fillna(1).astype(int),
                'is_uncontested': df_filtered['is_uncontested'],
                'by_election': df_filtered['by_election'],
                'votes_received': df_filtered['votes_cast'],
                'is_elected': df_filtered['is_elected'],
                'is_incumbent_cllr': 0
            })
            all_processed_rows.append(df_staged)

        if not all_processed_rows:
            print("[EXTRACT] No data extracted.")
            return

        df_master = pd.concat(all_processed_rows, ignore_index=True)
        df_master = df_master.dropna(subset=['candidate_name'])
        df_master = df_master[df_master['candidate_name'].str.strip() != '']

        ward_totals = df_master.groupby(['election_year', 'ward_name'])['votes_received'].transform('sum')
        df_master['vote_share_pc'] = (df_master['votes_received'] / ward_totals * 100).round(2).fillna(0.0)

        for year, df_year_batch in df_master.groupby('election_year'):
            df_year_clean = df_year_batch.sort_values(by=['council_name', 'ward_name', 'vote_share_pc'], ascending=[True, True, False])
            file_name_out = f"target_council_results_{year}_clean.csv"
            out_path = os.path.join(self.output_processed_folder, file_name_out)
            df_year_clean.to_csv(out_path, index=False)
            print(f"[EXTRACT] Saved {len(df_year_clean):,} rows to processed file: {file_name_out}")


class ElectionDatabaseLoader:
    """
    Class 2: Connects to the database (MySQL/PostgreSQL) and securely loads cleaned 
    processed CSV results into election_results, candidates, and electoral_wards without duplicates.
    """
    def __init__(self, db_config: dict, processed_folder: str, lookups_folder: str):
        self.db_config = db_config
        self.processed_folder = processed_folder
        self.lookups_folder = lookups_folder
        
        db_backend = os.getenv("DB_BACKEND", "postgres").strip().lower()
        if db_backend == "mysql":
            self.engine = create_engine(
                f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
                f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )
        else:
            self.engine = create_engine(
                f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}@"
                f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )
            
        self.ward_to_authority = self._build_ward_authority_map()

    def _build_ward_authority_map(self):
        ward_map = {}
        files = glob.glob(os.path.join(self.lookups_folder, "Ward_to_LAD_to_County_to_County_Electoral_Division_*.csv"))
        files += glob.glob(os.path.join(self.lookups_folder, "Ward_to_Local_Authority_District_*.csv"))

        for file_path in files:
            try:
                sample = pd.read_csv(file_path, nrows=2, low_memory=False)
                cols = sample.columns.tolist()
                wd_col = next((c for c in cols if re.match(r'WD\d+CD', c) or c == 'WDCD'), None)
                ced_col = next((c for c in cols if re.match(r'CED\d+CD', c) or c == 'CEDCD'), None)
                lad_col = next((c for c in cols if re.match(r'LAD\d+CD', c) or c == 'LADCD'), None)
                cty_col = next((c for c in cols if re.match(r'CTY\d+CD', c) or c == 'CTYCD'), None)
                
                if not lad_col:
                    continue
                
                df = pd.read_csv(file_path, usecols=[c for c in [wd_col, ced_col, lad_col, cty_col] if c], low_memory=False)
                for _, row in df.iterrows():
                    lad_code = str(row[lad_col]).strip() if pd.notna(row[lad_col]) else ""
                    cty_code = str(row[cty_col]).strip() if cty_col and pd.notna(row[cty_col]) else ""
                    
                    chosen_code = lad_code if lad_code and lad_code.lower() != "nan" else cty_code
                    
                    if chosen_code and chosen_code.lower() != "nan":
                        for code_col in [wd_col, ced_col]:
                            if code_col and pd.notna(row.get(code_col)):
                                val = str(row[code_col]).strip()
                                if val:
                                    ward_map[val] = chosen_code
            except Exception:
                continue
        return ward_map

    @staticmethod
    def _clean_party_string(val):
        if pd.isna(val): 
            return "Independent"
        s = str(val).strip().lower()
        if "conservative" in s: return "Conservative"
        if "labour" in s: return "Labour"
        if "liberal democrat" in s: return "Liberal Democrats"
        if "green party" in s or s == "green": return "Green Party"
        if "reform" in s: return "Reform UK"
        if "independent" in s: return "Independent"
        return str(val).strip()

    def upload_all(self):
        target_files = [f for f in os.listdir(self.processed_folder) if f.startswith("target_council_results_") and f.endswith(".csv")]
        print(f"[LOAD] Found {len(target_files)} cleaned dataset(s) for database insertion.")

        db_backend = os.getenv("DB_BACKEND", "postgres").strip().lower()
        current_db_fn = "DATABASE()" if db_backend == "mysql" else "current_database()"
        with self.engine.connect() as conn:
            vote_share_col = conn.execute(text(f"""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = {current_db_fn} AND TABLE_NAME = 'election_results'
                  AND COLUMN_NAME IN ('vote_share_pc', 'vote_share') LIMIT 1
            """)).scalar() or 'vote_share'

        for file_name in sorted(target_files):
            file_path = os.path.join(self.processed_folder, file_name)
            df_flat = pd.read_csv(file_path, low_memory=False)
            
            df_flat['candidate_name'] = df_flat['candidate_name'].fillna('').astype(str).str.strip()
            df_flat['clean_party'] = df_flat['party_name'].apply(self._clean_party_string)
            df_flat['clean_ward_code'] = df_flat['wd_code'].fillna('').astype(str).str.strip()
            df_flat['derived_cc_code'] = df_flat['clean_ward_code'].map(self.ward_to_authority)
            
            df_flat = df_flat.dropna(subset=['derived_cc_code'])
            if len(df_flat) == 0:
                continue

            # 1. Commit Candidates without duplicates
            df_candidates = df_flat[['candidate_name', 'clean_party']].drop_duplicates()
            from_clause = "FROM dual" if db_backend == "mysql" else ""
            with self.engine.connect() as conn:
                for _, row in df_candidates.iterrows():
                    conn.execute(text(f"""
                        INSERT INTO candidates (candidate_name, registered_party)
                        SELECT :name, :party {from_clause}
                        WHERE NOT EXISTS (
                            SELECT 1 FROM candidates WHERE candidate_name = :name AND registered_party = :party
                        );
                    """), {"name": row['candidate_name'], "party": row['clean_party']})
                conn.commit()

            # 2. Fetch candidate IDs and map
            df_db_candidates = pd.read_sql("SELECT candidate_id, candidate_name, registered_party FROM candidates", con=self.engine)
            df_flat['join_name'] = df_flat['candidate_name'].str.lower().str.strip()
            df_flat['join_party'] = df_flat['clean_party'].str.lower().str.strip()
            df_db_candidates['join_name'] = df_db_candidates['candidate_name'].str.lower().str.strip()
            df_db_candidates['join_party'] = df_db_candidates['registered_party'].str.lower().str.strip()

            df_staged = pd.merge(
                df_flat, 
                df_db_candidates[['candidate_id', 'join_name', 'join_party']].rename(columns={'candidate_id': 'resolved_candidate_id'}), 
                on=['join_name', 'join_party'],
                how='inner'
            )

            if len(df_staged) == 0:
                continue

            # 3. Format Core Results for Upsert without duplicates
            df_core = pd.DataFrame({
                'wd_code': df_staged['clean_ward_code'],
                'candidate_id': pd.to_numeric(df_staged['resolved_candidate_id']).astype(int),
                'election_date': df_staged['election_date'],
                'election_year': pd.to_numeric(df_staged['election_year']).astype(int),
                'votes_received': pd.to_numeric(df_staged['votes_received']).astype(int),
                'vote_share_value': pd.to_numeric(df_staged['vote_share_pc']).astype(float),
                'seats_available': pd.to_numeric(df_staged['seats_available']).astype(int),
                'is_uncontested': pd.to_numeric(df_staged['is_uncontested']).astype(bool),
                'is_elected': pd.to_numeric(df_staged['is_elected']).astype(bool),
                'is_incumbent_cllr': False
            }).where(pd.notnull, None)

            insert_cols = ['wd_code', 'election_date', 'candidate_id', 'seats_available', 'is_uncontested', 'votes_received', vote_share_col, 'election_year', 'is_elected', 'is_incumbent_cllr']
            val_expr = [':vote_share_value' if c == vote_share_col else f':{c}' for c in insert_cols]
            
            db_backend = os.getenv("DB_BACKEND", "postgres").strip().lower()
            if db_backend == "mysql":
                upsert_sql = f"""
                    INSERT INTO election_results ({', '.join(insert_cols)}) VALUES ({', '.join(val_expr)})
                    ON DUPLICATE KEY UPDATE votes_received = VALUES(votes_received), {vote_share_col} = VALUES({vote_share_col})
                """
            else:
                upsert_sql = f"""
                    INSERT INTO election_results ({', '.join(insert_cols)}) VALUES ({', '.join(val_expr)})
                    ON CONFLICT (wd_code, election_date, candidate_id) 
                    DO UPDATE SET votes_received = EXCLUDED.votes_received, {vote_share_col} = EXCLUDED.{vote_share_col}
                """

            rows = df_core.to_dict(orient='records')
            with self.engine.connect() as conn:
                for i in range(0, len(rows), 5000):
                    conn.execute(text(upsert_sql), rows[i:i+5000])
                conn.commit()
            print(f"[LOAD] Successfully upserted {len(rows):,} records from {file_name} without duplicates.")


if __name__ == "__main__":
    democracy_club_input = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\democracy club"
    processed_output_folder = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\election_results\processed"
    lookups_directory = r"C:\Users\ianmi\Computer Programs\Local_Election_forecaster\data\Lookups"

    db_configuration = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
        'database': os.getenv('POSTGRES_DB', 'irp_election_forecasting')
    }

    print("==================================================")
    print(" STARTING ELECTION RESULTS EXTRACTION & INGESTION")
    print("==================================================")

    # Step 1: Extract and clean Democracy Club raw files
    extractor = ElectionDataExtractor(
        input_folder=democracy_club_input,
        output_processed_folder=processed_output_folder,
        lookups_folder=lookups_directory
    )
    extractor.process_all_files()

    # Step 2: Load into DB without duplicates
    loader = ElectionDatabaseLoader(
        db_config=db_configuration,
        processed_folder=processed_output_folder,
        lookups_folder=lookups_directory
    )
    loader.upload_all()

    print("==================================================")
    print(" PIPELINE COMPLETED SUCCESSFULLY")
    print("==================================================")