#!/usr/bin/env python3
"""
Backfill daily station stats aggregation from hourly data.

This script aggregates historical realtime_station_stats data into
realtime_station_stats_daily for improved query performance.
"""

import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, "/home/burket/Git/BahnVision/backend")

from app.core.config import get_settings
from app.services.daily_aggregation_service import DailyAggregationService


async def backfill_daily_stats(days_back: int = 30, force: bool = False):
    """Backfill daily stats for the specified number of days.

    Args:
        days_back: Number of days to backfill from today
        force: If True, re-aggregate even if daily summary exists
    """
    settings = get_settings()

    print(
        f"Connecting to database: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'local'}"
    )
    engine = create_async_engine(settings.database_url, echo=False)
    async_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_maker() as session:
        service = DailyAggregationService(session=session)

        today = date.today()
        start_date = today - timedelta(days=days_back)

        print(f"\nBackfilling daily stats from {start_date} to {today}")
        print(f"Total days to process: {days_back}")
        print()

        results = {"success": 0, "skipped": 0, "error": 0}

        for i in range(days_back):
            target_date = today - timedelta(days=i + 1)  # Start from yesterday

            # Check if already aggregated
            if not force:
                already_exists = await service.is_day_aggregated(target_date)
                if already_exists:
                    print(f"✓ {target_date}: already exists, skipping")
                    results["skipped"] += 1
                    continue

            try:
                stations_count = await service.aggregate_day(target_date)
                results["success"] += 1
                print(f"✓ {target_date}: aggregated {stations_count} stations")
            except Exception as e:
                results["error"] += 1
                print(f"✗ {target_date}: ERROR - {e}")

    await engine.dispose()

    print()
    print("=" * 50)
    print("Backfill complete!")
    print(f"  Success: {results['success']} days")
    print(f"  Skipped: {results['skipped']} days")
    print(f"  Errors:  {results['error']} days")
    print("=" * 50)


async def check_coverage(days_back: int = 30):
    """Check which days have daily summaries.

    Args:
        days_back: Number of past days to check
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_maker() as session:
        service = DailyAggregationService(session=session)

        print(f"Checking daily aggregation coverage for the past {days_back} days...\n")

        coverage = await service.get_aggregation_coverage(days_back)

        # Print results in reverse chronological order
        dates = sorted(coverage.keys(), reverse=True)
        has_gaps = False

        for date_str in dates:
            status = "✓" if coverage[date_str] else "✗"
            if not coverage[date_str]:
                has_gaps = True
            print(
                f"{status} {date_str}: {'aggregated' if coverage[date_str] else 'MISSING'}"
            )

    await engine.dispose()

    if has_gaps:
        print(
            "\n⚠️  Some days are missing daily summaries. Run backfill to populate them."
        )
        print(f"   Usage: python -m scripts.backfill_daily_stats --days {days_back}")
    else:
        print("\n✓ All days have daily summaries!")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill daily station stats aggregation"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to backfill (default: 30)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-aggregate even if daily summary exists",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check which days have daily summaries (no backfill)",
    )

    args = parser.parse_args()

    if args.check:
        await check_coverage(args.days)
    else:
        await backfill_daily_stats(args.days, args.force)


if __name__ == "__main__":
    asyncio.run(main())
