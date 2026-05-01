"""
Pydantic models for ingestion status API responses.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class GTFSImportProgress(BaseModel):
    """Live progress of the GTFS static feed import."""

    state: str = "idle"
    phase: str | None = None
    message: str | None = None
    percent: float | None = None
    rows_processed: int | None = None
    rows_total: int | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    error_type: str | None = None
    error_message: str | None = None


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
    import_progress: GTFSImportProgress = Field(default_factory=GTFSImportProgress)


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
