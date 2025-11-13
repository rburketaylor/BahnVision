"""
Background job for syncing MVG stations to the database.

This module provides a scheduled job that fetches all stations from the MVG API
and stores them in the local database for fast, reliable access.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.database import AsyncSessionFactory
from app.persistence.repositories import StationRepository, StationPayload
from app.services.mvg_client import MVGClient

logger = logging.getLogger(__name__)


class StationsSyncJob:
    """Background job for syncing MVG stations to database."""

    def __init__(self, batch_size: int = 100):
        """
        Initialize the stations sync job.

        Args:
            batch_size: Number of stations to process in each database batch
        """
        self.batch_size = batch_size

    async def run_sync(self) -> dict[str, int]:
        """
        Run a full sync of all MVG stations to the database.

        This method fetches all stations from the MVG API and updates the database
        with any changes or new stations.

        Returns:
            Dictionary with sync statistics:
            - 'total': Total number of stations fetched
            - 'upserted': Number of stations inserted/updated
            - 'errors': Number of errors encountered
        """
        logger.info("Starting MVG stations sync job")
        start_time = datetime.now(timezone.utc)

        stats = {
            "total": 0,
            "upserted": 0,
            "errors": 0
        }

        try:
            # Fetch all stations from MVG API
            mvg_client = MVGClient()
            stations = await mvg_client.get_all_stations()

            if not stations:
                logger.warning("No stations returned from MVG API")
                return stats

            stats["total"] = len(stations)
            logger.info(f"Fetched {len(stations)} stations from MVG API")

            # Convert stations to repository payloads
            station_payloads = [
                StationPayload(
                    station_id=station.id,
                    name=station.name,
                    place=station.place,
                    latitude=station.latitude,
                    longitude=station.longitude,
                    transport_modes=[],  # MVG stations don't include transport modes in basic response
                    timezone="Europe/Berlin"  # Munich timezone
                )
                for station in stations
            ]

            # Process in batches to avoid memory issues
            async with AsyncSessionFactory() as session:
                station_repo = StationRepository(session)

                for i in range(0, len(station_payloads), self.batch_size):
                    batch = station_payloads[i:i + self.batch_size]

                    try:
                        upserted_batch = await station_repo.upsert_stations(batch)
                        stats["upserted"] += len(upserted_batch)
                        logger.info(f"Processed batch {i//self.batch_size + 1}: upserted {len(upserted_batch)} stations")
                    except Exception as e:
                        logger.error(f"Error processing batch {i//self.batch_size + 1}: {e}")
                        stats["errors"] += 1
                        # Continue with next batch rather than failing completely

                # Commit all changes
                await session.commit()

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"Completed MVG stations sync in {duration:.2f}s: {stats}")

        except Exception as e:
            logger.error(f"Fatal error in stations sync job: {e}")
            stats["errors"] += 1

        return stats

    async def get_sync_status(self) -> dict[str, any]:
        """
        Get the current status of stations in the database.

        Returns:
            Dictionary with database station count and other stats
        """
        try:
            async with AsyncSessionFactory() as session:
                station_repo = StationRepository(session)
                count = await station_repo.count_stations()

                # Get a sample of stations to verify data quality
                sample_stations = await station_repo.get_all_stations()
                sample_size = min(5, len(sample_stations))

                return {
                    "total_stations": count,
                    "sample_stations": [
                        {
                            "id": station.station_id,
                            "name": station.name,
                            "place": station.place,
                        }
                        for station in sample_stations[:sample_size]
                    ],
                    "last_checked": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                "total_stations": 0,
                "sample_stations": [],
                "last_checked": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }


# Global job instance
stations_sync_job = StationsSyncJob()


async def run_stations_sync() -> dict[str, int]:
    """
    Convenience function to run the stations sync job.

    Returns:
        Sync statistics dictionary
    """
    return await stations_sync_job.run_sync()


async def get_stations_sync_status() -> dict[str, any]:
    """
    Convenience function to get stations sync status.

    Returns:
        Status dictionary with station counts and sample data
    """
    return await stations_sync_job.get_sync_status()