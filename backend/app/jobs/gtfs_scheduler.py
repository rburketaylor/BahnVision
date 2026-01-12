import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import Settings
from app.core.database import get_session
from app.services.gtfs_feed import GTFSFeedImporter

logger = logging.getLogger(__name__)


class GTFSFeedScheduler:
    """Manages scheduled GTFS feed updates."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs."""
        # Daily GTFS feed update
        self.scheduler.add_job(
            func=self._update_gtfs_feed,
            trigger=IntervalTrigger(hours=self.settings.gtfs_update_interval_hours),
            id="gtfs_feed_update",
            name="Update GTFS feed",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    async def start(self):
        """Start the scheduler."""
        logger.info("Starting GTFS feed scheduler")
        self.scheduler.start()

        # Run initial feed update in background (don't block server startup)
        asyncio.create_task(self._check_and_update_feed())

    async def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping GTFS feed scheduler")
        self.scheduler.shutdown(wait=False)

    async def _update_gtfs_feed(self):
        """Update GTFS feed."""
        logger.info("Starting scheduled GTFS feed update")

        try:
            async for session in get_session():
                importer = GTFSFeedImporter(session, self.settings)
                feed_id = await importer.import_feed()
                logger.info(f"Successfully updated GTFS feed: {feed_id}")
                break

        except Exception as e:
            logger.error(f"Failed to update GTFS feed: {e}")

    async def _check_and_update_feed(self):
        """Check if feed needs updating and update if necessary."""
        try:
            async for session in get_session():
                # Check latest feed info
                from sqlalchemy import select
                from app.models.gtfs import GTFSFeedInfo

                stmt = (
                    select(GTFSFeedInfo)
                    .order_by(GTFSFeedInfo.downloaded_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                latest_feed = result.scalar_one_or_none()

                should_update = False

                if latest_feed is None:
                    logger.info("No GTFS feed found, performing initial import")
                    should_update = True
                else:
                    # Check if feed is expired (past feed_end_date)
                    today = datetime.now(timezone.utc).date()
                    feed_expired = (
                        latest_feed.feed_end_date is not None
                        and latest_feed.feed_end_date < today
                    )

                    # Check if feed download is too old
                    # Ensure downloaded_at is timezone-aware for comparison
                    downloaded_at = latest_feed.downloaded_at
                    if downloaded_at.tzinfo is None:
                        downloaded_at = downloaded_at.replace(tzinfo=timezone.utc)

                    age_hours = (
                        datetime.now(timezone.utc) - downloaded_at
                    ).total_seconds() / 3600

                    if feed_expired:
                        logger.info(
                            f"GTFS feed expired (end_date: {latest_feed.feed_end_date}), updating"
                        )
                        should_update = True
                    elif age_hours > self.settings.gtfs_max_feed_age_hours:
                        logger.info(f"GTFS feed is {age_hours:.1f} hours old, updating")
                        should_update = True
                    else:
                        logger.info(
                            f"GTFS feed is current (age: {age_hours:.1f}h, "
                            f"valid until: {latest_feed.feed_end_date})"
                        )

                if should_update:
                    importer = GTFSFeedImporter(session, self.settings)
                    feed_id = await importer.import_feed()
                    logger.info(f"Successfully imported GTFS feed: {feed_id}")

                break

        except Exception as e:
            logger.error(f"Failed to check/update GTFS feed: {e}")

    def get_job_info(self) -> dict:
        """Get information about scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            # APScheduler v4 might not have next_run_time until scheduler starts
            next_run = getattr(job, "next_run_time", None)
            jobs.append(
                {
                    "id": job.id,
                    "name": getattr(job, "name", "Unknown"),
                    "next_run": (next_run.isoformat() if next_run else None),
                    "trigger": str(getattr(job, "trigger", "Unknown")),
                }
            )

        return {
            "scheduler_running": self.scheduler.running,
            "jobs": jobs,
        }
