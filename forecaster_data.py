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

