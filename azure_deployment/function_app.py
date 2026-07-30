import json
import logging
import os
import urllib.request
from datetime import datetime, timezone

import azure.functions as func
import pyodbc

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

BASE_URL = "https://api-management-opendata-production.azure-api.net/api/gtfs/feed/nmbssncb/rt/"


# ── Helpers ──────────────────────────────────────────────────────────────

def parse_long(value):
    """Some int64 fields (e.g. tripUpdate.timestamp) arrive as a plain int,
    others as a protobuf Long object {low, high, unsigned}. 
    This normalizes either into a plain int.
    """

    if value is None:
        return None
    if isinstance(value, dict):
        low = value.get("low", 0) & 0xFFFFFFFF
        high = value.get("high", 0)
        return (high << 32) | low
    return int(value)


def epoch_to_datetime(value):
    """Converts a GTFS-RT epoch-seconds value to a
    naive UTC datetime, ready for a DATETIME2 column.
    """

    epoch = parse_long(value)
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)


def fetch_feed(feed_name):
    """Fetches one GTFS-RT feed and returns its
    list of entities. Raises on a non-200 response.
    """

    url = BASE_URL + feed_name + "/"
    headers = {
        "Cache-Control": "no-cache",
        "bmc-partner-key": os.environ["API_KEY"],
    }
    req = urllib.request.Request(url, headers=headers, method="GET")

    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            raise RuntimeError(f"{feed_name} fetch failed with status {response.getcode()}")
        payload = json.loads(response.read().decode("utf-8"))

    return payload.get("entity", [])


def get_connection():
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{os.environ['SQL_SERVER']},1433;"
        f"Database={os.environ['SQL_DB']};"
        f"Uid={os.environ['SQL_USER']};"
        f"Pwd={os.environ['SQL_PW']};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


# ── Trip updates ─────────────────────────────────────────────────────────

def insert_trip_updates(cursor, entities):
    for ent in entities:
        tu = ent.get("tripUpdate")
        if not tu:
            continue

        trip = tu.get("trip", {}) or {}
        vehicle = tu.get("vehicle", {}) or {}

        cursor.execute(
            """
            INSERT INTO dbo.trip_updates
                (entity_id, trip_id, route_id, start_date, start_time,
                 trip_schedule_relationship, vehicle_id, vehicle_label,
                 license_plate, overall_delay, update_timestamp)
            OUTPUT INSERTED.update_pk
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ent.get("id"),
            trip.get("tripId"),
            trip.get("routeId"),
            trip.get("startDate"),
            trip.get("startTime"),
            trip.get("scheduleRelationship"),
            vehicle.get("id"),
            vehicle.get("label"),
            vehicle.get("licensePlate"),
            tu.get("delay"),
            epoch_to_datetime(tu.get("timestamp")),
        )
        update_pk = cursor.fetchone()[0]

        for stu in tu.get("stopTimeUpdate", []):
            arrival = stu.get("arrival", {}) or {}
            departure = stu.get("departure", {}) or {}

            cursor.execute(
                """
                INSERT INTO dbo.trip_stop_updates
                    (update_pk, stop_sequence, stop_id, arrival_time,
                     arrival_delay, departure_time, departure_delay,
                     schedule_relationship)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                update_pk,
                stu.get("stopSequence"),
                stu.get("stopId"),
                epoch_to_datetime(arrival.get("time")),
                arrival.get("delay"),
                epoch_to_datetime(departure.get("time")),
                departure.get("delay"),
                stu.get("scheduleRelationship"),
            )


# ── Alerts ───────────────────────────────────────────────────────────────

def insert_alerts(cursor, entities):
    for ent in entities:
        alert = ent.get("alert")
        if not alert:
            continue

        cursor.execute(
            """
            INSERT INTO dbo.service_alerts (entity_id, cause, effect)
            OUTPUT INSERTED.alert_pk
            VALUES (?, ?, ?)
            """,
            ent.get("id"),
            alert.get("cause"),
            alert.get("effect"),
        )
        alert_pk = cursor.fetchone()[0]

        for period in alert.get("activePeriod", []):
            cursor.execute(
                """
                INSERT INTO dbo.alert_active_periods (alert_pk, period_start, period_end)
                VALUES (?, ?, ?)
                """,
                alert_pk,
                epoch_to_datetime(period.get("start")),
                epoch_to_datetime(period.get("end")),
            )

        text_fields = {
            "header": alert.get("headerText") or {},
            "description": alert.get("descriptionText") or {},
            "url": alert.get("url") or {},
        }
        for field_name, field_obj in text_fields.items():
            for translation in field_obj.get("translation", []):
                cursor.execute(
                    """
                    INSERT INTO dbo.alert_texts (alert_pk, field_name, language, text_value)
                    VALUES (?, ?, ?, ?)
                    """,
                    alert_pk,
                    field_name,
                    translation.get("language"),
                    translation.get("text"),
                )

        for informed in alert.get("informedEntity", []):
            trip = informed.get("trip", {}) or {}
            cursor.execute(
                """
                INSERT INTO dbo.alert_informed_entities
                    (alert_pk, agency_id, route_id, route_type, trip_id,
                     trip_start_date, trip_start_time,
                     trip_schedule_relationship, stop_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                alert_pk,
                informed.get("agencyId"),
                informed.get("routeId"),
                informed.get("routeType"),
                trip.get("tripId"),
                trip.get("startDate"),
                trip.get("startTime"),
                trip.get("scheduleRelationship"),
                informed.get("stopId"),
            )


# ── HTTP trigger ─────────────────────────────────────────────────────────

@app.route(route="fetch_liveboard", methods=["GET", "POST"])
def fetch_liveboard(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Starting liveboard fetch")

    try:
        trip_entities = fetch_feed("trip-update")
        alert_entities = fetch_feed("alert")

        conn = get_connection()
        cursor = conn.cursor()

        insert_trip_updates(cursor, trip_entities)
        insert_alerts(cursor, alert_entities)

        conn.commit()
        cursor.close()
        conn.close()

        return func.HttpResponse(
            json.dumps({
                "status": "ok",
                "trip_updates_processed": len(trip_entities),
                "alerts_processed": len(alert_entities),
            }),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as exc:
        logging.exception("Liveboard fetch failed")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(exc)}),
            mimetype="application/json",
            status_code=500,
        )