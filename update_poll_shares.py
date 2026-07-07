"""Interactive one-off script to update national poll shares by election date and party.

Usage:
    python update_poll_shares.py

Controls while entering values:
    - Enter a number (e.g. 27.5) to update that party/date poll share.
    - Press Enter to skip and leave existing values untouched.
    - Type q to quit early.
"""

import os
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "Xabp74yb%"),
    "database": os.getenv("MYSQL_DB", "irp_election_forecasting"),
}


def build_engine():
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )


def test_connection(engine):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[SUCCESS] Connected to MySQL database.")
        print("==============================================")
    except OperationalError as exc:
        raise RuntimeError(
            "Database login failed. Verify credentials and schema access."
        ) from exc


def fetch_date_party_rows(engine):
    query = text(
        """
        SELECT DISTINCT
            er.election_date,
            YEAR(er.election_date) AS election_year,
            DAYNAME(er.election_date) AS day_of_week,
            cand.registered_party AS party_name,
            ROUND(AVG(NULLIF(er.national_poll_party_share, 0)), 3) AS existing_poll_share
        FROM election_results er
        INNER JOIN candidates cand ON er.candidate_id = cand.candidate_id
        WHERE cand.registered_party IS NOT NULL
          AND TRIM(cand.registered_party) <> ''
        GROUP BY er.election_date, YEAR(er.election_date), DAYNAME(er.election_date), cand.registered_party
        ORDER BY er.election_date DESC, cand.registered_party ASC
        """
    )

    with engine.connect() as conn:
        return conn.execute(query).mappings().all()


def prompt_poll_value(election_date, party_name, existing_share):
    existing_text = "None" if existing_share is None else f"{existing_share:.3f}"
    prompt = (
        f"{election_date} | {party_name} | existing={existing_text} | "
        "new poll share (%), Enter=skip, q=quit: "
    )
    raw = input(prompt).strip()

    if raw == "":
        return "skip", None
    if raw.lower() == "q":
        return "quit", None

    try:
        value = float(raw)
    except ValueError:
        print("  [WARN] Invalid number. Skipped.")
        return "skip", None

    if value < 0 or value > 100:
        print("  [WARN] Value must be between 0 and 100. Skipped.")
        return "skip", None

    return "update", value


def update_poll_share(engine, election_date, party_name, poll_share):
    query = text(
        """
        UPDATE election_results er
        INNER JOIN candidates cand ON er.candidate_id = cand.candidate_id
        SET er.national_poll_party_share = :poll_share
        WHERE er.election_date = :election_date
          AND cand.registered_party = :party_name
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            query,
            {
                "poll_share": poll_share,
                "election_date": election_date,
                "party_name": party_name,
            },
        )
    return result.rowcount


def main():
    engine = build_engine()
    test_connection(engine)

    rows = fetch_date_party_rows(engine)
    if not rows:
        print("[INFO] No election date/party combinations found.")
        return

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["election_date"]].append(row)

    updates = 0
    skipped = 0

    print("[INFO] Starting interactive poll share input.")
    print("[INFO] Press Enter to skip a row, or q to quit early.")
    print("==============================================")

    for election_date in sorted(grouped.keys(), reverse=True):
        date_rows = grouped[election_date]
        election_year = date_rows[0]["election_year"]
        day_of_week = date_rows[0]["day_of_week"]
        print(f"\nDate: {election_date} ({day_of_week}, {election_year})")

        for row in date_rows:
            party_name = row["party_name"]
            existing_share = row["existing_poll_share"]
            action, value = prompt_poll_value(election_date, party_name, existing_share)

            if action == "quit":
                print("\n[INFO] Early exit requested.")
                print(f"[SUMMARY] Updated: {updates} | Skipped: {skipped}")
                return

            if action == "skip":
                skipped += 1
                continue

            affected = update_poll_share(engine, election_date, party_name, value)
            updates += 1
            print(f"  [UPDATED] {party_name} -> {value:.3f}% ({affected} rows)")

    print("\n[COMPLETE] Poll share update run finished.")
    print(f"[SUMMARY] Updated: {updates} | Skipped: {skipped}")


if __name__ == "__main__":
    main()


