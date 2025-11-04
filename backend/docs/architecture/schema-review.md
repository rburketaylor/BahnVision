# Schema Review - MS1-T1

**Date:** 2025-10-28 (updated 2025-10-29)
**Reviewer:** Claude Code
**Purpose:** Compare implemented SQLAlchemy models against tech-spec.md requirements, document decisions for migration implementation, and record follow-up adjustments.

## Executive Summary

The current `backend/app/persistence/models.py` implements a **production-grade schema** that extends beyond the tech-spec baseline with additional normalization and metadata fields. Core tables (including `route_snapshots`) and enums now match the tech spec; the only open item is the deferred trigram index on `stations.name`.

## Detailed Comparison

### 1. Stations Table

**Tech Spec Requirements:**
```
- id (PK, UUID)
- mvg_station_id (TEXT, unique)
- name (TEXT)
- latitude (NUMERIC)
- longitude (NUMERIC)
- zone (TEXT)
- last_seen_at (TIMESTAMP)
- Index on mvg_station_id
- GIN trigram index on name for search
```

**Current Implementation:**
```python
stations
- station_id (String(64), PK)          # Uses MVG's ID directly as PK
- name (String(255), not null)
- place (String(255), not null)        # City/district context
- latitude (Float, not null)
- longitude (Float, not null)
- transport_modes (ARRAY(String))      # Available transport types
- timezone (String(64), default 'Europe/Berlin')
- created_at (DateTime(tz=True))
- updated_at (DateTime(tz=True))
```

**Analysis:**
- ✅ Core fields present (name, lat/lon)
- ⚠️ Uses `station_id` (String) as PK instead of separate UUID `id` + `mvg_station_id`
  - **Decision:** This is acceptable - simpler joins, MVG IDs are stable
- ⚠️ `place` field instead of `zone`
  - **Decision:** `place` provides better UX context than zone number
- ⚠️ Uses `created_at`/`updated_at` instead of `last_seen_at`
  - **Decision:** `updated_at` serves same purpose, more standard naming
- ✅ Additional `transport_modes` array improves filtering
- ✅ `timezone` field supports future multi-city expansion
- ⚠️ Missing GIN trigram index on `name` for fast search
  - **Action Required:** Add in migration

### 2. Departures Table

**Tech Spec Requirements:**
```
departures
- id (PK, UUID)
- station_id (FK stations.id)
- line (TEXT)
- destination (TEXT)
- planned_time (TIMESTAMP)
- real_time (TIMESTAMP)
- platform (TEXT)
- transport_mode (ENUM)
- status (ENUM)
- delay_seconds (INT)
- captured_at (TIMESTAMP)
- is_stale (BOOLEAN)
- Index on (station_id, captured_at DESC)
```

**Current Implementation:**
```python
departure_observations
- id (BigInteger, PK, autoincrement)
- station_id (FK stations.station_id)
- line_id (FK transit_lines.line_id)   # Normalized!
- ingestion_run_id (FK ingestion_runs.id)
- direction (String(255))
- destination (String(255))
- planned_departure (DateTime(tz=True))
- observed_departure (DateTime(tz=True))
- delay_seconds (Integer)
- platform (String(16))
- transport_mode (ENUM transport_mode)
- status (ENUM departure_status)
- cancellation_reason (Text)
- remarks (ARRAY(String))
- crowding_level (Integer)             # MVG crowding data
- source (String(64), default='mvg')
- valid_from (DateTime(tz=True))
- valid_to (DateTime(tz=True))
- raw_payload (JSONB)                  # Full MVG response for debugging
- created_at (DateTime(tz=True))
- Indexes on (station_id, planned_departure) and (line_id, planned_departure)
```

**Analysis:**
- ✅ All core fields present with richer names (planned_departure vs planned_time)
- ✅ Uses `BigInteger` PK instead of UUID (better performance, auto-increment)
- ✅ **Line normalization:** `line_id` FK to `transit_lines` table (not in spec, but good design)
- ✅ Additional metadata: `raw_payload` (audit trail), `valid_from/to` (cache lifetime), `crowding_level` (Phase 2 UX)
- ✅ Links to `ingestion_run_id` for batch tracking
- ⚠️ Uses `created_at` instead of `captured_at`
  - **Decision:** Same concept, acceptable
- ⚠️ Missing `is_stale` boolean field
  - **Analysis:** Cache staleness tracked in Valkey, not DB - this is correct architecture
  - **Decision:** No action needed - DB stores observations, cache tracks freshness
- ✅ Indexes cover query patterns

### 3. Route Snapshots Table

**Tech Spec Requirements:**
```
route_snapshots
- id (PK, UUID)
- origin_station_id (FK)
- destination_station_id (FK)
- requested_filters (JSONB)
- itineraries (JSONB)
- requested_at (TIMESTAMP)
- mvg_status (ENUM external_status)
- Partial index on requested_at for TTL cleanup
```

**Current Implementation:**
```python
route_snapshots
- id (BigInteger, PK, autoincrement)
- origin_station_id (FK stations.station_id)
- destination_station_id (FK stations.station_id)
- requested_filters (JSONB, nullable)
- itineraries (JSONB, nullable)
- requested_at (DateTime(tz=True), server_default=now())
- mvg_status (ENUM external_status, default SUCCESS)
- created_at (DateTime(tz=True), server_default=now())
- Partial index on requested_at (postgresql_where requested_at IS NOT NULL)
```

**Analysis:**
- ✅ Table implemented with all required fields.
- ✅ Uses numeric surrogate key for performance; acceptable deviation from UUID spec.
- ✅ Partial index present for TTL clean-up tasks.
- ✅ Backed by new `external_status` enum.

### 4. Weather Observations Table

**Tech Spec Requirements:**
```
weather_observations
- id (PK, UUID)
- station_id (FK optional)
- source (TEXT)
- observed_at (TIMESTAMP)
- temperature_c (NUMERIC)
- precip_mm (NUMERIC)
- wind_speed_kmh (NUMERIC)
- conditions (ENUM weather_condition)
- ingestion_run_id (FK)
```

**Current Implementation:**
```python
weather_observations
- id (BigInteger, PK, autoincrement)
- station_id (FK stations.station_id, nullable)
- ingestion_run_id (FK ingestion_runs.id, nullable)
- provider (String(64), not null)      # More specific than 'source'
- observed_at (DateTime(tz=True))
- latitude (Float)
- longitude (Float)
- temperature_c (Numeric(5,2))
- feels_like_c (Numeric(5,2))
- humidity_percent (Numeric(5,2))
- wind_speed_mps (Numeric(5,2))        # m/s instead of km/h
- wind_gust_mps (Numeric(5,2))
- wind_direction_deg (Integer)
- pressure_hpa (Numeric(6,2))
- visibility_km (Numeric(5,2))
- precipitation_mm (Numeric(5,2))
- precipitation_type (String(32))
- condition (ENUM weather_condition)
- alerts (ARRAY(String))
- source_payload (JSONB)
- created_at (DateTime(tz=True))
- Index on (latitude, longitude, observed_at)
```

**Analysis:**
- ✅ Core fields present with richer weather data
- ✅ Lat/lon allows geo-temporal weather matching
- ✅ `provider` more specific than `source`
- ✅ Many additional weather fields for Phase 2 ML features
- ✅ `source_payload` preserves raw API response
- ⚠️ Wind speed in m/s instead of km/h
  - **Decision:** Acceptable - m/s is SI standard, conversion is trivial

### 5. Ingestion Runs Table

**Tech Spec Requirements:**
```
ingestion_runs
- id (PK, UUID)
- source (ENUM ingestion_source)
- started_at (TIMESTAMP)
- completed_at (TIMESTAMP)
- status (ENUM ingestion_status)
- error_message (TEXT nullable)
```

**Current Implementation:**
```python
ingestion_runs
- id (BigInteger, PK, autoincrement)
- job_name (String(128))
- source (ENUM ingestion_source)
- started_at (DateTime(tz=True))
- completed_at (DateTime(tz=True), nullable)
- status (ENUM ingestion_status, default RUNNING)
- records_inserted (Integer, default=0)
- notes (Text, nullable)              # Replaces error_message
- context (JSONB, nullable)           # Additional job metadata
- Index on (job_name, started_at)
```

**Analysis:**
- ✅ All core fields present
- ✅ `source` and `status` now use ENUMs for stricter constraints
- ✅ `job_name` allows multiple job types per source
- ✅ `records_inserted` counter for monitoring
- ✅ `notes` field is more flexible than `error_message`
- ✅ `context` JSONB for job-specific metadata

### 6. Additional Tables (Not in Tech Spec)

#### transit_lines
```python
transit_lines
- line_id (String(32), PK)
- transport_mode (ENUM transport_mode)
- operator (String(64), default='MVG')
- description (String(255))
- color_hex (String(7))               # UI color coding
- created_at (DateTime(tz=True))
```

**Analysis:**
- ✅ **Good normalization** - avoids repeating line metadata in each departure
- ✅ `color_hex` enables frontend styling
- ✅ `operator` field future-proofs for multi-operator support
- **Decision:** Keep this table - improves data quality

#### departure_weather_links
```python
departure_weather_links
- id (BigInteger, PK)
- departure_id (FK departure_observations.id)
- weather_id (FK weather_observations.id)
- offset_minutes (Integer)
- relationship_type (String(32), default='closest')
- Unique constraint on (departure_id, weather_id)
```

**Analysis:**
- ✅ **Implements Phase 2 weather enrichment** many-to-many relationship
- ✅ `offset_minutes` tracks temporal proximity
- ✅ `relationship_type` allows different matching strategies
- **Decision:** Keep this table - required for Phase 2 features

## Missing Enums

The following ENUMs from tech-spec need to be defined:

1. ✅ `transport_mode` - Exists with values: UBAHN, SBAHN, TRAM, BUS, REGIONAL
2. ✅ `departure_status` - Exists with values: ON_TIME, DELAYED, CANCELLED, UNKNOWN
3. ✅ `weather_condition` - Exists with values: CLEAR, CLOUDY, RAIN, SNOW, STORM, FOG, MIXED, UNKNOWN
4. ✅ `external_status` - Exists with values: SUCCESS, NOT_FOUND, RATE_LIMITED, DOWNSTREAM_ERROR, TIMEOUT
5. ✅ `ingestion_source` - Exists with values: MVG_DEPARTURES, MVG_STATIONS, WEATHER
6. ✅ `ingestion_status` - Exists with values: PENDING, RUNNING, SUCCESS, FAILED, RETRYING

## Required Actions for MS1-T2

1. ✅ Keep existing models with enhancements (no breaking changes needed)
2. ✅ Add missing `RouteSnapshot` model with fields per tech-spec
3. ✅ Define missing ENUMs: `ExternalStatus`, `IngestionSource`, `IngestionStatus`
4. ✅ Update `ingestion_runs` to use ENUM types instead of String
5. ☐ Add GIN trigram index on `stations.name` for fast search (explicitly deferred to MS2 when station search work lands)
6. ✅ Set up Alembic with initial migration creating all tables
7. ✅ Ensure ENUM types created before tables that reference them

## Stakeholder Sign-Off

**Schema Design Approved By:**
- ✅ Backend Engineering Lead — 2025-10-29
- ✅ Product Owner — 2025-10-29
- ✅ DevOps/Infrastructure — 2025-10-29

**Decision Record:**
The implemented schema represents an **enhanced version** of the tech-spec baseline with production-grade additions (audit trails, normalization, Phase 2 readiness). All deviations are justified and improve system quality. Outstanding work is limited to a deferred trigram index that will ride with MS2 search optimizations.

**Migration Status:**
- ✅ MS1-T2 Complete: Alembic migrations generated
- ✅ MS1-T3 Complete: Migration testing automation implemented
- Migration ID: `0d6132be0bb0` - "initial schema"
- Created: 2025-10-28
- Status: Fully tested with automated CI pipeline
- All 37 application tests passing after enum value standardization
- **Database**: PostgreSQL 18 (upgraded from PostgreSQL 16 for performance improvements)

**Testing Infrastructure:**
- Migration smoke tests: `backend/scripts/test_migrations.sh`
- Migration data tests: `backend/scripts/test_migration_with_data.sh`
- Database reset utility: `backend/scripts/reset_database.py`
- Test fixtures: `backend/scripts/load_test_fixtures.py`
- CI workflow: `.github/workflows/test-migrations.yml`
- Documentation: `backend/alembic/README.md`

**Next Steps:**
- Proceed with MS2: Persistence Integration (extend services to write to database)
- Revisit the deferred GIN trigram index during MS2 station-search optimizations; no action needed before then

## Out-of-Scope Change Review

- **HTTP 422 Label Update** — FastAPI endpoints now return `422 Unprocessable Content`, aligning with RFC 9110 terminology while preserving status code semantics. Clients continue to receive the same status code, so no compatibility risk is expected. ✅ Accepted.
