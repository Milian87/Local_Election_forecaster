"""Import cleaned election-result exports into the forecasting database."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from forecaster_data import DataManager
from forecaster_interfaces import iDatabaseInterface


class ElectionResultsImporter:
    """Stores processed election result files through the database abstraction."""

    required_columns = {
        "wd_code",
        "ward_name",
        "candidate_name",
        "party_name",
        "election_date",
    }

    def __init__(self, database: iDatabaseInterface):
        self.database = database

    def import_processed_folder(self, folder: str | Path) -> dict[str, int]:
        folder_path = Path(folder)
        files = sorted(folder_path.glob("target_council_results_*_clean.csv"))
        if not files:
            raise FileNotFoundError(f"No processed election result files found in {folder_path}")

        imported_rows = 0
        for file_path in files:
            imported_rows += self.import_processed_file(file_path)

        return {"files_processed": len(files), "rows_imported": imported_rows}

    def import_processed_file(self, file_path: str | Path) -> int:
        dataframe = pd.read_csv(file_path, low_memory=False)
        prepared = self.prepare_results(dataframe, file_path)
        if prepared.empty:
            return 0

        self.database.connect()
        try:
            self._store_candidates(prepared)
            results = self._resolve_candidate_ids(prepared)
            self._store_results(results)
        finally:
            self.database.disconnect()
        return len(prepared)

    @classmethod
    def prepare_results(cls, dataframe: pd.DataFrame, source_path: str | Path = "") -> pd.DataFrame:
        missing_columns = cls.required_columns.difference(dataframe.columns)
        if missing_columns:
            raise ValueError(
                f"{source_path or 'Election results'} is missing required columns: "
                f"{', '.join(sorted(missing_columns))}"
            )

        prepared = dataframe.copy()
        prepared["wd_code"] = prepared["wd_code"].fillna("").astype(str).str.strip()
        prepared["candidate_name"] = (
            prepared["candidate_name"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        )
        prepared["registered_party"] = prepared["party_name"].map(DataManager.normalise_party_name)
        prepared = prepared[(prepared["wd_code"] != "") & (prepared["candidate_name"] != "")].copy()

        dates = pd.to_datetime(prepared["election_date"], format="mixed", dayfirst=True, errors="coerce")
        file_year = cls._year_from_filename(source_path)
        prepared["election_date"] = dates.dt.strftime("%Y-%m-%d")
        prepared["election_year"] = dates.dt.year
        if "election_year" in dataframe.columns:
            supplied_year = pd.to_numeric(dataframe.loc[prepared.index, "election_year"], errors="coerce")
            prepared["election_year"] = supplied_year.fillna(prepared["election_year"])
        prepared["election_year"] = prepared["election_year"].fillna(file_year)
        if prepared["election_year"].isna().any():
            raise ValueError("Could not determine an election year for every result row.")
        prepared["election_year"] = prepared["election_year"].astype(int)
        fallback_dates = prepared["election_year"].astype(str) + "-05-01"
        prepared["election_date"] = prepared["election_date"].fillna(fallback_dates)

        prepared["votes_received"] = cls._numeric_column(prepared, ("votes_received", "votes_cast", "vote_count"), integer=True)
        prepared["vote_share"] = cls._numeric_column(prepared, ("vote_share_pc", "vote_share", "vote_share_percent"))
        prepared["seats_available"] = cls._numeric_column(prepared, ("seats_available", "seats_contested", "seats"), default=1, integer=True)
        prepared["is_uncontested"] = cls._boolean_column(prepared, ("is_uncontested", "uncontested"))
        prepared["is_elected"] = cls._boolean_column(prepared, ("is_elected", "elected"))
        prepared["is_incumbent_cllr"] = cls._boolean_column(prepared, ("is_incumbent_cllr", "incumbent", "is_incumbent"))
        prepared["national_poll_party_share"] = cls._numeric_column(prepared, ("national_poll_party_share", "national_poll"))
        prepared["prior_ward_closeness_margin"] = cls._numeric_column(prepared, ("prior_ward_closeness_margin", "closeness_margin"))
        return prepared

    def _store_candidates(self, results: pd.DataFrame) -> None:
        candidates = results[["candidate_name", "registered_party"]].drop_duplicates()
        statement = """
            INSERT INTO candidates (candidate_name, registered_party)
            SELECT :candidate_name, :registered_party
            WHERE NOT EXISTS (
                SELECT 1 FROM candidates
                WHERE candidate_name = :candidate_name
                  AND registered_party = :registered_party
            )
        """
        self.database.execute_many(statement, candidates.to_dict(orient="records"))

    def _resolve_candidate_ids(self, results: pd.DataFrame) -> pd.DataFrame:
        candidates = self.database.fetch_dataframe(
            "SELECT candidate_id, candidate_name, registered_party FROM candidates"
        )
        candidates = candidates.sort_values("candidate_id").drop_duplicates(
            ["candidate_name", "registered_party"], keep="first"
        )
        resolved = results.merge(
            candidates,
            on=["candidate_name", "registered_party"],
            how="left",
            validate="many_to_one",
        )
        if resolved["candidate_id"].isna().any():
            raise RuntimeError("Unable to resolve every candidate after candidate import.")
        resolved["candidate_id"] = resolved["candidate_id"].astype(int)
        return resolved

    def _store_results(self, results: pd.DataFrame) -> None:
        columns = [
            "wd_code", "election_date", "candidate_id", "seats_available", "is_uncontested",
            "votes_received", "vote_share", "election_year", "is_elected", "is_incumbent_cllr",
            "national_poll_party_share", "prior_ward_closeness_margin",
        ]
        update_columns = [column for column in columns if column not in {"wd_code", "election_date", "candidate_id"}]
        statement = f"""
            INSERT INTO election_results ({", ".join(columns)})
            VALUES ({", ".join(f":{column}" for column in columns)})
            ON DUPLICATE KEY UPDATE {", ".join(f"{column} = VALUES({column})" for column in update_columns)}
        """
        self.database.execute_many(statement, results[columns].to_dict(orient="records"))

    @staticmethod
    def _year_from_filename(source_path: str | Path) -> int | None:
        match = re.search(r"(20\d{2})", Path(source_path).name)
        return int(match.group(1)) if match else None

    @staticmethod
    def _numeric_column(
        dataframe: pd.DataFrame,
        candidates: tuple[str, ...],
        default: float = 0.0,
        integer: bool = False,
    ) -> pd.Series:
        column = next((candidate for candidate in candidates if candidate in dataframe.columns), None)
        if column is None:
            values = pd.Series(default, index=dataframe.index)
        else:
            values = pd.to_numeric(
                dataframe[column].astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
                errors="coerce",
            ).fillna(default)
        return values.astype(int) if integer else values.astype(float)

    @staticmethod
    def _boolean_column(dataframe: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series:
        column = next((candidate for candidate in candidates if candidate in dataframe.columns), None)
        if column is None:
            return pd.Series(0, index=dataframe.index, dtype="int64")
        return dataframe[column].astype(str).str.strip().str.lower().isin({"1", "true", "t", "yes", "y"}).astype(int)