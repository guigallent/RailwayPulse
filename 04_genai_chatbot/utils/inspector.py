"""
One-off script to dump the exact schema of the RailPulse star schema tables
from Azure SQL, so we can write a precise CREATE VIEW for:
  1. Deduplication (latest snapshot per trip, mirroring the IsLatestUpdate
     logic from the Sprint 3 Power BI measures)
  2. stop_id normalization (trip_stop_updates uses prefixed IDs like
     'gs:nmbssncb:8864501_3', dim_stations likely uses bare numeric IDs)

Run this once, share the printed output, and I'll draft the CREATE VIEW
statements against your real column names instead of guessing.
"""

import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

# Built from the separate SQL_SERVER / SQL_DB / SQL_USER / SQL_PW vars in .env
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DB = os.getenv("SQL_DB")
SQL_USER = os.getenv("SQL_USER")
SQL_PW = os.getenv("SQL_PW")

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DB};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PW};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

TABLES = ["trip_stop_updates", "trip_updates", "dim_stations", "dim_routes", "dim_trips"]


def inspect():
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

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    for table in TABLES:
        print(f"\n{'=' * 60}\n{table}\n{'=' * 60}")
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            table,
        )
        rows = cursor.fetchall()
        if not rows:
            print(f"  (no columns found - check table name/case: {table})")
            continue
        for row in rows:
            print(f"  {row.COLUMN_NAME:<30} {row.DATA_TYPE:<15} nullable={row.IS_NULLABLE}")

    # Confirm the stop_id format mismatch with real sample data
    print(f"\n{'=' * 60}\nSample stop_id values - trip_stop_updates\n{'=' * 60}")
    try:
        cursor.execute("SELECT DISTINCT TOP 5 stop_id FROM trip_stop_updates")
        for row in cursor.fetchall():
            print(f"  {row.stop_id}")
    except Exception as e:
        print(f"  Could not query trip_stop_updates.stop_id: {e}")

    print(f"\n{'=' * 60}\nSample values - dim_stations (first 5 rows, all columns)\n{'=' * 60}")
    try:
        cursor.execute("SELECT TOP 5 * FROM dim_stations")
        cols = [d[0] for d in cursor.description]
        print(f"  columns: {cols}")
        for row in cursor.fetchall():
            print(f"  {tuple(row)}")
    except Exception as e:
        print(f"  Could not query dim_stations: {e}")

    # Confirm the timestamp column used for "latest snapshot" dedup
    print(f"\n{'=' * 60}\nSample values - trip_updates (first 5 rows, all columns)\n{'=' * 60}")
    try:
        cursor.execute("SELECT TOP 5 * FROM trip_updates")
        cols = [d[0] for d in cursor.description]
        print(f"  columns: {cols}")
        for row in cursor.fetchall():
            print(f"  {tuple(row)}")
    except Exception as e:
        print(f"  Could not query trip_updates: {e}")

    conn.close()


if __name__ == "__main__":
    inspect()