import sqlite3


def build_database(conn):
    """Builds the SQLite database by creating the necessary tables."""
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS calendar_dates")
    cursor.execute("DROP TABLE IF EXISTS calendar")
    cursor.execute("DROP TABLE IF EXISTS routes")
    cursor.execute("DROP TABLE IF EXISTS stop_times")
    cursor.execute("DROP TABLE IF EXISTS stops")
    cursor.execute("DROP TABLE IF EXISTS transfers")
    cursor.execute("DROP TABLE IF EXISTS trips")
    cursor.execute("DROP TABLE IF EXISTS translations")
    print("Dropped existing tables (if any)")

    """Creates the necessary tables in the SQLite database if they do not already exist."""

    # 1. Create the calendar_dates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_dates (
            service_id     TEXT NOT NULL,
            date           TEXT NOT NULL,
            exception_type INTEGER NOT NULL,
            PRIMARY KEY (service_id, date)
        )
    """)
    print("Created table: calendar_dates")

    # 2. Create the calendar table
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

    # 3. Create the routes table
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

    # 4. Create the stop_times table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stop_times (
            trip_id       TEXT NOT NULL,
            arrival_time  TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            drop_off_type INTEGER,
            pickup_type   INTEGER,
            stop_id       TEXT NOT NULL,
            stop_sequence INTEGER NOT NULL,
            PRIMARY KEY (trip_id, stop_sequence)
        )
    """)
    print("Created table: stop_times")

    # 5. Create the stops table
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
            PRIMARY KEY (stop_id)
        )
    """)
    print("Created table: stops")

    # 6. Create the transfers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            from_stop_id  TEXT NOT NULL,
            to_stop_id    TEXT NOT NULL,
            transfer_type INTEGER NOT NULL,
            min_transfer_time INTEGER,
            from_trip_id  TEXT,
            to_trip_id    TEXT,
            PRIMARY KEY (from_stop_id, to_stop_id)
        )
    """)
    print("Created table: transfers")

    # 7. Create the trips table
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
            PRIMARY KEY (trip_id)
        )
    """)
    print("Created table: trips")

    # 8. Create the translations table
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

def load_data_to_database(conn, calendar_dates, calendar, routes, stop_times, stops, transfers, trips, translations):
    calendar_dates.to_sql("calendar_dates", conn, if_exists="append", index=False)
    print("Loaded data into: calendar_dates")
    calendar.to_sql("calendar", conn, if_exists="append", index=False)
    print("Loaded data into: calendar")
    routes.to_sql("routes", conn, if_exists="append", index=False)
    print("Loaded data into: routes")
    stop_times.to_sql("stop_times", conn, if_exists="append", index=False)
    print("Loaded data into: stop_times")
    stops.to_sql("stops", conn, if_exists="append", index=False)
    print("Loaded data into: stops")
    transfers.to_sql("transfers", conn, if_exists="append", index=False)
    print("Loaded data into: transfers")
    trips.to_sql("trips", conn, if_exists="append", index=False)
    print("Loaded data into: trips")
    translations.to_sql("translations", conn, if_exists="append", index=False)
    print("Loaded data into: translations")
    conn.commit()
    print("All data committed to database")