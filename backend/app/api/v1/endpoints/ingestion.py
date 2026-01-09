"""
System ingestion status endpoint.

Provides status information about GTFS static feed imports and
GTFS-RT realtime harvester.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.gtfs import GTFSFeedInfo
from app.models.ingestion import (
    GTFSFeedStatus,
    GTFSRTHarvesterStatus,
    IngestionStatus,
)
from app.persistence.models import RealtimeStationStats

router = APIRouter()

_REALTIME_STATS_TABLE_NAME = "realtime_station_stats"


async def _get_realtime_stats_row_count_estimate(session: AsyncSession) -> int:
    """
    Return a fast, approximate row count for realtime station stats.

    Exact `COUNT(*)` on a large table can be slow and can time out the frontend
    monitoring view. For monitoring, an estimate is sufficient.
    """
    try:
        # Prefer live tuple estimate (updated by autovacuum/analyze).
        stmt = text(
            """
            select n_live_tup::bigint
            from pg_stat_all_tables
            where schemaname = current_schema()
              and relname = :table_name
            """
        )
        result = await session.execute(stmt, {"table_name": _REALTIME_STATS_TABLE_NAME})
        estimate = result.scalar_one_or_none()
        if estimate is not None:
            return int(estimate)
    except Exception:
        # Fall back to reltuples.
        pass

    try:
        stmt = text(
            """
            select reltuples::bigint
            from pg_class
            where relname = :table_name
            """
        )
        result = await session.execute(stmt, {"table_name": _REALTIME_STATS_TABLE_NAME})
        estimate = result.scalar_one_or_none()
        if estimate is not None:
            return int(estimate)
    except Exception:
        pass

    # Final fallback: exact count (may be slow on large tables).
    count_stmt = select(func.count(RealtimeStationStats.id))
    count_result = await session.execute(count_stmt)
    return int(count_result.scalar() or 0)


@router.get("/ingestion-status", response_model=IngestionStatus)
async def get_ingestion_status(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> IngestionStatus:
    """Get GTFS static and realtime ingestion status.

    Returns status of:
    - GTFS static feed: last import info, record counts, validity dates
    - GTFS-RT harvester: running status, last harvest info
    """
    # Get latest GTFS feed info
    feed_stmt = (
        select(GTFSFeedInfo).order_by(GTFSFeedInfo.downloaded_at.desc()).limit(1)
    )
    feed_result = await session.execute(feed_stmt)
    feed_info = feed_result.scalar_one_or_none()

    # Check if feed is expired
    today = datetime.now(timezone.utc).date()
    is_expired = False
    if feed_info and feed_info.feed_end_date:
        is_expired = feed_info.feed_end_date < today

    gtfs_feed_status = GTFSFeedStatus(
        feed_id=feed_info.feed_id if feed_info else None,
        feed_url=feed_info.feed_url if feed_info else None,
        downloaded_at=feed_info.downloaded_at if feed_info else None,
        feed_start_date=feed_info.feed_start_date if feed_info else None,
        feed_end_date=feed_info.feed_end_date if feed_info else None,
        stop_count=feed_info.stop_count or 0 if feed_info else 0,
        route_count=feed_info.route_count or 0 if feed_info else 0,
        trip_count=feed_info.trip_count or 0 if feed_info else 0,
        is_expired=is_expired,
    )

    # Get harvester status from request.state (populated by lifespan yield dict)
    harvester_status = GTFSRTHarvesterStatus()
    # FastAPI shallow-copies the lifespan yield dict {"harvester": ...} to request.state
    harvester = getattr(request.state, "harvester", None)
    if harvester:
        status = harvester.get_status()
        harvester_status = GTFSRTHarvesterStatus(
            is_running=status.get("is_running", False),
            last_harvest_at=status.get("last_harvest_at"),
            stations_updated_last_harvest=status.get(
                "stations_updated_last_harvest", 0
            ),
        )

    # Get total stats record count
    harvester_status.total_stats_records = await _get_realtime_stats_row_count_estimate(
        session
    )

    return IngestionStatus(
        gtfs_feed=gtfs_feed_status,
        gtfs_rt_harvester=harvester_status,
    )
