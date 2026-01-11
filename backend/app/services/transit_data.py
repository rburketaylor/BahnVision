"""
Combined Transit Data Service

Integrates static GTFS schedule data with real-time updates to provide
a unified view of transit information including:
- Departures with real-time delays
- Route information with service alerts
- Vehicle tracking
- Stop information
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.services.cache import CacheService
from app.models.gtfs import GTFSStop, GTFSRoute

logger = logging.getLogger(__name__)

# Import with fallbacks for missing dependencies
try:
    from app.services.gtfs_schedule import GTFSScheduleService, ScheduledDeparture

    GTFS_SCHEDULE_AVAILABLE = True
except ImportError as e:
    GTFSScheduleService = None  # type: ignore[misc,assignment]
    ScheduledDeparture = None  # type: ignore[misc,assignment]
    GTFS_SCHEDULE_AVAILABLE = False
    logger.warning(f"GTFS schedule service not available: {e}")

try:
    from app.services.gtfs_realtime import (
        GtfsRealtimeService,
        TripUpdate,
        VehiclePosition,
        ServiceAlert,
    )

    GTFS_REALTIME_AVAILABLE = True
except ImportError as e:
    GtfsRealtimeService = None  # type: ignore[misc,assignment]
    TripUpdate = None  # type: ignore[misc,assignment]
    VehiclePosition = None  # type: ignore[misc,assignment]
    ServiceAlert = None  # type: ignore[misc,assignment]
    GTFS_REALTIME_AVAILABLE = False
    logger.warning(f"GTFS realtime service not available: {e}")


class ScheduleRelationship(Enum):
    """Schedule relationship for stop times"""

    SCHEDULED = "SCHEDULED"
    SKIPPED = "SKIPPED"
    NO_DATA = "NO_DATA"
    UNSCHEDULED = "UNSCHEDULED"


@dataclass
class DepartureInfo:
    """Combined departure information with real-time updates"""

    trip_id: str
    route_id: str
    route_short_name: str
    route_long_name: str
    trip_headsign: str
    stop_id: str
    stop_name: str
    scheduled_departure: datetime
    scheduled_arrival: Optional[datetime] = None
    real_time_departure: Optional[datetime] = None
    real_time_arrival: Optional[datetime] = None
    departure_delay_seconds: Optional[int] = None
    arrival_delay_seconds: Optional[int] = None
    schedule_relationship: ScheduleRelationship = ScheduleRelationship.SCHEDULED
    vehicle_id: Optional[str] = None
    vehicle_position: Optional[Dict] = None
    alerts: Optional[List] = None  # ServiceAlert list

    def __post_init__(self) -> None:
        if self.alerts is None:
            self.alerts = []

    def to_dict(self) -> Dict:
        """Convert to dictionary with JSON-serializable values"""
        data = asdict(self)

        # Convert enums to string
        if isinstance(self.schedule_relationship, ScheduleRelationship):
            data["schedule_relationship"] = self.schedule_relationship.value

        # Convert datetimes to ISO format strings
        for field in [
            "scheduled_departure",
            "scheduled_arrival",
            "real_time_departure",
            "real_time_arrival",
        ]:
            if data.get(field):
                data[field] = data[field].isoformat()

        # Handle alerts list - serialize ServiceAlert objects
        if self.alerts:
            serialized_alerts = []
            for alert in self.alerts:
                # If alert is a dataclass (ServiceAlert), use asdict
                # We need to handle set types in ServiceAlert manually
                alert_dict = asdict(alert)

                # Convert sets to lists for JSON serialization
                if "affected_routes" in alert_dict and isinstance(
                    alert_dict["affected_routes"], set
                ):
                    alert_dict["affected_routes"] = list(alert_dict["affected_routes"])
                if "affected_stops" in alert_dict and isinstance(
                    alert_dict["affected_stops"], set
                ):
                    alert_dict["affected_stops"] = list(alert_dict["affected_stops"])

                # Convert datetimes in alerts
                for alert_field in ["start_time", "end_time", "timestamp"]:
                    if alert_dict.get(alert_field):
                        alert_dict[alert_field] = alert_dict[alert_field].isoformat()

                serialized_alerts.append(alert_dict)
            data["alerts"] = serialized_alerts

        return data

    @staticmethod
    def from_dict(data: Dict) -> "DepartureInfo":
        """Create from dictionary handling type conversions.

        Note: This method creates a shallow copy of the input dict to avoid
        mutating the caller's data.
        """
        # Copy to avoid mutating the input
        data = data.copy()

        # Convert string to enum
        if "schedule_relationship" in data:
            data["schedule_relationship"] = ScheduleRelationship(
                data["schedule_relationship"]
            )

        # Convert ISO strings back to datetime
        for field in [
            "scheduled_departure",
            "scheduled_arrival",
            "real_time_departure",
            "real_time_arrival",
        ]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Reconstruct ServiceAlert objects
        if data.get("alerts") and GTFS_REALTIME_AVAILABLE and ServiceAlert is not None:
            alerts = []
            for alert_data in data["alerts"]:
                # Copy alert data to avoid mutating nested structures
                alert_data = alert_data.copy()
                # Convert lists back to sets
                if "affected_routes" in alert_data:
                    alert_data["affected_routes"] = set(alert_data["affected_routes"])
                if "affected_stops" in alert_data:
                    alert_data["affected_stops"] = set(alert_data["affected_stops"])

                # Convert ISO strings back to datetime
                for alert_field in ["start_time", "end_time", "timestamp"]:
                    if alert_data.get(alert_field):
                        alert_data[alert_field] = datetime.fromisoformat(
                            alert_data[alert_field]
                        )

                alerts.append(ServiceAlert(**alert_data))
            data["alerts"] = alerts
        elif data.get("alerts") and not GTFS_REALTIME_AVAILABLE:
            # If realtime service is not available, we can't reconstruct ServiceAlert objects
            logger.warning(
                f"Discarding {len(data['alerts'])} cached alerts: GTFS-RT service unavailable"
            )
            data["alerts"] = []

        return DepartureInfo(**data)


@dataclass
class RouteInfo:
    """Route information with real-time status"""

    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    route_color: str
    route_text_color: str
    active_trips: int = 0
    alerts: Optional[List] = None  # ServiceAlert list

    def __post_init__(self) -> None:
        if self.alerts is None:
            self.alerts = []


@dataclass
class StopInfo:
    """Stop information with real-time status"""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    zone_id: Optional[str] = None
    wheelchair_boarding: int = 0
    upcoming_departures: Optional[List] = None  # DepartureInfo list
    alerts: Optional[List] = None  # ServiceAlert list

    def __post_init__(self) -> None:
        if self.upcoming_departures is None:
            self.upcoming_departures = []
        if self.alerts is None:
            self.alerts = []


class TransitDataService:
    """Combined service for static and real-time transit data"""

    def __init__(
        self,
        cache_service: CacheService,
        gtfs_schedule,  # Remove type hint to avoid import issues
        gtfs_realtime,  # Remove type hint to avoid import issues
        db_session: AsyncSession,
    ):
        self.settings = get_settings()
        self.cache = cache_service
        self.gtfs_schedule = gtfs_schedule
        self.gtfs_realtime = gtfs_realtime
        self.db = db_session

    async def get_departures_for_stop(
        self,
        stop_id: str,
        limit: int = 10,
        offset_minutes: int = 0,
        include_real_time: bool = True,
    ) -> List[DepartureInfo]:
        """Get departures for a stop with optional real-time updates.

        Results are cached for 15 seconds to prevent thundering herd on popular stops
        while keeping real-time data reasonably fresh.
        """
        try:
            # Cache key without time bucket - use stale-while-revalidate instead
            cache_key = (
                f"departures:{stop_id}:{limit}:{offset_minutes}:{include_real_time}"
            )

            # Try to get from cache (fresh or stale)
            try:
                cached_data = await self.cache.get_json(cache_key)
                if cached_data:
                    return [DepartureInfo.from_dict(d) for d in cached_data]

                # Try stale fallback if fresh cache miss
                stale_data = await self.cache.get_stale_json(cache_key)
                if stale_data:
                    logger.info(f"Serving stale departures for {stop_id}")
                    return [DepartureInfo.from_dict(d) for d in stale_data]
            except Exception as cache_error:
                logger.warning(
                    f"Failed to read from cache for {stop_id}: {cache_error}"
                )

            # Get scheduled departures
            scheduled_time = datetime.now(timezone.utc) + timedelta(
                minutes=offset_minutes
            )
            scheduled_departures = await self.gtfs_schedule.get_departures_for_stop(
                stop_id, scheduled_time, limit
            )

            if not scheduled_departures:
                return []

            # Get stop information (uses cached get_stop_info)
            stop_info_obj = await self.get_stop_info(stop_id, include_departures=False)
            if not stop_info_obj:
                logger.warning(f"Stop {stop_id} not found")
                return []

            # Convert to departure info
            departures = []
            for dep in scheduled_departures:
                # We use route info directly from the scheduled departure which
                # already joins with the route table. This avoids a redundant
                # cache/DB lookup.
                departure_info = DepartureInfo(
                    trip_id=str(dep.trip_id),
                    route_id=str(dep.route_id),
                    route_short_name=str(dep.route_short_name or ""),
                    route_long_name=str(dep.route_long_name or ""),
                    trip_headsign=str(dep.trip_headsign or ""),
                    stop_id=str(stop_id),
                    stop_name=str(stop_info_obj.stop_name),
                    scheduled_departure=dep.departure_time,
                    scheduled_arrival=dep.arrival_time,
                    schedule_relationship=ScheduleRelationship.SCHEDULED,
                )
                departures.append(departure_info)

            # Apply real-time updates if requested
            if include_real_time and self.is_realtime_available():
                await self._apply_real_time_updates(departures, stop_id)

            # Cache the result
            # We use a short TTL (10 seconds) because this includes real-time data
            # which changes frequently. The main benefit is preventing thundering herd
            # for popular stops.
            try:
                serialized_departures = [d.to_dict() for d in departures]
                await self.cache.set_json(
                    cache_key,
                    serialized_departures,
                    ttl_seconds=self.settings.transit_departures_cache_ttl_seconds,
                    stale_ttl_seconds=self.settings.transit_departures_cache_stale_ttl_seconds,
                )
            except Exception as cache_error:
                logger.warning(
                    f"Failed to cache departures for {stop_id}: {cache_error}"
                )

            return departures

        except Exception as e:
            logger.error(f"Failed to get departures for stop {stop_id}: {e}")
            return []

    def is_realtime_available(self) -> bool:
        """Return True if GTFS-RT is enabled and a realtime service is configured."""
        return bool(self.settings.gtfs_rt_enabled and self.gtfs_realtime is not None)

    async def get_route_info(
        self, route_id: str, include_real_time: bool = True
    ) -> Optional[RouteInfo]:
        """Get route information with real-time status"""
        try:
            cache_key = f"route:{route_id}:{include_real_time}"
            cached_result = await self.cache.get_json(cache_key)
            if cached_result:
                return RouteInfo(**cached_result)

            # Get route from database
            stmt = select(GTFSRoute).where(GTFSRoute.route_id == route_id)
            result = await self.db.execute(stmt)
            route = result.scalar_one_or_none()

            if not route:
                return None

            route_info = RouteInfo(
                route_id=str(route.route_id),
                route_short_name=str(route.route_short_name or ""),
                route_long_name=str(route.route_long_name or ""),
                route_type=int(route.route_type),
                route_color=str(route.route_color or ""),
                route_text_color="",  # Not in GTFS model
            )

            # Get real-time alerts if requested
            if include_real_time:
                route_info.alerts = await self.gtfs_realtime.get_alerts_for_route(
                    route_id
                )

            # Cache the result
            await self.cache.set_json(
                cache_key,
                asdict(route_info),
                ttl_seconds=self.settings.gtfs_schedule_cache_ttl_seconds,
            )

            return route_info

        except Exception as e:
            logger.error(f"Failed to get route info for {route_id}: {e}")
            return None

    async def get_stop_info(
        self, stop_id: str, include_departures: bool = False
    ) -> Optional[StopInfo]:
        """Get stop information with optional departures"""
        try:
            cache_key = f"stop:{stop_id}:{include_departures}"
            cached_result = await self.cache.get_json(cache_key)
            if cached_result:
                return StopInfo(**cached_result)

            # Get stop from database
            stmt = select(GTFSStop).where(GTFSStop.stop_id == stop_id)
            result = await self.db.execute(stmt)
            stop = result.scalar_one_or_none()

            if not stop:
                return None

            stop_info = StopInfo(
                stop_id=str(stop.stop_id),
                stop_name=str(stop.stop_name),
                stop_lat=float(stop.stop_lat),
                stop_lon=float(stop.stop_lon),
                zone_id=None,  # Not in GTFS model
                wheelchair_boarding=0,  # Not in GTFS model
            )

            # Get upcoming departures if requested
            if include_departures:
                stop_info.upcoming_departures = await self.get_departures_for_stop(
                    stop_id, limit=5
                )

            # Cache the result
            await self.cache.set_json(
                cache_key,
                asdict(stop_info),
                ttl_seconds=self.settings.gtfs_stop_cache_ttl_seconds,
            )

            return stop_info

        except Exception as e:
            logger.error(f"Failed to get stop info for {stop_id}: {e}")
            return None

    async def search_stops(self, query: str, limit: int = 10) -> List[StopInfo]:
        """Search for stops by name with caching."""
        try:
            # Normalize query for consistent cache keys
            normalized_query = query.strip().lower()
            cache_key = f"stop_search:{normalized_query}:{limit}"

            # Try cache first
            try:
                cached_data = await self.cache.get_json(cache_key)
                if cached_data:
                    return [StopInfo(**s) for s in cached_data]
            except Exception as cache_error:
                logger.warning(f"Failed to read stop search from cache: {cache_error}")

            # Cache miss - query database
            stops = await self.gtfs_schedule.search_stops(query, limit)

            stop_infos = []
            for stop in stops:
                stop_info = StopInfo(
                    stop_id=str(stop.stop_id),
                    stop_name=str(stop.stop_name),
                    stop_lat=float(stop.stop_lat) if stop.stop_lat else 0.0,
                    stop_lon=float(stop.stop_lon) if stop.stop_lon else 0.0,
                    zone_id=None,
                    wheelchair_boarding=0,
                )
                stop_infos.append(stop_info)

            # Cache the result
            try:
                serialized = [asdict(s) for s in stop_infos]
                await self.cache.set_json(
                    cache_key,
                    serialized,
                    ttl_seconds=self.settings.transit_station_search_cache_ttl_seconds,
                    stale_ttl_seconds=self.settings.transit_station_search_cache_stale_ttl_seconds,
                )
            except Exception as cache_error:
                logger.warning(f"Failed to cache stop search: {cache_error}")

            return stop_infos

        except Exception as e:
            logger.error(f"Failed to search stops for query '{query}': {e}")
            return []

    async def get_vehicle_position(self, vehicle_id: str) -> Optional[VehiclePosition]:
        """Get real-time vehicle position"""
        return await self.gtfs_realtime.get_vehicle_position(vehicle_id)

    async def refresh_real_time_data(self) -> Dict[str, int]:
        """Refresh all real-time data and return counts"""
        try:
            # Fetch all real-time data types
            trip_updates_task = self.gtfs_realtime.fetch_trip_updates()
            vehicle_positions_task = self.gtfs_realtime.fetch_vehicle_positions()
            alerts_task = self.gtfs_realtime.fetch_alerts()

            results = await asyncio.gather(
                trip_updates_task,
                vehicle_positions_task,
                alerts_task,
                return_exceptions=True,
            )
            trip_updates_result = results[0]
            vehicle_positions_result = results[1]
            alerts_result = results[2]

            # Handle exceptions
            trip_updates_count = (
                len(trip_updates_result)
                if not isinstance(trip_updates_result, BaseException)
                else 0
            )
            vehicle_positions_count = (
                len(vehicle_positions_result)
                if not isinstance(vehicle_positions_result, BaseException)
                else 0
            )
            alerts_count = (
                len(alerts_result)
                if not isinstance(alerts_result, BaseException)
                else 0
            )

            # Log any errors
            if isinstance(trip_updates_result, BaseException):
                logger.error(f"Failed to fetch trip updates: {trip_updates_result}")
            if isinstance(vehicle_positions_result, BaseException):
                logger.error(
                    f"Failed to fetch vehicle positions: {vehicle_positions_result}"
                )
            if isinstance(alerts_result, BaseException):
                logger.error(f"Failed to fetch alerts: {alerts_result}")

            logger.info(
                f"Real-time data refresh: {trip_updates_count} trip updates, "
                f"{vehicle_positions_count} vehicle positions, {alerts_count} alerts"
            )

            return {
                "trip_updates": trip_updates_count,
                "vehicle_positions": vehicle_positions_count,
                "alerts": alerts_count,
            }

        except Exception as e:
            logger.error(f"Failed to refresh real-time data: {e}")
            return {"trip_updates": 0, "vehicle_positions": 0, "alerts": 0}

    async def _get_stop_info(self, stop_id: str) -> Optional[GTFSStop]:
        """Get stop information from database"""
        try:
            stmt = select(GTFSStop).where(GTFSStop.stop_id == stop_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get stop info for {stop_id}: {e}")
            return None

    async def _get_route_info_batch(self, route_ids: Set[str]) -> Dict[str, GTFSRoute]:
        """Get route information for multiple routes"""
        try:
            stmt = select(GTFSRoute).where(GTFSRoute.route_id.in_(route_ids))
            result = await self.db.execute(stmt)
            routes = result.scalars().all()
            return {str(route.route_id): route for route in routes}
        except Exception as e:
            logger.error(f"Failed to get route info batch: {e}")
            return {}

    async def _get_route_info_batch_cached(
        self, route_ids: Set[str]
    ) -> Dict[str, GTFSRoute]:
        """Get route information for multiple routes, using cache where available."""
        if not route_ids:
            return {}

        result: Dict[str, GTFSRoute] = {}
        uncached_ids: Set[str] = set()

        # Try cache first for each route
        # Use the same format as get_route_info/get_stop_info
        # route:{route_id}:{include_real_time}
        route_id_list = list(route_ids)
        cache_keys = [f"route:{rid}:False" for rid in route_id_list]
        try:
            # We need to handle mget_json result mapping back to route_ids
            cached_data = await self.cache.mget_json(cache_keys)
            for route_id, key in zip(route_id_list, cache_keys):
                data = cached_data.get(key)
                if data:
                    result[route_id] = SimpleNamespace(**data)  # type: ignore[assignment]
                else:
                    uncached_ids.add(route_id)
        except Exception:
            uncached_ids = set(route_ids)

        # Fetch uncached from DB
        if uncached_ids:
            db_routes = await self._get_route_info_batch(uncached_ids)
            result.update(db_routes)

            # Optimistically cache these for next time if not already cached
            # (get_route_info normally handles this, but here we did a batch fetch)
            for rid, route in db_routes.items():
                try:
                    # Match RouteInfo-like structure for cache
                    route_info_dict = {
                        "route_id": str(route.route_id),
                        "route_short_name": str(route.route_short_name or ""),
                        "route_long_name": str(route.route_long_name or ""),
                        "route_type": int(route.route_type),
                        "route_color": str(route.route_color or ""),
                        "route_text_color": "",
                    }
                    await self.cache.set_json(
                        f"route:{rid}:False",
                        route_info_dict,
                        ttl_seconds=self.settings.gtfs_schedule_cache_ttl_seconds,
                    )
                except Exception:
                    pass

        return result

    async def _apply_real_time_updates(
        self, departures: List[DepartureInfo], stop_id: str
    ):
        """Apply real-time updates to scheduled departures"""
        try:
            # Prepare tasks for concurrent execution
            # 1. Get trip updates for this stop
            trip_updates_task = self.gtfs_realtime.get_trip_updates_for_stop(stop_id)

            # 2. Get vehicle positions for active trips (batch fetch)
            trip_ids = list({dep.trip_id for dep in departures})
            vehicle_positions_task = self.gtfs_realtime.get_vehicle_positions_by_trips(
                trip_ids
            )

            # Execute both requests in parallel to reduce latency
            trip_updates, vehicle_positions = await asyncio.gather(
                trip_updates_task, vehicle_positions_task
            )

            # Create lookup map
            update_map = {}
            for tu in trip_updates:
                key = (tu.trip_id, tu.stop_id)
                update_map[key] = tu

            # Apply updates to departures
            for departure in departures:
                # Apply trip updates
                key = (departure.trip_id, departure.stop_id)
                if key in update_map:
                    tu = update_map[key]

                    # Update times
                    if tu.arrival_delay is not None and departure.scheduled_arrival:
                        departure.real_time_arrival = (
                            departure.scheduled_arrival
                            + timedelta(seconds=tu.arrival_delay)
                        )
                        departure.arrival_delay_seconds = tu.arrival_delay

                    if tu.departure_delay is not None:
                        departure.real_time_departure = (
                            departure.scheduled_departure
                            + timedelta(seconds=tu.departure_delay)
                        )
                        departure.departure_delay_seconds = tu.departure_delay

                    # Update schedule relationship
                    departure.schedule_relationship = ScheduleRelationship(
                        tu.schedule_relationship
                    )

                # Apply vehicle positions
                vehicle_pos = vehicle_positions.get(departure.trip_id)
                if vehicle_pos:
                    departure.vehicle_id = vehicle_pos.vehicle_id
                    departure.vehicle_position = {
                        "latitude": vehicle_pos.latitude,
                        "longitude": vehicle_pos.longitude,
                        "bearing": vehicle_pos.bearing,
                        "speed": vehicle_pos.speed,
                    }

        except Exception as e:
            logger.error(f"Failed to apply real-time updates for stop {stop_id}: {e}")
