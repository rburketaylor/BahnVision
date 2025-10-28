# Alembic Database Migrations

This directory contains database migrations for the BahnVision backend.

## Overview

- **Migration Tool**: Alembic 1.17.0
- **Database**: PostgreSQL 18 with asyncpg driver
- **Current Migration**: `0d6132be0bb0` - "initial schema"
- **Schema**: 7 tables, 6 ENUMs, multiple indexes including partial indexes

### PostgreSQL 18 Features

BahnVision uses PostgreSQL 18 (released September 2025) for:

- **Up to 3× I/O performance** - New I/O subsystem dramatically improves read performance
- **Skip scan optimization** - Better B-tree index performance for partial matches
- **Page checksums enabled by default** - Enhanced data integrity with minimal overhead
- **Virtual generated columns** - Compute values at query time (useful for calculated fields)
- **uuidv7() support** - Better indexing and read performance for UUIDs
- **Faster major-version upgrades** - Parallel pg_upgrade support

## Quick Start

### Running Migrations

```bash
# Upgrade to latest
python -m alembic upgrade head

# Downgrade one revision
python -m alembic downgrade -1

# Downgrade to base (clean database)
python -m alembic downgrade base

# Check current migration
python -m alembic current

# View migration history
python -m alembic history --verbose
```

### Creating New Migrations

```bash
# Auto-generate migration from model changes
python -m alembic revision --autogenerate -m "description of changes"

# Review the generated migration file in versions/
# Edit if needed (Alembic doesn't catch everything)

# Test the migration
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

## Testing Migrations

### Local Testing

#### Smoke Test (No Data)
Tests basic upgrade/downgrade cycles:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision" \
./scripts/test_migrations.sh
```

#### Full Test (With Data)
Tests migrations with actual fixtures to verify schema changes work:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision" \
./scripts/test_migration_with_data.sh
```

#### Reset Database
Clean the database for fresh testing:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision" \
PYTHONPATH=. python scripts/reset_database.py
```

### CI Testing

Migrations are automatically tested in GitHub Actions on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Changes to `backend/alembic/**` or `backend/app/persistence/models.py`

The CI workflow:
1. Runs migration smoke tests (upgrade/downgrade cycles)
2. Runs migrations with test data
3. Runs full pytest suite with migrations applied

See `.github/workflows/test-migrations.yml` for details.

## Schema Overview

### Tables Created

1. **stations** - Transit stations (Marienplatz, Hauptbahnhof, etc.)
2. **transit_lines** - Transit lines (U3, S1, Bus 100, etc.)
3. **ingestion_runs** - Batch job tracking
4. **departure_observations** - Historical departure data
5. **route_snapshots** - Route planning request history
6. **weather_observations** - Weather data (Phase 2)
7. **departure_weather_links** - Many-to-many weather/departure relationship (Phase 2)

### ENUMs Defined

- **transport_mode**: UBAHN, SBAHN, TRAM, BUS, REGIONAL
- **departure_status**: ON_TIME, DELAYED, CANCELLED, UNKNOWN
- **weather_condition**: CLEAR, CLOUDY, RAIN, SNOW, STORM, FOG, MIXED, UNKNOWN
- **external_status**: SUCCESS, NOT_FOUND, RATE_LIMITED, DOWNSTREAM_ERROR, TIMEOUT
- **ingestion_source**: MVG_DEPARTURES, MVG_STATIONS, WEATHER
- **ingestion_status**: PENDING, RUNNING, SUCCESS, FAILED, RETRYING

### Key Indexes

- **stations.name** - Will add GIN trigram index for fast search (future migration)
- **departure_observations** - (station_id, planned_departure), (line_id, planned_departure)
- **route_snapshots.requested_at** - Partial index for TTL cleanup queries
- **weather_observations** - (latitude, longitude, observed_at)
- **ingestion_runs** - (job_name, started_at)

## Configuration

Database URL is configured via environment variable or `app/core/config.py`:

```python
DATABASE_URL = "postgresql+asyncpg://user:pass@host:port/dbname"
```

The Alembic env.py automatically imports settings from the application config.

## Common Issues

### ENUM Already Exists Error

If you see "type 'enum_name' already exists":

1. This happens when downgrade didn't drop ENUMs
2. Use `scripts/reset_database.py` to clean up
3. ENUMs are manually dropped in the downgrade function

### Migration Conflicts

If multiple developers create migrations simultaneously:

1. Merge the migrations locally
2. Use `alembic merge` to create a merge migration
3. Test the merged migration thoroughly

### Schema Drift

If models don't match database:

1. Generate a new migration with `--autogenerate`
2. Review the generated changes carefully
3. Alembic may miss some changes (indexes, constraints) - add manually if needed

## Best Practices

1. **Always review auto-generated migrations** - Alembic doesn't catch everything
2. **Test both upgrade and downgrade** - Ensure rollback works
3. **Keep migrations small** - One logical change per migration
4. **Add data migrations separately** - Schema changes and data changes should be separate
5. **Document breaking changes** - Add comments in the migration file
6. **Never edit applied migrations** - Create a new migration to fix issues

## Migration Workflow

```
┌─────────────────────────────────────────────┐
│ 1. Update SQLAlchemy models                 │
│    (backend/app/persistence/models.py)      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ 2. Generate migration                        │
│    alembic revision --autogenerate -m "..."  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ 3. Review & edit generated migration         │
│    Check versions/*.py file                  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ 4. Test locally                              │
│    Run upgrade/downgrade cycles              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ 5. Commit and push                           │
│    CI will test automatically                │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ 6. Deploy                                    │
│    Run migrations before starting app        │
└─────────────────────────────────────────────┘
```

## Deployment

In production:

```bash
# 1. Stop application
# 2. Backup database
pg_dump bahnvision > backup_$(date +%Y%m%d_%H%M%S).sql

# 3. Run migrations
alembic upgrade head

# 4. Verify
alembic current

# 5. Start application
```

## Rollback Procedure

If a migration causes issues in production:

```bash
# 1. Stop application

# 2. Rollback one migration
alembic downgrade -1

# 3. Verify
alembic current

# 4. Restart application with previous version
```

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [tech-spec.md](../../docs/tech-spec.md) - Full schema specification
- [schema-review.md](../../docs/schema-review.md) - Schema design decisions
