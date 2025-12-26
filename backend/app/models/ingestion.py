"""
Pydantic models for ingestion status API responses.
"""

from datetime import date, datetime

from pydantic import BaseModel


class GTFSFeedStatus(BaseModel):
    """Status of the GTFS static feed import."""

    feed_id: str | None = None
    feed_url: str | None = None
    downloaded_at: datetime | None = None
    feed_start_date: date | None = None
    feed_end_date: date | None = None
    stop_count: int = 0
    route_count: int = 0
    trip_count: int = 0
    is_expired: bool = False


class GTFSRTHarvesterStatus(BaseModel):
    """Status of the GTFS-RT realtime harvester."""

    is_running: bool = False
    last_harvest_at: datetime | None = None
    stations_updated_last_harvest: int = 0
    total_stats_records: int = 0


class IngestionStatus(BaseModel):
    """Combined ingestion status for GTFS static and realtime data."""

    gtfs_feed: GTFSFeedStatus
    gtfs_rt_harvester: GTFSRTHarvesterStatus
