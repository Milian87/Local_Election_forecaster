# Local_Election_forecaster
Independent Research Project to predict the results of local elections using demographics, electoral history, and national polls.

## Program

The main ETL program is in [scripts/Election_results_upload.py](scripts/Election_results_upload.py).
The desktop app entrypoint is [irp_computer_program.py](irp_computer_program.py).

## Setup

1. Create a virtual environment and install dependencies from [requirements.txt](requirements.txt).
2. Copy [.env.example](.env.example) to `.env` and set your PostgreSQL connection values.
3. Put processed election CSV files in `data/election_results/processed`, or set `RESULTS_INPUT_FOLDER` to another folder.
4. Run the uploader with Python.
5. Run the desktop app with `python irp_computer_program.py`.

## Notes

The repository intentionally ignores local data files, generated logs, and virtual environments. The uploader supports an optional `PURGE_ON_RUN=true` switch for clearing the staging tables before loading.

## Forecast Models

### Delta Model

The Delta Model predicts the change in each party's vote share from its historical baseline. It combines electoral history, demographic features, polling information, and tactical voting features, then applies the predicted change to the baseline share. Its design originated in Ian Milburn's MSc dissertation at the University of York in 2026.

### Softmax Model

The Softmax Model predicts an unconstrained support score for each party or candidate in a division, then normalizes the scores across that division so the forecasted vote shares sum to exactly 100%. This makes the model compositional and ensures that its division-level output is internally consistent.

### MySQL fallback

The forecast application uses PostgreSQL by default. To fall back to the retained MySQL backend, set this before starting the app:

```powershell
$env:DB_BACKEND = "mysql"
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "your-user"
$env:MYSQL_PASSWORD = "your-password"
$env:MYSQL_DB = "irp_election_forecasting"
```

Close the terminal or run `Remove-Item Env:DB_BACKEND` to return to the PostgreSQL default.
