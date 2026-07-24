import os
import sqlite3
from src.clean import read_csv_file, drop_empty_columns
from src.build import build_database, load_data_to_database

# Anchor all paths to this script's location, so it works regardless of
# which directory you run "python main.py" from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw", "sncb")
DB_PATH = os.path.join(BASE_DIR, "data", "railwaypulse.db")

# Load data from GTFS .txt files using the stdlib csv module

calendar_dates = read_csv_file(os.path.join(DATA_DIR, "calendar_dates.txt"))
print("Loaded calendar_dates.txt")
calendar = read_csv_file(os.path.join(DATA_DIR, "calendar.txt"))
print("Loaded calendar.txt")
routes = read_csv_file(os.path.join(DATA_DIR, "routes.txt"))
print("Loaded routes.txt")
stop_times = read_csv_file(os.path.join(DATA_DIR, "stop_times.txt"))
print("Loaded stop_times.txt")
stops = read_csv_file(os.path.join(DATA_DIR, "stops.txt"))
print("Loaded stops.txt")
transfers = read_csv_file(os.path.join(DATA_DIR, "transfers.txt"))
print("Loaded transfers.txt")
translations = read_csv_file(os.path.join(DATA_DIR, "translations.txt"))
print("Loaded translations.txt")
trips = read_csv_file(os.path.join(DATA_DIR, "trips.txt"))
print("Loaded trips.txt")

# Delete empty columns with no values
stop_times = drop_empty_columns(stop_times)
print("Dropped empty columns from stop_times")
routes = drop_empty_columns(routes)
print("Dropped empty columns from routes")
stops = drop_empty_columns(stops)
print("Dropped empty columns from stops")
trips = drop_empty_columns(trips)
print("Dropped empty columns from trips")
translations = drop_empty_columns(translations)
print("Dropped empty columns from translations")

# Create database connection
conn = sqlite3.connect(DB_PATH)
print("Connected to database at", DB_PATH)

# Build the database and load data into it
build_database(conn)
print("Database tables built")
load_data_to_database(conn, calendar_dates, calendar, routes, stop_times, stops, transfers, trips, translations)
print("Data loaded into all tables")

# Close the database connection
conn.close()
print("Database connection closed")

print("Database created and data loaded successfully.")