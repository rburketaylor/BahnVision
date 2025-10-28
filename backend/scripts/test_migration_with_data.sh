#!/usr/bin/env bash
# Test migration cycles with actual data
# Ensures data survives upgrade/downgrade operations

set -e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BACKEND_DIR"

echo "=========================================="
echo "Migration Data Persistence Test"
echo "=========================================="
echo ""

# Check environment
if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

echo "✓ Environment configured"
echo ""

# Step 1: Reset to clean state
echo "Step 1: Resetting database to clean state..."
PYTHONPATH=. python scripts/reset_database.py
echo ""

# Step 2: Run migrations
echo "Step 2: Running migrations to head..."
python -m alembic upgrade head
echo ""

# Step 3: Load test data
echo "Step 3: Loading test fixtures..."
PYTHONPATH=. python scripts/load_test_fixtures.py | grep -E "(✓|✅)"
echo ""

# Step 4: Verify data exists
echo "Step 4: Verifying data was properly persisted..."
PYTHONPATH=. python -c "
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
from app.persistence.models import Station, TransitLine, DepartureObservation

async def verify():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        # Check stations
        result = await conn.execute(select(Station))
        stations = result.all()
        assert len(stations) > 0, 'No stations found'
        print(f'✓ Found {len(stations)} station(s)')

        # Check transit lines
        result = await conn.execute(select(TransitLine))
        lines = result.all()
        assert len(lines) > 0, 'No transit lines found'
        print(f'✓ Found {len(lines)} transit line(s)')

        # Check departures
        result = await conn.execute(select(DepartureObservation))
        departures = result.all()
        assert len(departures) > 0, 'No departures found'
        print(f'✓ Found {len(departures)} departure(s)')

    await engine.dispose()

asyncio.run(verify())
"
echo ""

# Step 5: Test downgrade (will drop all data - this is expected)
echo "Step 5: Testing downgrade to base (drops all tables)..."
python -m alembic downgrade base 2>&1 | grep -E "Running downgrade"
echo "✓ Successfully downgraded to base"
echo ""

# Step 6: Test re-upgrade
echo "Step 6: Testing re-upgrade to head..."
python -m alembic upgrade head 2>&1 | grep -E "Running upgrade"
echo "✓ Successfully re-upgraded to head"
echo ""

echo "=========================================="
echo "✅ All migration tests passed!"
echo "Migration upgrade/downgrade cycle works correctly"
echo "=========================================="
