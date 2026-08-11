-- 1. The Peak Hour Problem: What hour of the day experiences the highest volume of scheduled train departures across the entire network?

SELECT
    strftime('%H', st.departure_time) AS departure_hour,
    COUNT(*) AS departure_count
FROM
    stop_times st
JOIN
    trips t ON st.trip_id = t.trip_id
JOIN
    routes r ON t.route_id = r.route_id
WHERE
    r.route_type = 2
GROUP BY
    departure_hour
ORDER BY
    departure_count DESC
LIMIT 3

-- Result of the query: [('10', 136043), ('09', 132435), ('11', 132222)]


-- 2. Platform Bottlenecks: Identify the top 3 busiest platforms in Brussels-Central.

SELECT
    s.platform_code,
    COUNT(*) AS platform_usage_count
FROM
    stop_times st
JOIN
    stops s ON st.stop_id = s.stop_id
WHERE
    s.parent_station IN (
        SELECT stop_id
        FROM stops
        WHERE stop_name LIKE '%Bruxelles-Central%'
    )
    AND s.platform_code IS NOT NULL
GROUP BY
    s.platform_code
ORDER BY
    platform_usage_count DESC
LIMIT 3

-- Result of the query: [('3', 11982), ('4', 10515), ('2', 7473)]


-- 3. Busiest Morning Destinations: Find the top 3 most frequent terminal destinations (trip_headsign) for all morning trips that depart before 12:00:00 PM.

SELECT
    t.trip_headsign,
    COUNT(DISTINCT t.trip_id) AS trip_count
FROM
    trips t
JOIN
    stop_times st ON t.trip_id = st.trip_id
WHERE
    st.stop_sequence = (
        SELECT MIN(st2.stop_sequence)
        FROM stop_times st2
        WHERE st2.trip_id = st.trip_id
    )
    AND st.departure_time < '12:00:00'
GROUP BY
    t.trip_headsign
ORDER BY
    trip_count DESC
LIMIT 3

-- Result of the query: [('Anvers-Central', 3930), ('Bruxelles-Midi', 3150), ('Louvain', 2505)]


-- 4. Service Frequency: Classify each active service ID into a weekly frequency category using a CASE WHEN statement. 
-- If a service operates 5 or more days a week, classify it as "High Frequency"; 
-- if 2–4 days, "Medium Frequency"; 
-- and if 1 day or completely irregular, "Low Frequency/Special". 
-- Show the percentage of services in each category.


-- NOTES: calendar.monday..sunday is all 0 in this feed, so the weekly pattern has
-- to be derived from calendar_dates instead. This uses each service's MODAL
-- (most common) days-per-active-week, so one unusual week (a holiday dip,
-- a one-off bulge) doesn't distort its classification.

WITH service_dates AS (
    -- Convert GTFS YYYYMMDD strings to ISO dates SQLite's date functions understand
    SELECT
        service_id,
        date(substr(date, 1, 4) || '-' || substr(date, 5, 2) || '-' || substr(date, 7, 2)) AS iso_date
    FROM calendar_dates
    WHERE exception_type = 1  -- ADDED dates only
),
service_weeks AS (
    -- Bucket each date into a Monday-Sunday week, counted from a fixed
    -- Monday epoch (2024-01-01) rather than strftime('%W'), which resets
    -- at each Jan 1 and would split a week straddling year-end in two.
    SELECT
        service_id,
        CAST((julianday(iso_date) - julianday('2024-01-01')) / 7 AS INTEGER) AS week_bucket
    FROM service_dates
),
days_per_week AS (
    -- How many days this service ran in each of its active weeks
    SELECT
        service_id,
        week_bucket,
        COUNT(*) AS operating_days
    FROM service_weeks
    GROUP BY service_id, week_bucket
),
mode_counts AS (
    -- How often each days-per-week value recurs for this service
    SELECT
        service_id,
        operating_days,
        COUNT(*) AS weeks_with_this_count
    FROM days_per_week
    GROUP BY service_id, operating_days
),
ranked_modes AS (
    -- Pick the most frequent value per service; ties broken toward the
    -- higher day count
    SELECT
        service_id,
        operating_days,
        ROW_NUMBER() OVER (
            PARTITION BY service_id
            ORDER BY weeks_with_this_count DESC, operating_days DESC
        ) AS rn
    FROM mode_counts
),
service_frequency AS (
    SELECT service_id, operating_days AS typical_days_per_week
    FROM ranked_modes
    WHERE rn = 1
),
classified AS (
    SELECT
        service_id,
        CASE
            WHEN typical_days_per_week >= 5 THEN 'High Frequency'
            WHEN typical_days_per_week >= 2 THEN 'Medium Frequency'
            ELSE 'Low Frequency/Special'
        END AS frequency_category
    FROM service_frequency
)
SELECT
    frequency_category,
    COUNT(*) AS service_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM classified
GROUP BY frequency_category
ORDER BY
    CASE frequency_category
        WHEN 'High Frequency' THEN 1
        WHEN 'Medium Frequency' THEN 2
        ELSE 3
    END;

-- Result of the query: [('High Frequency', 23340, 45.24),
-- ('Medium Frequency', 17877, 34.65),
-- ('Low Frequency/Special', 10376, 20.11)]


-- 5. The Accessibility Audit (Vehicle Features) 
-- Calculate the exact ratio and percentage of scheduled trips per route that explicitly guarantee wheelchair accessibility or bicycle storage (bikes_allowed). 
-- Which specific routes score the lowest in passenger amenity availability?

WITH route_trip_counts AS (
    SELECT
        r.route_id,
        COUNT(t.trip_id) AS total_trips,
        SUM(CASE WHEN t.bikes_allowed = 1 THEN 1 ELSE 0 END) AS trips_with_bikes,
        SUM(CASE WHEN t.wheelchair_accessible = 1 THEN 1 ELSE 0 END) AS trips_with_wheelchair,
        SUM(CASE WHEN t.bikes_allowed = 1 OR t.wheelchair_accessible = 1 THEN 1 ELSE 0 END) AS trips_with_any_amenity
    FROM
        routes r
    JOIN
        trips t ON r.route_id = t.route_id
    GROUP BY
        r.route_id
)
SELECT
    route_id,
    total_trips,
    trips_with_bikes,
    trips_with_wheelchair,
    trips_with_any_amenity,
    ROUND(CAST(trips_with_bikes AS FLOAT) / total_trips, 4) AS ratio_bikes,
    ROUND(CAST(trips_with_wheelchair AS FLOAT) / total_trips, 4) AS ratio_wheelchair,
    ROUND(CAST(trips_with_any_amenity AS FLOAT) / total_trips, 4) AS ratio_any_amenity,
    ROUND(100.0 * CAST(trips_with_bikes AS FLOAT) / total_trips, 2) AS percentage_bikes,
    ROUND(100.0 * CAST(trips_with_wheelchair AS FLOAT) / total_trips, 2) AS percentage_wheelchair,
    ROUND(100.0 * CAST(trips_with_any_amenity AS FLOAT) / total_trips, 2) AS percentage_any_amenity
FROM
    route_trip_counts
LIMIT 20;

-- Result of the query: [('gr:nmbssncb:1', 1, 1, 0, 1, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:10', 436, 436, 0, 436, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:100', 31, 31, 0, 31, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1000', 3, 3, 0, 3, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1001', 2, 2, 0, 2, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1002', 4, 4, 0, 4, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1003', 1, 1, 0, 1, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1004', 15, 15, 0, 15, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1005', 10, 10, 0, 10, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1006', 10, 10, 0, 10, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1007', 2, 2, 0, 2, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1008', 1, 1, 0, 1, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1009', 787, 787, 0, 787, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:101', 39, 39, 0, 39, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1010', 86, 86, 0, 86, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1011', 275, 275, 0, 275, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1012', 93, 93, 0, 93, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1013', 139, 139, 0, 139, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1014', 110, 110, 0, 110, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0),
-- ('gr:nmbssncb:1015', 53, 53, 0, 53, 1.0, 0.0, 1.0, 100.0, 0.0, 100.0)]
