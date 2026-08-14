"""
One-time export of the Azure SQL reporting views into a local SQLite file.

Run this once now, and optionally re-run it later for a fresher snapshot
before you disable the Azure Function's polling trigger. After this, the
chatbot's DB layer points entirely at the local .db file - Azure SQL is no
longer needed for day-to-day development or the final demo, so there's no
further credit risk.

Table names in SQLite intentionally match the Azure view names
(vw_trip_stop_updates_enriched, vw_latest_trip_updates) so prompts.py's
SCHEMA_CONTEXT and ALLOWED_VIEWS don't need to change at all.
"""

import os
import csv
import sqlite3
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent  # one level up from utils/ - see PATHS block below

load_dotenv(REPO_ROOT / ".env")

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DB = os.getenv("SQL_DB")
SQL_USER = os.getenv("SQL_USER")
SQL_PW = os.getenv("SQL_PW")

    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DB};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PW};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

# ----------------------------------------------------------------------------
# PATHS - anchored to this file's own location (THIS_DIR/REPO_ROOT defined
# above, near the .env loading), not the working directory you happen to
# run the script from. If you move this script or reorganize the repo,
# adjust the .parent count in REPO_ROOT above to match the new depth - that
# single line is all that needs to change.
# ----------------------------------------------------------------------------
SQLITE_PATH = str(REPO_ROOT / "railpulse_snapshot.db")

# Standard GTFS translations.txt from Sprint 1, expected in the same folder
# as this script. Columns: table_name, field_name, record_id, record_sub_id,
# field_value, language, translation. Station names elsewhere in the data
# are French (field_value); this builds a French -> nl/de/en lookup table.
TRANSLATIONS_PATH = str(THIS_DIR / "translations.txt")

# Prototype constraint: only Aug 5, 2026 has enough properly-populated live
# polling data. This is a temporary scoping decision (not a data-quality
# fix like the views), so it lives here in the export step - easy to widen
# or remove once more days of live data are collected. Format: YYYYMMDD,
# matching trip_updates.start_date.
PROTOTYPE_DATE = "20260805"

CREATE_ENRICHED = """
CREATE TABLE IF NOT EXISTS vw_trip_stop_updates_enriched (
    id INTEGER,
    update_pk INTEGER,
    stop_sequence INTEGER,
    raw_stop_id TEXT,
    normalized_stop_id TEXT,
    stop_name TEXT,
    platform_code TEXT,
    arrival_time TEXT,
    arrival_delay INTEGER,
    departure_time TEXT,
    departure_delay INTEGER,
    schedule_relationship INTEGER,
    trip_id TEXT,
    start_date TEXT,
    start_time TEXT,
    trip_overall_delay INTEGER,
    snapshot_timestamp TEXT,
    trip_headsign TEXT,
    route_id TEXT,
    route_short_name TEXT,
    route_long_name TEXT,
    route_type INTEGER
);
"""

CREATE_LATEST = """
CREATE TABLE IF NOT EXISTS vw_latest_trip_updates (
    update_pk INTEGER,
    entity_id TEXT,
    trip_id TEXT,
    route_id TEXT,
    start_date TEXT,
    start_time TEXT,
    trip_schedule_relationship INTEGER,
    vehicle_id TEXT,
    vehicle_label TEXT,
    license_plate TEXT,
    overall_delay INTEGER,
    update_timestamp TEXT,
    fetched_at TEXT
);
"""

TABLES = {
    "vw_trip_stop_updates_enriched": CREATE_ENRICHED,
    "vw_latest_trip_updates": CREATE_LATEST,
}


def stringify_row(row):
    """Convert datetime/other non-primitive values to plain strings for sqlite."""
    out = []
    for val in row:
        if hasattr(val, "isoformat"):
            out.append(val.isoformat(sep=" "))
        else:
            out.append(val)
    return tuple(out)


def build_station_translations(sqlite_cursor):
    """Build a French -> nl/de/en station name lookup from translations.txt.

    One row per station (unlike the GTFS-RT tables, this isn't sourced from
    Azure - it's a static reference file from Sprint 1).
    """
    print(f"\n--- station_translations (from {TRANSLATIONS_PATH}) ---")

    if not os.path.exists(TRANSLATIONS_PATH):
        print(f"  WARNING: {TRANSLATIONS_PATH} not found next to this script - skipping")
        return

    stations = {}
    with open(TRANSLATIONS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["table_name"] != "stops" or row["field_name"] != "stop_name":
                continue
            fr_name = row["field_value"]
            lang = row["language"]
            stations.setdefault(fr_name, {})[lang] = row["translation"]

    sqlite_cursor.execute("DROP TABLE IF EXISTS station_translations")
    sqlite_cursor.execute(
        """
        CREATE TABLE station_translations (
            stop_name_fr TEXT PRIMARY KEY,
            stop_name_nl TEXT,
            stop_name_de TEXT,
            stop_name_en TEXT
        )
        """
    )

    rows = [
        (fr_name, langs.get("nl"), langs.get("de"), langs.get("en"))
        for fr_name, langs in stations.items()
    ]
    sqlite_cursor.executemany(
        """
        INSERT INTO station_translations
            (stop_name_fr, stop_name_nl, stop_name_de, stop_name_en)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    print(f"  wrote {len(rows)} station rows")


def export():
    missing = [
        name
        for name, val in [
            ("SQL_SERVER", SQL_SERVER),
            ("SQL_DB", SQL_DB),
            ("SQL_USER", SQL_USER),
            ("SQL_PW", SQL_PW),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing env vars: {missing}. Check your .env file.")

    print("Connecting to Azure SQL...")
    azure_conn = pyodbc.connect(AZURE_CONN_STR)
    azure_cursor = azure_conn.cursor()

    print(f"Creating local SQLite file: {SQLITE_PATH}")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cursor = sqlite_conn.cursor()

    for table_name, create_sql in TABLES.items():
        print(f"\n--- {table_name} ---")

        sqlite_cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        sqlite_cursor.execute(create_sql)

        azure_cursor.execute(
            f"SELECT * FROM {table_name} WHERE start_date = ?", PROTOTYPE_DATE
        )
        columns = [d[0] for d in azure_cursor.description]
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        rows = azure_cursor.fetchall()
        print(f"  fetched {len(rows)} rows from Azure")

        clean_rows = [stringify_row(r) for r in rows]
        sqlite_cursor.executemany(insert_sql, clean_rows)
        sqlite_conn.commit()

        local_count = sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  wrote {local_count} rows to SQLite")

        if local_count != len(rows):
            print(f"  WARNING: row count mismatch! Azure={len(rows)} SQLite={local_count}")

    build_station_translations(sqlite_cursor)
    sqlite_conn.commit()

    azure_conn.close()
    sqlite_conn.close()
    print(f"\nDone. Snapshot saved to {SQLITE_PATH}")


if __name__ == "__main__":
    export()