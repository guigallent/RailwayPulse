import os
import io
import zipfile
import urllib.request

API_URL = "https://api-management-opendata-production.azure-api.net/api/gtfs/feed/nmbssncb/static/"


def download_gtfs_feed(url, api_key, extract_to):
    """Downloads the latest static GTFS zip from the BMC open data API
    and extracts its contents directly into `extract_to`.
    """
    headers = {
        "Cache-Control": "no-cache",
        "bmc-partner-key": api_key,
    }
    req = urllib.request.Request(url, headers=headers, method="GET")

    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            raise RuntimeError(f"GTFS download failed with status {response.getcode()}")
        data = response.read()

    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(extract_to)

    print(f"Downloaded and extracted latest GTFS feed to {extract_to}")


def extract_local_zip(zip_path, extract_to):
    """Extracts an already-downloaded GTFS zip sitting on disk into
    `extract_to`, instead of hitting the API.
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(
            f"No zip file found at {zip_path}. Place the GTFS zip there, "
            "or choose the API option instead."
        )

    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_to)

    print(f"Extracted existing local GTFS feed ({zip_path}) to {extract_to}")