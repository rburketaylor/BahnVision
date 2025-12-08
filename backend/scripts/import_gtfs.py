#!/usr/bin/env python3
"""
Import GTFS feed into the database.

Usage:
    python scripts/import_gtfs.py [URL_OR_PATH]

Examples:
    python scripts/import_gtfs.py  # Uses GTFS_FEED_URL from env
    python scripts/import_gtfs.py https://download.gtfs.de/germany/free/latest.zip
    python scripts/import_gtfs.py /tmp/gtfs/gtfs_feed.zip  # Use local file
"""
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(feed_source: str | None = None):
    """Import GTFS feed."""
    from app.core.config import get_settings
    from app.core.database import get_session
    from app.services.gtfs_feed import GTFSFeedImporter

    settings = get_settings()

    # Check if feed_source is a local file
    local_path = None
    feed_url = None

    if feed_source:
        if Path(feed_source).exists():
            local_path = Path(feed_source)
            logger.info(f"Using local file: {local_path}")
        else:
            feed_url = feed_source
            logger.info(f"Downloading from: {feed_url}")
    else:
        feed_url = settings.gtfs_feed_url
        logger.info(f"Downloading from: {feed_url}")

    logger.info(f"Storage path: {settings.gtfs_storage_path}")
    logger.info("This may take several minutes for large feeds...")

    async for session in get_session():
        importer = GTFSFeedImporter(session, settings)
        if local_path:
            feed_id = await importer.import_from_path(local_path)
        else:
            feed_id = await importer.import_feed(feed_url=feed_url)
        logger.info(f"Successfully imported: {feed_id}")
        break


if __name__ == "__main__":
    feed_source = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(feed_source))
