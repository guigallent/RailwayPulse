import sqlite3
from src.clean import prepare_rows

# Column definitions per table, in schema order, used to cast raw CSV
# string values to the right SQL type before insertion. This is the only
# thing standing in for pandas' automatic dtype handling.
TABLE_SCHEMAS = {
    "routes": [
        ("route_id", "str"),
        ("agency_id", "str"),
        ("route_short_name", "str"),
        ("route_long_name", "str"),
        ("route_type", "int"),
        ("route_color", "str"),
        ("route_text_color", "str"),
    ],
    "calendar": [
        ("service_id", "str"),
        ("monday", "int"),
        ("tuesday", "int"),
        ("wednesday", "int"),
        ("thursday", "int"),
        ("friday", "int"),
        ("saturday", "int"),
        ("sunday", "int"),
        ("start_date", "str"),
        ("end_date", "str"),
    ],
    "stops": [
        ("stop_id", "str"),
        ("stop_name", "str"),
        ("stop_lat", "float"),
        ("stop_lon", "float"),
        ("location_type", "int"),
        ("parent_station", "str"),
        ("platform_code", "str"),
        ("stop_desc", "str"),
    ],
    "calendar_dates": [
        ("service_id", "str"),
        ("date", "str"),
        ("exception_type", "int"),
    ],
    "trips": [
        ("route_id", "str"),
        ("service_id", "str"),
        ("trip_id", "str"),
        ("trip_headsign", "str"),
        ("block_id", "str"),
        ("bikes_allowed", "int"),
        ("wheelchair_accessible", "int"),
        ("trip_short_name", "str"),
    ],
    "stop_times": [
        ("trip_id", "str"),
        ("arrival_time", "str"),
        ("departure_time", "str"),
        ("drop_off_type", "int"),
        ("pickup_type", "int"),
        ("stop_id", "str"),
        ("stop_sequence", "int"),
    ],
    "transfers": [
        ("from_stop_id", "str"),
        ("to_stop_id", "str"),
        ("transfer_type", "int"),
        ("min_transfer_time", "int"),
        ("from_trip_id", "str"),
        ("to_trip_id", "str"),
    ],
    "translations": [
        ("table_name", "str"),
        ("field_name", "str"),
        ("field_value", "str"),
        ("language", "str"),
        ("translation", "str"),
    ],
}


def build_database(conn):
    """Builds the SQLite database by creating the necessary tables."""
    cursor = conn.cursor()

    # Drop in reverse dependency order (children before parents)
    cursor.execute("DROP TABLE IF EXISTS translations")
    cursor.execute("DROP TABLE IF EXISTS transfers")
    cursor.execute("DROP TABLE IF EXISTS stop_times")
    cursor.execute("DROP TABLE IF EXISTS trips")
    cursor.execute("DROP TABLE IF EXISTS calendar_dates")
    cursor.execute("DROP TABLE IF EXISTS stops")
    cursor.execute("DROP TABLE IF EXISTS calendar")
    cursor.execute("DROP TABLE IF EXISTS routes")
    print("Dropped existing tables (if any)")

    """Creates the necessary tables in the SQLite database if they do not already exist."""

    # 1. Create the routes table (no dependencies)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            route_id     TEXT NOT NULL,
            agency_id    TEXT,
            route_short_name TEXT,
            route_long_name  TEXT,
            route_type   INTEGER NOT NULL,
            route_color  TEXT,
            route_text_color TEXT,
            PRIMARY KEY (route_id)
        )
    """)
    print("Created table: routes")

    # 2. Create the calendar table (no dependencies)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendar (
            service_id   TEXT NOT NULL,
            monday       INTEGER NOT NULL,
            tuesday      INTEGER NOT NULL,
            wednesday    INTEGER NOT NULL,
            thursday     INTEGER NOT NULL,
            friday       INTEGER NOT NULL,
            saturday     INTEGER NOT NULL,
            sunday       INTEGER NOT NULL,
            start_date   TEXT NOT NULL,
            end_date     TEXT NOT NULL,
            PRIMARY KEY (service_id)
        )
    """)
    print("Created table: calendar")

    # 3. Create the stops table (self-referencing via parent_station)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stops (
            stop_id       TEXT NOT NULL,
            stop_name     TEXT NOT NULL,
            stop_lat      REAL NOT NULL,
            stop_lon      REAL NOT NULL,
            location_type INTEGER NOT NULL,
            parent_station TEXT,
            platform_code TEXT,
            stop_desc      TEXT,
            PRIMARY KEY (stop_id),
            FOREIGN KEY (parent_station) REFERENCES stops (stop_id)
        )
    """)
    print("Created table: stops")

    # 4. Create the calendar_dates table (depends on calendar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_dates (
            service_id     TEXT NOT NULL,
            date           TEXT NOT NULL,
            exception_type INTEGER NOT NULL,
            PRIMARY KEY (service_id, date),
            FOREIGN KEY (service_id) REFERENCES calendar (service_id)
        )
    """)
    print("Created table: calendar_dates")

    # 5. Create the trips table (depends on routes and calendar)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            route_id      TEXT NOT NULL,
            service_id    TEXT NOT NULL,
            trip_id       TEXT NOT NULL,
            trip_headsign TEXT,
            block_id      TEXT,
            bikes_allowed INTEGER,
            wheelchair_accessible INTEGER,
            trip_short_name TEXT,
            PRIMARY KEY (trip_id),
            FOREIGN KEY (route_id) REFERENCES routes (route_id),
            FOREIGN KEY (service_id) REFERENCES calendar (service_id)
        )
    """)
    print("Created table: trips")

    # 6. Create the stop_times table (depends on trips and stops)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stop_times (
            trip_id       TEXT NOT NULL,
            arrival_time  TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            drop_off_type INTEGER,
            pickup_type   INTEGER,
            stop_id       TEXT NOT NULL,
            stop_sequence INTEGER NOT NULL,
            PRIMARY KEY (trip_id, stop_sequence),
            FOREIGN KEY (trip_id) REFERENCES trips (trip_id),
            FOREIGN KEY (stop_id) REFERENCES stops (stop_id)
        )
    """)
    print("Created table: stop_times")

    # 7. Create the transfers table (depends on stops)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            from_stop_id  TEXT NOT NULL,
            to_stop_id    TEXT NOT NULL,
            transfer_type INTEGER NOT NULL,
            min_transfer_time INTEGER,
            from_trip_id  TEXT,
            to_trip_id    TEXT,
            PRIMARY KEY (from_stop_id, to_stop_id),
            FOREIGN KEY (from_stop_id) REFERENCES stops (stop_id),
            FOREIGN KEY (to_stop_id) REFERENCES stops (stop_id)
        )
    """)
    print("Created table: transfers")

    # 8. Create the translations table (no clear FK target - generic key/value)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            table_name    TEXT NOT NULL,
            field_name    TEXT NOT NULL,
            field_value   TEXT NOT NULL,
            language      TEXT NOT NULL,
            translation   TEXT NOT NULL,
            PRIMARY KEY (table_name, field_name, field_value, language)
        )
    """)
    print("Created table: translations")

    conn.commit()
    print("All tables committed to database")


def insert_rows(conn, table_name, rows):
    """Inserts a list of dicts into a table using raw sqlite3 executemany.
    """
    if not rows:
        print(f"  -> No rows to insert into {table_name}, skipping")
        return

    columns = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"

    values = [tuple(row[c] for c in columns) for row in rows]
    conn.executemany(sql, values)


def load_data_to_database(conn, calendar_dates, calendar, routes, stop_times,
                           stops, transfers, trips, translations):
    """Casts each raw (string-valued) row list to its table's schema and
    inserts it via raw SQL, in dependency order (parents before children).
    """
    raw_tables = {
        "routes": routes,
        "calendar": calendar,
        "stops": stops,
        "calendar_dates": calendar_dates,
        "trips": trips,
        "stop_times": stop_times,
        "transfers": transfers,
        "translations": translations,
    }

    # Dependency order matters for FK integrity even without PRAGMA
    # foreign_keys = ON.
    for table_name in ["routes", "calendar", "stops", "calendar_dates",
                        "trips", "stop_times", "transfers", "translations"]:
        prepared = prepare_rows(raw_tables[table_name], TABLE_SCHEMAS[table_name])
        insert_rows(conn, table_name, prepared)
        print(f"Loaded data into: {table_name}")

    conn.commit()
    print("All data committed to database")