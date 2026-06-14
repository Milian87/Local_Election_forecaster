# Local_Election_forecaster
Independent Research Project to predict the results of local elections using demographics, electoral history, and national polls.

## Program

The main ETL program is in [scripts/Election_results_upload.py](scripts/Election_results_upload.py).

## Setup

1. Create a virtual environment and install dependencies from [requirements.txt](requirements.txt).
2. Copy [.env.example](.env.example) to `.env` and set your MySQL connection values.
3. Put processed election CSV files in `data/election_results/processed`, or set `RESULTS_INPUT_FOLDER` to another folder.
4. Run the uploader with Python.

## Notes

The repository intentionally ignores local data files, generated logs, and virtual environments. The uploader supports an optional `PURGE_ON_RUN=true` switch for clearing the staging tables before loading.
