# Optimization Plan: Efficiency, Space Saving, and GTFS Imports

## Objective

Implement structural and algorithmic optimizations across the codebase to significantly reduce database storage footprint, speed up massive GTFS data imports, and decrease response times for real-time heatmap and harvester services.

## Key Files & Context

- **Database Models:** `backend/app/models/gtfs.py`, `backend/app/persistence/models.py`
- **Import Service:** `backend/app/services/gtfs_feed.py`
- **Realtime Harvester:** `backend/app/services/gtfs_realtime_harvester.py`
- **Heatmap Service:** `backend/app/services/heatmap_service.py`
- **Database Migrations:** `backend/alembic/versions/`

## Implementation Steps

### 1. Database Storage Optimization (Space Saving)

- **GTFSStopTime Table (`gtfs.py`)**:
  - Remove the surrogate `id` (Integer) primary key.
  - Implement a composite primary key using `(trip_id, stop_sequence)` to save ~4 bytes per row plus index overhead on millions of rows.
- **RealtimeStationStats & Daily Tables (`models.py`)**:
  - **Daily:** Remove the surrogate `id` (BigInteger) and set `(stop_id, date)` as the composite primary key.
  - **Hourly:** Remove the surrogate `id` (BigInteger). Adjust the schema to support a composite primary key on `(stop_id, bucket_start, route_type)` by ensuring `route_type` is non-nullable (e.g., default `0` for unknown/bus).
- **GTFSStop Table (`gtfs.py`)**:
  - Change `stop_lat` and `stop_lon` from `Numeric(9, 6)` to `Float()` (Double Precision/Real) to reduce storage size and improve spatial computation speed.
- **Migrations**: Generate an Alembic migration script to apply these schema changes safely, dropping the old surrogate keys and indexes, and adding the new primary keys.

### 2. GTFS Import Speedup

- **Batching Optimization (`gtfs_feed.py`)**:
  - In `_copy_stop_times_from_zip`, increase the Polars `read_csv_batched` `batch_size` parameter from `500_000` to `1_500_000` or `2_000_000` to maximize PostgreSQL `COPY` throughput.
- **Index Management**:
  - Verify that `UNLOGGED` table creation and index dropping/recreation are fully operational during the `stop_times` import phase to minimize WAL writing overhead.

### 3. Heatmap Query Efficiency

- **Query Consolidation (`heatmap_service.py`)**:
  - Refactor the `_aggregate_station_data_from_db` and `_aggregate_from_daily_stats` methods.
  - Currently, they execute a two-pass strategy: a CTE to find top/representative stations, followed by a second query using `.in_(station_ids)` to fetch breakdowns.
  - Combine these into a single highly-optimized PostgreSQL query using Window Functions (`ROW_NUMBER() OVER (...)`) or JSON aggregation (`jsonb_object_agg`) to retrieve the station metadata, totals, and route_type breakdowns in one network round-trip.

### 4. GTFS-RT Harvester Optimization

- **Metadata Caching (`gtfs_realtime_harvester.py`)**:
  - In the `_cache_live_snapshot` workflow, station metadata (name, lat, lon) is repeatedly processed.
  - Fetch and cache this static GTFS metadata in Valkey (e.g., using a hash `HSET` or a single JSON string with a long TTL) to drastically reduce the load on the database during the rapid 5-minute heartbeat cycle.
  - Clean up the brittle private member access (`hasattr(self._cache, "set_json")`) into a proper service interface.

## Verification & Testing

1.  **Test Suite**: Run `pytest backend/tests` to ensure no regressions in endpoint logic or model interactions.
2.  **Schema Validation**: Run `alembic upgrade head` and `alembic downgrade -1` locally to verify the migration logic is idempotent and correct.
3.  **Import Benchmark**: Execute `python scripts/import_gtfs.py` and observe log timings to confirm the increased batch size improves the total ingestion time.
4.  **Heatmap Benchmark**: Test the heatmap API endpoints (`/api/v1/endpoints/heatmap`) to verify faster execution times for large date ranges and ensuring data parity with the old two-pass query.
5.  **Harvester Benchmark**: Monitor logs for the realtime harvester task to ensure snapshot caching completes without excessive DB queries.
