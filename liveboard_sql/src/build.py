import sqlite3



def build_database(conn):
    cursor = conn.cursor()
    
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
    conn.commit()

def load_data_to_database(conn, calendar_dates, calendar, routes, stop_times, stops, transfers, trips, translations):
    calendar_dates.to_sql("calendar_dates", conn, if_exists="append", index=False)
    calendar.to_sql("calendar", conn, if_exists="append", index=False)
    routes.to_sql("routes", conn, if_exists="append", index=False)
    stop_times.to_sql("stop_times", conn, if_exists="append", index=False)
    stops.to_sql("stops", conn, if_exists="append", index=False)
    transfers.to_sql("transfers", conn, if_exists="append", index=False)
    trips.to_sql("trips", conn, if_exists="append", index=False)
    translations.to_sql("translations", conn, if_exists="append", index=False)
    conn.commit()