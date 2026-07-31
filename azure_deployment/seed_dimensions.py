import csv
import os
import time
import pyodbc
import json

_script_dir = os.path.dirname(os.path.abspath(__file__))
_settings_path = os.path.join(_script_dir, "local.settings.json")

with open(_settings_path, "r", encoding="utf-8") as f:
    _settings = json.load(f)["Values"]

SQL_SERVER = _settings["SQL_SERVER"]
SQL_DB = _settings["SQL_DB"]
SQL_USER = _settings["SQL_USER"]
SQL_PW = _settings["SQL_PW"]

# ── 1. Database Connection Configuration ─────────────────────────────────────

def get_connection():
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SQL_SERVER},1433;"
        f"Database={SQL_DB};"
        f"Uid={SQL_USER};"
        f"Pwd={SQL_PW};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
    )
    return pyodbc.connect(conn_str)


# ── 2. Data Cleaning Helpers ──────────────────────────────────────────────────

def clean_str(val, max_length=None):
    """Trims whitespace, converts empty strings to None (SQL NULL),
    and safely truncates to fit column constraints.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if max_length and len(s) > max_length:
        return s[:max_length]
    return s


def clean_int(val):
    """Safely converts GTFS integer fields to Python int or None."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or not s.isdigit():
        return None
    return int(s)


# ── 3. Bulk Insert Runners ───────────────────────────────────────────────────

def load_stations(cursor, file_path):
    print(f"Loading stations from {file_path}...")
    sql = """
        INSERT INTO dbo.dim_stations
            (stop_id, stop_name, parent_station, platform_code, wheelchair_boarding)
        VALUES (?, ?, ?, ?, ?)
    """
    rows = []
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                clean_str(row.get("stop_id"), 50),
                clean_str(row.get("stop_name"), 150) or "Unknown Station",
                clean_str(row.get("parent_station"), 50),
                clean_str(row.get("platform_code"), 20),
                clean_int(row.get("wheelchair_boarding")),
            ))

    cursor.executemany(sql, rows)
    print(f"  └─ Inserted {len(rows):,} records into dbo.dim_stations.")


def load_routes(cursor, file_path):
    print(f"Loading routes from {file_path}...")
    sql = """
        INSERT INTO dbo.dim_routes
            (route_id, agency_id, route_short_name, route_long_name, route_type)
        VALUES (?, ?, ?, ?, ?)
    """
    rows = []
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                clean_str(row.get("route_id"), 50),
                clean_str(row.get("agency_id"), 30),
                clean_str(row.get("route_short_name"), 50),
                clean_str(row.get("route_long_name"), 200),
                clean_int(row.get("route_type")) or 2,  # Default 2 = Rail
            ))

    cursor.executemany(sql, rows)
    print(f"  └─ Inserted {len(rows):,} records into dbo.dim_routes.")


def load_trips(cursor, file_path, batch_size=10000):
    print(f"Loading static trips from {file_path}...")
    sql = """
        INSERT INTO dbo.dim_trips
            (trip_id, route_id, service_id, trip_headsign, bikes_allowed, wheelchair_accessible)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    
    # First, collect valid route_ids to enforce foreign key integrity
    cursor.execute("SELECT route_id FROM dbo.dim_routes")
    valid_route_ids = {row[0] for row in cursor.fetchall()}

    rows = []
    total_inserted = 0
    skipped_orphan_trips = 0

    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            route_id = clean_str(row.get("route_id"), 50)
            
            # Skip trip if route_id is not in dim_routes to prevent FK error
            if route_id not in valid_route_ids:
                skipped_orphan_trips += 1
                continue

            rows.append((
                clean_str(row.get("trip_id"), 100),
                route_id,
                clean_str(row.get("service_id"), 50) or "UNKNOWN",
                clean_str(row.get("trip_headsign"), 150),
                clean_int(row.get("bikes_allowed")),
                clean_int(row.get("wheelchair_accessible")),
            ))

            # Batch execution for memory management on large files
            if len(rows) >= batch_size:
                cursor.executemany(sql, rows)
                total_inserted += len(rows)
                rows = []

        if rows:
            cursor.executemany(sql, rows)
            total_inserted += len(rows)

    print(f"  └─ Inserted {total_inserted:,} records into dbo.dim_trips.")
    if skipped_orphan_trips > 0:
        print(f"  └─ Skipped {skipped_orphan_trips:,} trips due to missing route_id in dim_routes.")


# ── 4. Main Execution Flow ───────────────────────────────────────────────────

def main():
    gtfs_dir = "./azure_deployment/gtfs_static"  
    
    stops_file = os.path.join(gtfs_dir, "stops.txt")
    routes_file = os.path.join(gtfs_dir, "routes.txt")
    trips_file = os.path.join(gtfs_dir, "trips.txt")

    # Verification of files
    for file_path in [stops_file, routes_file, trips_file]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing required GTFS file: {file_path}")

    start_time = time.time()
    print("Connecting to Azure SQL Database...")
    conn = get_connection()
    cursor = conn.cursor()

    # Enable fast_executemany for high-speed bulk inserts
    cursor.fast_executemany = True

    try:
        print("Clearing old dimension data...")
        # Clear in order of Foreign Key dependencies
        cursor.execute("DELETE FROM dbo.dim_trips")
        cursor.execute("DELETE FROM dbo.dim_routes")
        cursor.execute("DELETE FROM dbo.dim_stations")
        conn.commit()

        # Insert dimensions in order (Parent tables first)
        load_stations(cursor, stops_file)
        load_routes(cursor, routes_file)
        load_trips(cursor, trips_file)

        print("Committing transaction...")
        conn.commit()
        print(f"Successfully populated static GTFS dimensions in {time.time() - start_time:.2f} seconds!")

    except Exception as e:
        print(f"\n[ERROR] Transaction failed: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()