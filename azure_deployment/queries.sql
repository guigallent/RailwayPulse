-- Covers: /rt/trip-update and /rt/alert feeds, matching their actual JSON shape.
-- Run against your Azure SQL Database (serverless tier).

-- ── Drop existing tables (children before parents) ─────────────────────────
IF OBJECT_ID('dbo.trip_stop_updates', 'U')       IS NOT NULL DROP TABLE dbo.trip_stop_updates;
IF OBJECT_ID('dbo.alert_informed_entities', 'U') IS NOT NULL DROP TABLE dbo.alert_informed_entities;
IF OBJECT_ID('dbo.alert_texts', 'U')             IS NOT NULL DROP TABLE dbo.alert_texts;
IF OBJECT_ID('dbo.alert_active_periods', 'U')    IS NOT NULL DROP TABLE dbo.alert_active_periods;
IF OBJECT_ID('dbo.trip_updates', 'U')            IS NOT NULL DROP TABLE dbo.trip_updates;
IF OBJECT_ID('dbo.service_alerts', 'U')          IS NOT NULL DROP TABLE dbo.service_alerts;
GO

-- ═══════════════════════ TRIP UPDATES ═══════════════════════

-- ── 1. trip_updates — one row per tripUpdate entity, per poll ───────────────
CREATE TABLE dbo.trip_updates (
    update_pk               INT IDENTITY(1,1) NOT NULL,
    entity_id                VARCHAR(100)  NOT NULL,   -- entity.id, e.g. 'rs:tec:90a2253b-...'
    trip_id                   VARCHAR(100)  NOT NULL,   -- trip.tripId
    route_id                  VARCHAR(50)   NULL,       -- trip.routeId
    start_date                VARCHAR(8)    NULL,       -- trip.startDate (YYYYMMDD)
    start_time                VARCHAR(8)    NULL,       -- trip.startTime (HH:MM:SS)
    trip_schedule_relationship INT           NULL,       -- trip.scheduleRelationship, RAW numeric
                                                          -- code (0 = SCHEDULED observed). Don't
                                                          -- pre-map to text in Python — map at query
                                                          -- time instead, once you trust the codes.
    vehicle_id                VARCHAR(50)   NULL,       -- vehicle.id
    vehicle_label              VARCHAR(50)   NULL,       -- vehicle.label
    license_plate              VARCHAR(20)   NULL,       -- vehicle.licensePlate
    overall_delay              INT           NULL,       -- tripUpdate.delay
    update_timestamp            DATETIME2     NULL,       -- tripUpdate.timestamp, converted from epoch
    fetched_at                  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_trip_updates PRIMARY KEY (update_pk)
);
GO

-- ── 2. trip_stop_updates — one row per stopTimeUpdate item ──────────────────
CREATE TABLE dbo.trip_stop_updates (
    id                     INT IDENTITY(1,1) NOT NULL,
    update_pk               INT           NOT NULL,
    stop_sequence            INT           NOT NULL,   -- stopTimeUpdate.stopSequence
    stop_id                   VARCHAR(50)   NOT NULL,   -- stopTimeUpdate.stopId
    arrival_time              DATETIME2     NULL,       -- arrival.time, converted from epoch
    arrival_delay             INT           NULL,       -- arrival.delay
    departure_time            DATETIME2     NULL,       -- departure.time, converted from epoch
    departure_delay           INT           NULL,       -- departure.delay
    schedule_relationship     INT           NULL,       -- stopTimeUpdate.scheduleRelationship, RAW
                                                          -- numeric code.
    CONSTRAINT PK_trip_stop_updates PRIMARY KEY (id),
    CONSTRAINT FK_stop_update_trip FOREIGN KEY (update_pk)
        REFERENCES dbo.trip_updates (update_pk)
);
GO

-- ═══════════════════════ SERVICE ALERTS ═══════════════════════

-- ── 3. service_alerts — one row per alert entity, per poll ──────────────────
CREATE TABLE dbo.service_alerts (
    alert_pk       INT IDENTITY(1,1) NOT NULL,
    entity_id       VARCHAR(100)  NOT NULL,     -- entity.id
    cause           INT           NULL,         -- alert.cause, RAW numeric code. Do not
                                                  -- pre-map to text — observed values don't
                                                  -- clearly match the standard GTFS-RT enum
                                                  -- (e.g. cause=1 alongside a very specific
                                                  -- described cause), so guessing a label here
                                                  -- risks mislabeling. Map at query time once
                                                  -- you've cross-checked enough real examples.
    effect          INT           NULL,         -- alert.effect, RAW numeric code (3 =
                                                  -- SIGNIFICANT_DELAYS matched the observed
                                                  -- sample, but still verify at query time
                                                  -- rather than trusting it during ingestion)
    fetched_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_service_alerts PRIMARY KEY (alert_pk),
    CONSTRAINT UQ_service_alerts_poll UNIQUE (entity_id, fetched_at)
);
GO

-- ── 4. alert_active_periods — one row per activePeriod item ─────────────────
-- Split out because an alert can carry several date ranges
-- (e.g. recurring weekday disruptions), not just one.
CREATE TABLE dbo.alert_active_periods (
    id             INT IDENTITY(1,1) NOT NULL,
    alert_pk       INT           NOT NULL,
    period_start   DATETIME2     NULL,   -- activePeriod[].start, converted from epoch
    period_end     DATETIME2     NULL,   -- activePeriod[].end, converted from epoch
    CONSTRAINT PK_alert_active_periods PRIMARY KEY (id),
    CONSTRAINT FK_active_period_alert FOREIGN KEY (alert_pk)
        REFERENCES dbo.service_alerts (alert_pk)
);
GO

-- ── 5. alert_texts — one row per (field, language) translation ──────────────
-- Same polymorphic shape as the static GTFS translations.txt from last
-- sprint: headerText, descriptionText, and url each carry their own
-- translation[] array of {language, text}.
CREATE TABLE dbo.alert_texts (
    id           INT IDENTITY(1,1) NOT NULL,
    alert_pk     INT           NOT NULL,
    field_name   VARCHAR(20)   NOT NULL,   -- 'header' | 'description' | 'url'
    language     VARCHAR(10)   NULL,       -- BCP-47 code, e.g. 'en', 'fr', 'nl'
    text_value   NVARCHAR(MAX) NULL,       -- NVARCHAR(MAX): descriptions can be long,
                                             -- and carry French/Dutch/German accents
    CONSTRAINT PK_alert_texts PRIMARY KEY (id),
    CONSTRAINT FK_alert_text_alert FOREIGN KEY (alert_pk)
        REFERENCES dbo.service_alerts (alert_pk)
);
GO

-- ── 6. alert_informed_entities — one row per informedEntity item ────────────
-- Surrogate IDENTITY key required: route_id / trip fields / stop_id are all
-- individually optional depending on the alert's scope, and SQL Server
-- disallows NULLs in primary key columns.
CREATE TABLE dbo.alert_informed_entities (
    id                          INT IDENTITY(1,1) NOT NULL,
    alert_pk                    INT           NOT NULL,
    agency_id                    VARCHAR(30)   NULL,   -- informedEntity.agencyId
    route_id                     VARCHAR(50)   NULL,   -- informedEntity.routeId
    route_type                   INT           NULL,   -- informedEntity.routeType
    trip_id                       VARCHAR(100)  NULL,   -- informedEntity.trip.tripId
    trip_start_date                VARCHAR(8)    NULL,   -- informedEntity.trip.startDate
    trip_start_time                VARCHAR(8)    NULL,   -- informedEntity.trip.startTime
    trip_schedule_relationship      INT           NULL,   -- informedEntity.trip.scheduleRelationship, raw code
    stop_id                          VARCHAR(50)   NULL,   -- not present in this API's documented
                                                             -- schema, kept nullable in case it
                                                             -- appears in practice — verify before
                                                             -- relying on it
    CONSTRAINT PK_alert_informed_entities PRIMARY KEY (id),
    CONSTRAINT FK_informed_entity_alert FOREIGN KEY (alert_pk)
        REFERENCES dbo.service_alerts (alert_pk)
);
GO