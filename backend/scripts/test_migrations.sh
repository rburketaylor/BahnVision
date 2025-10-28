#!/usr/bin/env bash
# Migration smoke test script
# Tests upgrade and downgrade cycles to ensure migrations work correctly

set -e  # Exit on error
set -u  # Exit on undefined variable

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BACKEND_DIR"

echo "=========================================="
echo "Migration Smoke Test"
echo "=========================================="
echo ""

# Check for required environment variables
if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

echo "✓ Environment variables configured"
echo ""

# Test 1: Check current migration state
echo "Test 1: Checking current migration state..."
python -m alembic current
echo "✓ Successfully retrieved current migration state"
echo ""

# Test 2: Downgrade to base (clean slate)
echo "Test 2: Downgrading to base..."
python -m alembic downgrade base
echo "✓ Successfully downgraded to base"
echo ""

# Test 3: Upgrade to head
echo "Test 3: Upgrading to head..."
python -m alembic upgrade head
MIGRATION_ID=$(python -m alembic current | head -n 1 | awk '{print $1}')
echo "✓ Successfully upgraded to head (${MIGRATION_ID})"
echo ""

# Test 4: Downgrade one revision
echo "Test 4: Testing downgrade -1..."
python -m alembic downgrade -1
echo "✓ Successfully downgraded one revision"
echo ""

# Test 5: Upgrade back to head
echo "Test 5: Upgrading back to head..."
python -m alembic upgrade head
echo "✓ Successfully upgraded back to head"
echo ""

echo "=========================================="
echo "✓ All migration smoke tests passed!"
echo "=========================================="
