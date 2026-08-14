import os
import getpass
import sqlite3
from src.clean import read_csv_file, drop_empty_columns
from src.build import build_database, load_data_to_database
from src.fetch import download_gtfs_feed, extract_local_zip, API_URL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw", "sncb")
DB_PATH = os.path.join(BASE_DIR, "data", "railwaypulse.db")
LOCAL_ZIP_PATH = os.path.join(BASE_DIR, "data", "raw", "sncb", "railwaypulse.zip")

# Ask the user whether to reuse the bundled GTFS zip or fetch a fresh one from the API
choice = input(
    "Use (1) the existing local .zip file, or (2) fetch the latest feed from the API? [1/2]: "
).strip()

if choice == "2":
    # Check the environment first so people who *have* set BMC_API_KEY
    # (e.g. via .env) aren't prompted unnecessarily; everyone else is
    # asked to paste their own key in on the spot.
    api_key = os.environ.get("BMC_API_KEY") or getpass.getpass(
        "Enter your BMC API key (input hidden, get your own at "
        "https://data.belgianmobility.io/en/data.html): "
    )
    if not api_key:
        raise ValueError("No API key provided — please run again and enter a valid key.")

    download_gtfs_feed(API_URL, api_key, DATA_DIR)
elif choice == "1":
    extract_local_zip(LOCAL_ZIP_PATH, DATA_DIR)
else:
    raise ValueError("Invalid choice — please run again and enter 1 or 2.")

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