-- ═══════════════════════════════════════════════════════════════════════════
-- RAILPULSE CLOUD DATA WAREHOUSE: UNIFIED GTFS STATIC & REALTIME SCHEMA
-- Target DB: Azure SQL Serverless
-- ═══════════════════════════════════════════════════════════════════════════

-- ── 0. Drop existing tables (Facts first, then Dimensions) ─────────────────
IF OBJECT_ID('dbo.trip_stop_updates', 'U')       IS NOT NULL DROP TABLE dbo.trip_stop_updates;
IF OBJECT_ID('dbo.alert_informed_entities', 'U') IS NOT NULL DROP TABLE dbo.alert_informed_entities;
IF OBJECT_ID('dbo.alert_texts', 'U')             IS NOT NULL DROP TABLE dbo.alert_texts;
IF OBJECT_ID('dbo.alert_active_periods', 'U')    IS NOT NULL DROP TABLE dbo.alert_active_periods;
IF OBJECT_ID('dbo.trip_updates', 'U')            IS NOT NULL DROP TABLE dbo.trip_updates;
IF OBJECT_ID('dbo.service_alerts', 'U')          IS NOT NULL DROP TABLE dbo.service_alerts;

IF OBJECT_ID('dbo.dim_trips', 'U')               IS NOT NULL DROP TABLE dbo.dim_trips;
IF OBJECT_ID('dbo.dim_routes', 'U')              IS NOT NULL DROP TABLE dbo.dim_routes;
IF OBJECT_ID('dbo.dim_stations', 'U')            IS NOT NULL DROP TABLE dbo.dim_stations;
GO

-- ═══════════════════════ DIMENSION TABLES (GTFS-STATIC) ═══════════════════════

-- ── 1. dim_stations — Station & Platform Metadata ─────────────────────────
CREATE TABLE dbo.dim_stations (
    stop_id             VARCHAR(50)   NOT NULL,   -- GTFS stop_id, e.g. '8813003'
    stop_name           NVARCHAR(150) NOT NULL,   -- e.g. 'Brussel-Centraal / Bruxelles-Central'
    parent_station      VARCHAR(50)   NULL,       -- Parent hub ID for platforms
    platform_code       VARCHAR(20)   NULL,       -- Platform number (e.g. '3', '4')
    wheelchair_boarding INT           NULL,       -- 0 = No info, 1 = Accessible, 2 = Not accessible
    CONSTRAINT PK_dim_stations PRIMARY KEY (stop_id)
);
GO

-- ── 2. dim_routes — Line & Route Metadata ──────────────────────────────────
CREATE TABLE dbo.dim_routes (
    route_id            VARCHAR(50)   NOT NULL,   -- e.g. 'gr:nmbssncb:10'
    agency_id           VARCHAR(30)   NULL,
    route_short_name    NVARCHAR(50)  NULL,       -- e.g. 'IC-01'
    route_long_name     NVARCHAR(200) NULL,       -- e.g. 'Eupen -- Oostende'
    route_type          INT           NOT NULL,   -- GTFS route type (2 = Rail)
    CONSTRAINT PK_dim_routes PRIMARY KEY (route_id)
);
GO

-- ── 3. dim_trips — Scheduled Trip Reference ───────────────────────────────
CREATE TABLE dbo.dim_trips (
    trip_id             VARCHAR(100)  NOT NULL,   -- GTFS static trip_id
    route_id            VARCHAR(50)   NOT NULL,
    service_id          VARCHAR(50)   NOT NULL,   -- Operating calendar service key
    trip_headsign       NVARCHAR(150) NULL,       -- Destination shown on train (e.g. 'Anvers-Central')
    bikes_allowed       INT           NULL,       -- 0 = No info, 1 = Allowed, 2 = Not allowed
    wheelchair_accessible INT         NULL,       -- 0 = No info, 1 = Accessible, 2 = Not accessible
    CONSTRAINT PK_dim_trips PRIMARY KEY (trip_id),
    CONSTRAINT FK_dim_trips_routes FOREIGN KEY (route_id) REFERENCES dbo.dim_routes (route_id)
);
GO


-- ═══════════════════════ FACT TABLES (GTFS-REALTIME) ═══════════════════════

-- ── 4. trip_updates — Liveboard Trip Header Telemetry ─────────────────────
CREATE TABLE dbo.trip_updates (
    update_pk                   INT IDENTITY(1,1) NOT NULL,
    entity_id                   VARCHAR(100)  NOT NULL,   -- GTFS-RT entity ID
    trip_id                     VARCHAR(100)  NOT NULL,   -- Links to dim_trips.trip_id
    route_id                    VARCHAR(50)   NULL,       -- Links to dim_routes.route_id
    start_date                  VARCHAR(8)    NULL,       -- YYYYMMDD
    start_time                  VARCHAR(8)    NULL,       -- HH:MM:SS
    trip_schedule_relationship  INT           NULL,       -- GTFS-RT numeric code (0 = SCHEDULED)
    vehicle_id                  VARCHAR(50)   NULL,
    vehicle_label               VARCHAR(50)   NULL,
    license_plate               VARCHAR(20)   NULL,
    overall_delay               INT           NULL,       -- Delay in seconds across entire trip
    update_timestamp            DATETIME2     NULL,       -- Feed snapshot generation time (UTC)
    fetched_at                  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_trip_updates PRIMARY KEY (update_pk)
);
GO

-- ── 5. trip_stop_updates — Station-Level Arrival/Departure Delays ─────────
CREATE TABLE dbo.trip_stop_updates (
    id                      INT IDENTITY(1,1) NOT NULL,
    update_pk                INT           NOT NULL,   -- Parent FK to trip_updates
    stop_sequence           INT           NOT NULL,   -- Sequential stop index in trip
    stop_id                  VARCHAR(50)   NOT NULL,   -- Links to dim_stations.stop_id
    arrival_time             DATETIME2     NULL,       -- Scheduled/estimated arrival (UTC)
    arrival_delay            INT           NULL,       -- Arrival delay in seconds
    departure_time           DATETIME2     NULL,       -- Scheduled/estimated departure (UTC)
    departure_delay          INT           NULL,       -- Departure delay in seconds
    schedule_relationship    INT           NULL,
    CONSTRAINT PK_trip_stop_updates PRIMARY KEY (id),
    CONSTRAINT FK_stop_update_trip FOREIGN KEY (update_pk)
        REFERENCES dbo.trip_updates (update_pk) ON DELETE CASCADE
);
GO

-- ── 6. service_alerts — Live Network Disruption Events ────────────────────
CREATE TABLE dbo.service_alerts (
    alert_pk        INT IDENTITY(1,1) NOT NULL,
    entity_id       VARCHAR(100)  NOT NULL,
    cause           INT           NULL,         -- GTFS-RT alert cause code
    effect          INT           NULL,         -- GTFS-RT alert effect code (e.g., 3 = SIGNIFICANT_DELAYS)
    fetched_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_service_alerts PRIMARY KEY (alert_pk),
    CONSTRAINT UQ_service_alerts_poll UNIQUE (entity_id, fetched_at)
);
GO

-- ── 7. alert_active_periods — Active Time Windows ─────────────────────────
CREATE TABLE dbo.alert_active_periods (
    id              INT IDENTITY(1,1) NOT NULL,
    alert_pk        INT           NOT NULL,
    period_start    DATETIME2     NULL,
    period_end      DATETIME2     NULL,
    CONSTRAINT PK_alert_active_periods PRIMARY KEY (id),
    CONSTRAINT FK_active_period_alert FOREIGN KEY (alert_pk)
        REFERENCES dbo.service_alerts (alert_pk) ON DELETE CASCADE
);
GO

-- ── 8. alert_texts — Multilingual Translation Strings ──────────────────────
CREATE TABLE dbo.alert_texts (
    id              INT IDENTITY(1,1) NOT NULL,
    alert_pk        INT           NOT NULL,
    field_name      VARCHAR(20)   NOT NULL,   -- 'header' | 'description' | 'url'
    language        VARCHAR(10)   NULL,       -- BCP-47 code ('fr', 'nl', 'en', 'de')
    text_value      NVARCHAR(MAX) NULL,
    CONSTRAINT PK_alert_texts PRIMARY KEY (id),
    CONSTRAINT FK_alert_text_alert FOREIGN KEY (alert_pk)
        REFERENCES dbo.service_alerts (alert_pk) ON DELETE CASCADE
);
GO

-- ── 9. alert_informed_entities — Impacted Routes/Stations/Trips ────────────
CREATE TABLE dbo.alert_informed_entities (
    id                          INT IDENTITY(1,1) NOT NULL,
    alert_pk                    INT           NOT NULL,
    agency_id                   VARCHAR(30)   NULL,
    route_id                    VARCHAR(50)   NULL,
    route_type                  INT           NULL,
    trip_id                     VARCHAR(100)  NULL,
    trip_start_date             VARCHAR(8)    NULL,
    trip_start_time             VARCHAR(8)    NULL,
    trip_schedule_relationship  INT           NULL,
    stop_id                     VARCHAR(50)   NULL,
    CONSTRAINT PK_alert_informed_entities PRIMARY KEY (id),
    CONSTRAINT FK_informed_entity_alert FOREIGN KEY (alert_pk)
        REFERENCES dbo.service_alerts (alert_pk) ON DELETE CASCADE
);
GO

-- ═══════════════════════ INDEXES FOR POWER BI PERFORMANCE ═══════════════════════

CREATE NONCLUSTERED INDEX IX_trip_updates_fetched_at ON dbo.trip_updates(fetched_at DESC);
CREATE NONCLUSTERED INDEX IX_trip_updates_trip_id ON dbo.trip_updates(trip_id);
CREATE NONCLUSTERED INDEX IX_trip_stop_updates_stop_id ON dbo.trip_stop_updates(stop_id);
CREATE NONCLUSTERED INDEX IX_trip_stop_updates_update_pk ON dbo.trip_stop_updates(update_pk);
GO