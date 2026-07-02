import argparse
import csv
import os
import re
from typing import Dict, List, Tuple

import mysql.connector

TARGET_COUNCILS = [
    "Norfolk County Council",
    "Suffolk County Council",
    "Essex County Council",
    "Central Bedfordshire Council",
    "Cambridgeshire County Council",
    "Cornwall Council",
    "Cumberland County Council",
    "Devon County Council",
    "Dorset Council",
    "Derbyshire County Council",
    "Durham County Council",
    "Gloucestershire County Council",
    "Hampshire County Council",
    "Herefordshire Council",
    "Kent County Council",
    "Lincolnshire County Council",
    "North Yorkshire County Council",
    "Oxfordshire County Council",
    "Shropshire Council",
    "Staffordshire County Council",
    "Surrey County Council",
    "Warwickshire County Council",
    "West Sussex County Council",
    "Worcestershire County Council",
]

# Reorganization-aware code aliases: include modern unitary code(s) for legacy county labels.
CODE_ALIASES = {
    "E10000006": ["E06000063"],  # Cumbria County -> Cumberland
    "E10000009": ["E06000059"],  # Dorset County -> Dorset unitary
    "E10000023": ["E06000065"],  # North Yorkshire County -> North Yorkshire unitary
}


def normalize_name(name: str) -> str:
    s = str(name).strip().lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = s.replace("county council", "").replace("council", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_db_config() -> Dict[str, str]:
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "Xabp74yb%"),
        "database": os.getenv("MYSQL_DB", "irp_election_forecasting"),
    }


def build_reports(cur, alias_aware: bool) -> List[Tuple]:
    cur.execute("SELECT cc_code, council_name FROM county_codes")
    rows = cur.fetchall()
    exact = {r["council_name"]: r for r in rows}
    normed = {}
    for r in rows:
        key = normalize_name(r["council_name"])
        if key not in normed:
            normed[key] = r

    out = []
    for target in TARGET_COUNCILS:
        match = exact.get(target) or normed.get(normalize_name(target))
        if not match:
            out.append(
                (
                    target,
                    "",
                    "",
                    "NO",
                    "NO",
                    0,
                    0,
                    0,
                    "MISSING_IN_COUNTY_CODES",
                    "",
                )
            )
            continue

        base_cc = match["cc_code"]
        check_codes = [base_cc]
        if alias_aware:
            check_codes.extend(CODE_ALIASES.get(base_cc, []))

        ward_count = 0
        result_count = 0
        candidate_count = 0

        for cc_code in check_codes:
            cur.execute("SELECT COUNT(*) AS c FROM electoral_wards WHERE cc_code = %s", (cc_code,))
            ward_count += cur.fetchone()["c"]

            cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM election_results er
                INNER JOIN electoral_wards ew ON ew.wd_code = er.wd_code
                WHERE ew.cc_code = %s
                """,
                (cc_code,),
            )
            result_count += cur.fetchone()["c"]

            cur.execute(
                """
                SELECT COUNT(DISTINCT er.candidate_id) AS c
                FROM election_results er
                INNER JOIN electoral_wards ew ON ew.wd_code = er.wd_code
                WHERE ew.cc_code = %s
                """,
                (cc_code,),
            )
            candidate_count += cur.fetchone()["c"]

        status = "OK"
        if ward_count == 0:
            status = "NO_WARDS_MAPPED"
        elif result_count == 0:
            status = "NO_RESULTS_LINKED"

        aliases_used = ",".join(check_codes[1:]) if len(check_codes) > 1 else ""

        out.append(
            (
                target,
                match["council_name"],
                base_cc,
                "YES" if exact.get(target) else "NO",
                "YES",
                ward_count,
                result_count,
                candidate_count,
                status,
                aliases_used,
            )
        )

    return out


def write_report(path: str, rows: List[Tuple]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "target_council",
                "matched_council_name",
                "base_cc_code",
                "exact_name_match",
                "normalized_name_match",
                "electoral_wards_count",
                "election_results_rows",
                "distinct_candidates",
                "status",
                "alias_codes_used",
            ]
        )
        writer.writerows(rows)


def summarize(rows: List[Tuple], label: str) -> None:
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row[8]] = counts.get(row[8], 0) + 1

    print(f"{label} summary")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate council coverage audits.")
    parser.add_argument(
        "--output-dir",
        default=os.path.join("data", "election_results", "processed"),
        help="Folder where CSV reports are written.",
    )
    args = parser.parse_args()

    db_config = get_db_config()
    conn = mysql.connector.connect(**db_config)
    cur = conn.cursor(dictionary=True)

    try:
        strict_rows = build_reports(cur, alias_aware=False)
        strict_path = os.path.join(args.output_dir, "council_coverage_audit.csv")
        write_report(strict_path, strict_rows)
        summarize(strict_rows, "Strict")

        alias_rows = build_reports(cur, alias_aware=True)
        alias_path = os.path.join(args.output_dir, "council_coverage_audit_alias_aware.csv")
        write_report(alias_path, alias_rows)
        summarize(alias_rows, "Alias-aware")

        print(f"Wrote: {strict_path}")
        print(f"Wrote: {alias_path}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
