-- ============================================================================
-- Purpose: encapsulate the two known gotchas from Sprint 3 directly in SQL,
-- so the LLM cannot get them wrong:
--   1. Dedup: trip_updates is polled every ~10 min, so a trip_id has many
--      snapshot rows. Mirrors the IsLatestUpdate DAX logic from Power BI.
--   2. stop_id normalization: trip_stop_updates.stop_id occasionally carries
--      a platform-level suffix (e.g. '_3') not present in dim_stations.
--      Handled defensively - direct match first, suffix-stripped fallback
--      second - since the current sample didn't show the suffix but it may
--      appear elsewhere in the full dataset.
--
-- The text-to-SQL chain should ONLY ever be given these views, not the raw
-- tables - that's what makes the guardrail/allow-list simple later.
-- ============================================================================

DROP VIEW IF EXISTS vw_trip_stop_updates_enriched;
DROP VIEW IF EXISTS vw_latest_trip_updates;
GO

-- ----------------------------------------------------------------------------
-- 1. vw_latest_trip_updates
--    One row per trip_id: only the most recent polling snapshot.
-- ----------------------------------------------------------------------------
CREATE VIEW vw_latest_trip_updates AS
WITH ranked AS (
    SELECT
        tu.update_pk,
        tu.entity_id,
        tu.trip_id,
        tu.route_id,          -- kept for reference; often NULL, see dim_trips join in enriched view
        tu.start_date,
        tu.start_time,
        tu.trip_schedule_relationship,
        tu.vehicle_id,
        tu.vehicle_label,
        tu.license_plate,
        tu.overall_delay,
        tu.update_timestamp,
        tu.fetched_at,
        ROW_NUMBER() OVER (
            PARTITION BY tu.trip_id
            ORDER BY tu.update_timestamp DESC, tu.fetched_at DESC
        ) AS rn
    FROM trip_updates tu
)
SELECT
    update_pk,
    entity_id,
    trip_id,
    route_id,
    start_date,
    start_time,
    trip_schedule_relationship,
    vehicle_id,
    vehicle_label,
    license_plate,
    overall_delay,
    update_timestamp,
    fetched_at
FROM ranked
WHERE rn = 1;
GO

-- ----------------------------------------------------------------------------
-- 2. vw_trip_stop_updates_enriched
--    Stop-level events, restricted to each trip's latest snapshot only,
--    joined out to station/route/trip names with normalized stop_id matching.
--    This is the main table the LLM will query for delay analysis.
-- ----------------------------------------------------------------------------
CREATE VIEW vw_trip_stop_updates_enriched AS
SELECT
    tsu.id,
    tsu.update_pk,
    tsu.stop_sequence,
    tsu.stop_id                    AS raw_stop_id,
    norm.normalized_stop_id,
    ds.stop_name,
    ds.platform_code,
    tsu.arrival_time,
    tsu.arrival_delay,             -- seconds; convert to minutes in the app layer
    tsu.departure_time,
    tsu.departure_delay,           -- seconds; convert to minutes in the app layer
    tsu.schedule_relationship,     -- raw GTFS-RT int code, not yet decoded
    ltu.trip_id,
    ltu.start_date,
    ltu.start_time,
    ltu.overall_delay              AS trip_overall_delay,  -- seconds
    ltu.update_timestamp           AS snapshot_timestamp,
    dt.trip_headsign,
    dr.route_id,
    dr.route_short_name,
    dr.route_long_name,
    dr.route_type
FROM trip_stop_updates tsu
INNER JOIN vw_latest_trip_updates ltu
    ON tsu.update_pk = ltu.update_pk
CROSS APPLY (
    SELECT
        CASE
            WHEN CHARINDEX('_', tsu.stop_id) > 0
                THEN LEFT(tsu.stop_id, CHARINDEX('_', tsu.stop_id) - 1)
            ELSE tsu.stop_id
        END AS normalized_stop_id
) norm
LEFT JOIN dim_stations ds
    ON ds.stop_id = tsu.stop_id
    OR ds.stop_id = norm.normalized_stop_id
LEFT JOIN dim_trips dt
    ON dt.trip_id = ltu.trip_id
LEFT JOIN dim_routes dr
    ON dr.route_id = dt.route_id;  -- route via dim_trips, NOT trip_updates.route_id (it's NULL in your data)
GO