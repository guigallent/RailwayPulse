# ☁️ RailPulse Cloud: Azure Challenge

[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Azure Functions](https://img.shields.io/badge/azure-functions-0078D4)](https://azure.microsoft.com/en-us/products/functions)
[![Azure SQL](https://img.shields.io/badge/database-Azure%20SQL-CC2927)](https://azure.microsoft.com/en-us/products/azure-sql/database)

## 📑 Contents
- [Description](#-description)
- [Repo structure](#-repo-structure)
- [Database structure](#-database-structure)
- [Design decisions](#-design-decisions)
- [Usage](#-usage)
- [Timeline](#️-timeline)
- [Personal situation](#-personal-situation)

## 📖 Description

**RailPulse Cloud** is the second sprint of the RailPulse project, moving from a static GTFS feed loaded into local SQLite to a cloud-native pipeline on Azure. An Azure Function (Python, Consumption plan) fetches two live feeds from the SNCB/NMBS BMC open data API — `/rt/trip-update` and `/rt/alert` — parses the JSON responses, and writes normalized rows into an Azure SQL Database (serverless tier). Static GTFS reference data (stations, routes, trips) is seeded separately into lean dimension tables, so live telemetry can be filtered and labeled by station name or ID rather than raw stop codes alone.

## 📦 Repo structure

```
azure_deployment/
├── assets/
│   └── db-structure.png
├── gtfs_static/
│   ├── routes.txt
│   ├── stops.txt
│   └── trips.txt
├── function_app.py
├── host.json
├── local.settings.json
├── queries.sql
├── README.md
├── requirements.txt
└── seed_dimensions.py
```

### 🧩 Project modules

- `function_app.py` is the Azure Function itself (Functions Python v2 model, HTTP trigger). On each invocation, it fetches both feeds from the BMC API, resolves any `station` query parameter against the seeded dimension tables, parses the JSON, and inserts rows into Azure SQL using `OUTPUT INSERTED.<pk>` to capture the generated surrogate key for each parent and use it as the foreign key on its children.
- `seed_dimensions.py` is a one-off script that parses the static GTFS `.txt` files (`stops.txt`, `routes.txt`, `trips.txt`) from `gtfs_static/` that were fetched in the `liveboard_sql` exercise and populates `dim_stations`, `dim_routes`, and `dim_trips` in Azure SQL.
- `host.json` / `local.settings.json` hold the Functions runtime configuration and local-only environment variables respectively. `local.settings.json` is gitignored and never committed.
- `queries.sql` is the schema DDL for this sprint. It drops and recreates all nine tables in Azure SQL (three static dimensions plus six real-time fact/update tables) with explicit `PRIMARY KEY` / `FOREIGN KEY` constraints. Unlike the static-feed sprint, this file defines structure rather than running analytical queries.
- `requirements.txt` lists the only external dependency, `pyodbc`, needed to connect to Azure SQL from Python.

## 🔀 Database structure

![db-structure](./assets/db-structure.png)

Nine tables cover both the static reference data and the two live feeds:

**Dimensions (GTFS-Static)**
- `dim_stations`: station/platform reference data (`stop_id`, `stop_name`, `platform_code`, `wheelchair_boarding`)
- `dim_routes`: line descriptions (`route_id`, `route_short_name`, `route_long_name`, `route_type`)
- `dim_trips`: scheduled service reference (`trip_id`, `route_id`, `trip_headsign`, `bikes_allowed`, `wheelchair_accessible`)

**Trip updates**: `trip_updates` (parent) → `trip_stop_updates` (child, one row per stop in a trip's `stopTimeUpdate` array, referencing `dim_stations.stop_id`)

**Alerts**: `service_alerts` (parent) → `alert_active_periods`, `alert_texts`, `alert_informed_entities` (children)

Parent tables in the real-time fact tables use surrogate `IDENTITY` primary keys (`update_pk`, `alert_pk`), since the child tables have optional/nullable fields that rule out a composite natural key. The dimension tables use their natural GTFS-static IDs (`stop_id`, `route_id`, `trip_id`) as primary keys.

> **Note:** The foreign key from `trip_stop_updates` to `dim_stations` is intentionally soft/non-enforced (or resolved via `LEFT JOIN` at query time rather than a hard constraint). This keeps live ingestion from failing if SNCB pushes a temporary or unscheduled stop ID that isn't in the static feed.

## 🧠 Design decisions

A few choices worth mentioning, since they were not obvious from the GTFS-RT spec alone:

- **`timestamp` arrives in two shapes.** `tripUpdate.timestamp` sometimes comes through as a plain integer and sometimes as a protobuf "Long" object (`{low, high, unsigned}`). A small parsing helper normalizes both into a proper SQL `datetime`.
- **Alerts get child tables, not flat columns**, because a single alert can have multi-language text (`fr`/`nl`/`de`/`en` via `translation` arrays on `headerText`/`descriptionText`/`url`) and multiple `activePeriod` date ranges.
- **`activePeriod` was empty for every alert observed during testing**, and `informedEntity` always contained exactly one entity. Both were checked against the raw API response to confirm this reflects the live feed's actual content rather than a parsing gap. The child tables are still there to correctly hold multiple rows if a future alert does have more than one.
- **Static dimensions are seeded separately from live ingestion.** `seed_dimensions.py` runs once (or on demand, e.g. after a GTFS-static feed update) rather than on every function invocation, since station/route/trip reference data changes far less often than live telemetry.
- **Station filtering accepts both IDs and names.** The Function's `station` query parameter is resolved by `resolve_station_ids()`: a numeric value (e.g. `8813003`) filters directly on `stop_id`, while a text value (e.g. `Bruxelles-Central`, or a partial match like `Central`) runs a `LIKE '%<input>%'` lookup against `dim_stations.stop_name` to resolve the matching `stop_id` set before filtering the live feed. This lets a single parameter support both a stable numeric code and a human-friendly, partial station name.

## 📌 Usage

1. Clone the repository and navigate to `azure_deployment/`; create a virtual environment (Python 3.12, required by the Functions Consumption plan) and install `requirements.txt`.

2. Set the following environment variables, either in `local.settings.json` for local runs or as Application Settings on the deployed Function App (the two are separate, portal settings do not apply locally, and vice versa):
   - `SQL_SERVER`, `SQL_DB`, `SQL_USER`, `SQL_PW` — Azure SQL Database connection details
   - `API_KEY` — your BMC API key ([sign up here](https://data.belgianmobility.io/en/data.html) if you don't have one)
   
3. Seed the static dimension tables (one-off, or whenever the GTFS-static feed is refreshed):
   ```bash
   python seed_dimensions.py
   ```
4. Run locally with the Azure Functions Core Tools:
   ```bash
   func start
   ```
5. Trigger the function (it is an HTTP trigger). Without a station filter, it fetches and inserts network-wide telemetry:
   ```bash
   curl "http://localhost:7071/api/<function-name>"
   ```
   Filter to a specific station by numeric stop ID:
   ```bash
   curl "http://localhost:7071/api/<function-name>?station=8813003"
   ```
   Or by station name (full or partial):
   ```bash
   curl "http://localhost:7071/api/<function-name>?station=Bruxelles-Central"
   ```
   A successful run returns a small JSON summary, e.g.:
   ```json
   {
     "status": "ok",
     "station_filter": "Bruxelles-Central",
     "resolved_stop_ids_count": 1,
     "total_trips_fetched": 170,
     "trips_inserted": 49,
     "alerts_processed": 33
   }
   ```
6. To deploy: use the Azure Functions extension in VS Code (`Azure Functions: Deploy to Function App...`) against an already-provisioned Function App (Consumption plan, Python runtime) and Azure SQL Database (serverless tier), with the same Application Settings as step 2 configured in the portal.

## ⏱️ Timeline

This sprint was completed over 4 days.

## 📌 Personal situation

This project was done as part of the AI & Data Science Bootcamp at BeCode.

👥 Connect with me via [LinkedIn](https://www.linkedin.com/in/guillermo-gallent/).