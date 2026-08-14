"""
RailPulse AI Co-Pilot - few-shot example bank.

Each entry pairs a realistic station-manager question with the correct T-SQL
query against the Aug 5, 2026 snapshot (railpulse_snapshot.db). These get
embedded into a Chroma vectorstore (see build_vectorstore.py) and the most
similar examples to an incoming question are injected into the SQL
generation prompt at query time.

Keep questions phrased the way a station manager would actually ask them -
that's what the embedding similarity search matches against.
"""

FEW_SHOT_EXAMPLES = [
    # --- Delays & Punctuality ---
    {
        "question": "Which stations have the most delays?",
        "sql": """SELECT stop_name, AVG(arrival_delay) AS avg_delay_seconds, COUNT(*) AS tracked_events
FROM vw_trip_stop_updates_enriched
WHERE arrival_delay IS NOT NULL
GROUP BY stop_name
HAVING COUNT(*) >= 5
ORDER BY avg_delay_seconds DESC
LIMIT 5;""",
    },
    {
        "question": "Which platform at Bruxelles-Central had the worst average delay?",
        "sql": """SELECT platform_code, AVG(arrival_delay) AS avg_delay_seconds
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Central' AND arrival_delay IS NOT NULL AND platform_code IS NOT NULL
GROUP BY platform_code
ORDER BY avg_delay_seconds DESC
LIMIT 1;""",
    },
    {
        "question": "Which train category has the highest average delay?",
        "sql": """SELECT route_short_name, AVG(arrival_delay) AS avg_delay_seconds, COUNT(*) AS tracked_events
FROM vw_trip_stop_updates_enriched
WHERE arrival_delay IS NOT NULL AND route_short_name IS NOT NULL
GROUP BY route_short_name
HAVING COUNT(*) >= 5
ORDER BY avg_delay_seconds DESC;""",
    },
    {
        "question": "Show me the 5 most delayed trips.",
        "sql": """SELECT trip_id, trip_headsign, stop_name, arrival_delay
FROM vw_trip_stop_updates_enriched
WHERE arrival_delay IS NOT NULL
ORDER BY arrival_delay DESC
LIMIT 5;""",
    },
    {
        "question": "What percentage of tracked trips at Bruxelles-Midi are on time?",
        "sql": """SELECT
    100.0 * SUM(CASE WHEN arrival_delay <= 359 THEN 1 ELSE 0 END) / COUNT(*) AS on_time_pct,
    COUNT(*) AS tracked_events
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Midi' AND arrival_delay IS NOT NULL;""",
    },
    # --- Traffic & Volume ---
    {
        "question": "Which Brussels station has the most traffic?",
        "sql": """SELECT stop_name, COUNT(DISTINCT trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched
WHERE stop_name LIKE '%ruxelles%' OR stop_name LIKE '%russel%'
GROUP BY stop_name
ORDER BY trip_count DESC
LIMIT 1;""",
    },
    {
        "question": "How many trains pass through Bruxelles-Nord?",
        "sql": """SELECT COUNT(DISTINCT trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Nord';""",
    },
    {
        "question": "Which platform at Bruxelles-Central handles the most trains?",
        "sql": """SELECT platform_code, COUNT(DISTINCT trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Central' AND platform_code IS NOT NULL
GROUP BY platform_code
ORDER BY trip_count DESC
LIMIT 1;""",
    },
    {
        "question": "What are the 5 busiest stations overall?",
        "sql": """SELECT stop_name, COUNT(DISTINCT trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched
GROUP BY stop_name
ORDER BY trip_count DESC
LIMIT 5;""",
    },
    # --- Time Patterns (Aug 5 only, not recurring trends) ---
    {
        "question": "What hour was busiest at Bruxelles-Midi?",
        "sql": """SELECT strftime('%H', arrival_time) AS hour_of_day, COUNT(DISTINCT trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Midi' AND arrival_time IS NOT NULL
GROUP BY hour_of_day
ORDER BY trip_count DESC
LIMIT 1;""",
    },
    {
        "question": "Was there a time of day when delays were worst at Bruxelles-Nord?",
        "sql": """SELECT strftime('%H', arrival_time) AS hour_of_day, AVG(arrival_delay) AS avg_delay_seconds
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Nord' AND arrival_delay IS NOT NULL AND arrival_time IS NOT NULL
GROUP BY hour_of_day
ORDER BY avg_delay_seconds DESC;""",
    },
    {
        "question": "Compare morning vs afternoon traffic at Bruxelles-Central.",
        "sql": """SELECT
    CASE WHEN strftime('%H', arrival_time) < '12' THEN 'morning' ELSE 'afternoon' END AS period,
    COUNT(DISTINCT trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Central' AND arrival_time IS NOT NULL
GROUP BY period;""",
    },
    # --- Comparisons & Data-Quality-Aware ---
    {
        "question": "Compare average delay between Bruxelles-Central and Bruxelles-Midi.",
        "sql": """SELECT stop_name, AVG(arrival_delay) AS avg_delay_seconds, COUNT(*) AS tracked_events
FROM vw_trip_stop_updates_enriched
WHERE stop_name IN ('Bruxelles-Central', 'Bruxelles-Midi') AND arrival_delay IS NOT NULL
GROUP BY stop_name;""",
    },
    {
        "question": "How much of the delay data at Bruxelles-Nord is actually tracked?",
        "sql": """SELECT
    100.0 * SUM(CASE WHEN arrival_delay IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*) AS tracked_pct,
    COUNT(*) AS total_stop_events
FROM vw_trip_stop_updates_enriched
WHERE stop_name = 'Bruxelles-Nord';""",
    },
    {
        "question": "Which routes have the least reliable delay tracking?",
        "sql": """SELECT
    route_short_name,
    100.0 * SUM(CASE WHEN arrival_delay IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*) AS tracked_pct,
    COUNT(*) AS total_stop_events
FROM vw_trip_stop_updates_enriched
WHERE route_short_name IS NOT NULL
GROUP BY route_short_name
HAVING COUNT(*) >= 5
ORDER BY tracked_pct ASC
LIMIT 5;""",
    },
    # --- Multilingual (exercises the station_translations join) ---
    {
        "question": "What's the average delay at Brussel-Zuid?",
        "sql": """SELECT AVG(t.arrival_delay) AS avg_delay_seconds, COUNT(*) AS tracked_events
FROM vw_trip_stop_updates_enriched t
JOIN station_translations st ON st.stop_name_fr = t.stop_name
WHERE st.stop_name_nl = 'Brussel-Zuid' AND t.arrival_delay IS NOT NULL;""",
    },
    {
        "question": "How many trains stop at Brussel-Noord?",
        "sql": """SELECT COUNT(DISTINCT t.trip_id) AS trip_count
FROM vw_trip_stop_updates_enriched t
JOIN station_translations st ON st.stop_name_fr = t.stop_name
WHERE st.stop_name_nl = 'Brussel-Noord';""",
    },
    {
        "question": "Which platform at Brussel-West had the worst delay?",
        "sql": """SELECT t.platform_code, AVG(t.arrival_delay) AS avg_delay_seconds
FROM vw_trip_stop_updates_enriched t
JOIN station_translations st ON st.stop_name_fr = t.stop_name
WHERE st.stop_name_nl = 'Brussel-West' AND t.arrival_delay IS NOT NULL AND t.platform_code IS NOT NULL
GROUP BY t.platform_code
ORDER BY avg_delay_seconds DESC
LIMIT 1;""",
    },
]