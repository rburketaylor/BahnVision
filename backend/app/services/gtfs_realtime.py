"""
GTFS Real-Time Stream Processing Service

Handles fetching, parsing, and storing GTFS-RT data including:
- Trip updates (delays, cancellations)
- Vehicle positions
- Alerts
- Service alerts
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Set
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.services.cache import CacheService

# Import GTFS-RT bindings with fallback
try:
    from google.transit import gtfs_realtime_pb2

    FeedMessage = gtfs_realtime_pb2.FeedMessage
    GTFS_RT_AVAILABLE = True
except ImportError:
    try:
        import gtfs_realtime_bindings

        FeedMessage = gtfs_realtime_bindings.FeedMessage
        GTFS_RT_AVAILABLE = True
    except ImportError:
        FeedMessage = None
        GTFS_RT_AVAILABLE = False
        logging.warning(
            "gtfs_realtime_bindings not available, GTFS-RT functionality disabled"
        )

logger = logging.getLogger(__name__)


@dataclass
class TripUpdate:
    """Processed trip update data"""

    trip_id: str
    route_id: str
    stop_id: str
    stop_sequence: int
    arrival_delay: Optional[int] = None  # seconds
    departure_delay: Optional[int] = None  # seconds
    schedule_relationship: str = "SCHEDULED"
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class VehiclePosition:
    """Processed vehicle position data"""

    trip_id: str
    vehicle_id: str
    route_id: str
    latitude: float
    longitude: float
    bearing: Optional[float] = None
    speed: Optional[float] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class ServiceAlert:
    """Processed service alert data"""

    alert_id: str
    cause: str
    effect: str
    header_text: str
    description_text: str
    affected_routes: Set[str]
    affected_stops: Set[str]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class GtfsRealtimeService:
    """Service for processing GTFS-RT data streams"""

    def __init__(self, cache_service: CacheService):
        self.settings = get_settings()
        self.cache = cache_service
        self._circuit_breaker_state = {
            "failures": 0,
            "last_failure": None,
            "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
        }

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows requests"""
        state = self._circuit_breaker_state

        if state["state"] == "OPEN":
            # Check if we should try half-open
            last_failure = state["last_failure"]
            if (
                isinstance(last_failure, datetime)
                and (datetime.now(timezone.utc) - last_failure).seconds
                > self.settings.gtfs_rt_circuit_breaker_recovery_seconds
            ):
                state["state"] = "HALF_OPEN"
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False

        return True

    def _record_success(self):
        """Record successful request"""
        state = self._circuit_breaker_state
        state["failures"] = 0
        state["state"] = "CLOSED"

    def _record_failure(self):
        """Record failed request"""
        state = self._circuit_breaker_state
        state["failures"] += 1
        state["last_failure"] = datetime.now(timezone.utc)

        if state["failures"] >= self.settings.gtfs_rt_circuit_breaker_threshold:
            state["state"] = "OPEN"
            logger.warning(f"Circuit breaker OPENED after {state['failures']} failures")

    async def fetch_and_process_feed(self) -> dict[str, int]:
        """Fetch and process all GTFS-RT data from a single feed.

        Optimized to download and parse the feed only once, reducing network
        overhead and CPU usage significantly compared to fetching types individually.
        """
        if not GTFS_RT_AVAILABLE:
            logger.warning("GTFS-RT bindings not available, skipping fetch")
            return {"trip_updates": 0, "vehicle_positions": 0, "alerts": 0}

        if not self._check_circuit_breaker():
            logger.warning("Circuit breaker OPEN, skipping fetch")
            return {"trip_updates": 0, "vehicle_positions": 0, "alerts": 0}

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gtfs_rt_timeout_seconds,
                headers={
                    "User-Agent": "BahnVision-GTFS-RT/1.0",
                    "Accept-Encoding": "gzip, deflate, br",
                },
            ) as client:
                response = await client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            if not FeedMessage:
                logger.warning("FeedMessage not available")
                return {"trip_updates": 0, "vehicle_positions": 0, "alerts": 0}

            feed = FeedMessage()
            feed.ParseFromString(response.content)

            trip_updates = []
            vehicle_positions = []
            alerts: List[ServiceAlert] = []

            for entity in feed.entity:
                # Process TripUpdate
                if entity.HasField("trip_update"):
                    tu = entity.trip_update
                    if tu.trip.trip_id:
                        for stop_time_update in tu.stop_time_update:
                            if stop_time_update.stop_id:
                                trip_updates.append(
                                    TripUpdate(
                                        trip_id=tu.trip.trip_id,
                                        route_id=tu.trip.route_id or "",
                                        stop_id=stop_time_update.stop_id,
                                        stop_sequence=stop_time_update.stop_sequence,
                                        arrival_delay=(
                                            stop_time_update.arrival.delay
                                            if stop_time_update.HasField("arrival")
                                            else None
                                        ),
                                        departure_delay=(
                                            stop_time_update.departure.delay
                                            if stop_time_update.HasField("departure")
                                            else None
                                        ),
                                        schedule_relationship=self._map_schedule_relationship(
                                            stop_time_update.schedule_relationship
                                        ),
                                    )
                                )

                # Process VehiclePosition
                if entity.HasField("vehicle"):
                    v = entity.vehicle
                    if v.vehicle.id:
                        vehicle_positions.append(
                            VehiclePosition(
                                trip_id=v.trip.trip_id if v.HasField("trip") else "",
                                vehicle_id=v.vehicle.id,
                                route_id=v.trip.route_id if v.HasField("trip") else "",
                                latitude=(
                                    v.position.latitude
                                    if v.HasField("position")
                                    else 0.0
                                ),
                                longitude=(
                                    v.position.longitude
                                    if v.HasField("position")
                                    else 0.0
                                ),
                                bearing=(
                                    v.position.bearing
                                    if v.HasField("position")
                                    else None
                                ),
                                speed=(
                                    v.position.speed if v.HasField("position") else None
                                ),
                            )
                        )

                # Process Alert
                if entity.HasField("alert"):
                    alert = entity.alert
                    alert_id = entity.id or f"alert_{len(alerts)}"

                    affected_routes = set()
                    affected_stops = set()

                    for informed_entity in alert.informed_entity:
                        if (
                            informed_entity.HasField("route_id")
                            and informed_entity.route_id
                        ):
                            affected_routes.add(informed_entity.route_id)
                        if (
                            informed_entity.HasField("stop_id")
                            and informed_entity.stop_id
                        ):
                            affected_stops.add(informed_entity.stop_id)

                    alerts.append(
                        ServiceAlert(
                            alert_id=alert_id,
                            cause=self._map_cause(alert.cause),
                            effect=self._map_effect(alert.effect),
                            header_text=self._extract_text(alert.header_text),
                            description_text=self._extract_text(alert.description_text),
                            affected_routes=affected_routes,
                            affected_stops=affected_stops,
                            start_time=(
                                datetime.fromtimestamp(
                                    alert.active_period[0].start, timezone.utc
                                )
                                if alert.active_period
                                else None
                            ),
                            end_time=(
                                datetime.fromtimestamp(
                                    alert.active_period[0].end, timezone.utc
                                )
                                if alert.active_period
                                else None
                            ),
                        )
                    )

            # Store in cache - parallelize independent storage operations
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._store_trip_updates(trip_updates))
                tg.create_task(self._store_vehicle_positions(vehicle_positions))
                tg.create_task(self._store_alerts(alerts))

            self._record_success()

            logger.info(
                f"Processed feed: {len(trip_updates)} trip updates, "
                f"{len(vehicle_positions)} vehicle positions, "
                f"{len(alerts)} alerts"
            )

            return {
                "trip_updates": len(trip_updates),
                "vehicle_positions": len(vehicle_positions),
                "alerts": len(alerts),
            }

        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch and process GTFS-RT feed: {e}")
            return {"trip_updates": 0, "vehicle_positions": 0, "alerts": 0}

    async def fetch_trip_updates(self) -> List[TripUpdate]:
        """Fetch and process trip updates from GTFS-RT feed (legacy method).

        Consider using fetch_and_process_feed() instead to process all data types at once.
        """
        # Kept for compatibility, but internally inefficient if used alongside others
        if not GTFS_RT_AVAILABLE or not self._check_circuit_breaker():
            return []

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gtfs_rt_timeout_seconds,
                headers={
                    "User-Agent": "BahnVision-GTFS-RT/1.0",
                    "Accept-Encoding": "gzip, deflate, br",
                },
            ) as client:
                response = await client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            if not FeedMessage:
                return []

            feed = FeedMessage()
            feed.ParseFromString(response.content)

            trip_updates = []
            for entity in feed.entity:
                if entity.HasField("trip_update"):
                    tu = entity.trip_update
                    if tu.trip.trip_id:
                        for stop_time_update in tu.stop_time_update:
                            if stop_time_update.stop_id:
                                trip_updates.append(
                                    TripUpdate(
                                        trip_id=tu.trip.trip_id,
                                        route_id=tu.trip.route_id or "",
                                        stop_id=stop_time_update.stop_id,
                                        stop_sequence=stop_time_update.stop_sequence,
                                        arrival_delay=(
                                            stop_time_update.arrival.delay
                                            if stop_time_update.HasField("arrival")
                                            else None
                                        ),
                                        departure_delay=(
                                            stop_time_update.departure.delay
                                            if stop_time_update.HasField("departure")
                                            else None
                                        ),
                                        schedule_relationship=self._map_schedule_relationship(
                                            stop_time_update.schedule_relationship
                                        ),
                                    )
                                )
            await self._store_trip_updates(trip_updates)
            self._record_success()
            return trip_updates
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch trip updates: {e}")
            return []

    async def fetch_vehicle_positions(self) -> List[VehiclePosition]:
        """Fetch and process vehicle positions from GTFS-RT feed (legacy method)."""
        if not GTFS_RT_AVAILABLE or not self._check_circuit_breaker():
            return []

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gtfs_rt_timeout_seconds,
                headers={
                    "User-Agent": "BahnVision-GTFS-RT/1.0",
                    "Accept-Encoding": "gzip, deflate, br",
                },
            ) as client:
                response = await client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            if not FeedMessage:
                return []
            feed = FeedMessage()
            feed.ParseFromString(response.content)

            vehicle_positions = []
            for entity in feed.entity:
                if entity.HasField("vehicle"):
                    v = entity.vehicle
                    if v.vehicle.id:
                        vehicle_positions.append(
                            VehiclePosition(
                                trip_id=v.trip.trip_id if v.HasField("trip") else "",
                                vehicle_id=v.vehicle.id,
                                route_id=v.trip.route_id if v.HasField("trip") else "",
                                latitude=v.position.latitude
                                if v.HasField("position")
                                else 0.0,
                                longitude=v.position.longitude
                                if v.HasField("position")
                                else 0.0,
                                bearing=v.position.bearing
                                if v.HasField("position")
                                else None,
                                speed=v.position.speed
                                if v.HasField("position")
                                else None,
                            )
                        )
            await self._store_vehicle_positions(vehicle_positions)
            self._record_success()
            return vehicle_positions
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch vehicle positions: {e}")
            return []

    async def fetch_alerts(self) -> List[ServiceAlert]:
        """Fetch and process service alerts from GTFS-RT feed (legacy method)."""
        if not GTFS_RT_AVAILABLE or not self._check_circuit_breaker():
            return []

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gtfs_rt_timeout_seconds,
                headers={
                    "User-Agent": "BahnVision-GTFS-RT/1.0",
                    "Accept-Encoding": "gzip, deflate, br",
                },
            ) as client:
                response = await client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            if not FeedMessage:
                return []
            feed = FeedMessage()
            feed.ParseFromString(response.content)

            alerts: List[ServiceAlert] = []
            for entity in feed.entity:
                if entity.HasField("alert"):
                    alert = entity.alert
                    alert_id = entity.id or f"alert_{len(alerts)}"
                    affected_routes = set()
                    affected_stops = set()
                    for informed_entity in alert.informed_entity:
                        if (
                            informed_entity.HasField("route_id")
                            and informed_entity.route_id
                        ):
                            affected_routes.add(informed_entity.route_id)
                        if (
                            informed_entity.HasField("stop_id")
                            and informed_entity.stop_id
                        ):
                            affected_stops.add(informed_entity.stop_id)
                    alerts.append(
                        ServiceAlert(
                            alert_id=alert_id,
                            cause=self._map_cause(alert.cause),
                            effect=self._map_effect(alert.effect),
                            header_text=self._extract_text(alert.header_text),
                            description_text=self._extract_text(alert.description_text),
                            affected_routes=affected_routes,
                            affected_stops=affected_stops,
                            start_time=(
                                datetime.fromtimestamp(
                                    alert.active_period[0].start, timezone.utc
                                )
                                if alert.active_period
                                else None
                            ),
                            end_time=(
                                datetime.fromtimestamp(
                                    alert.active_period[0].end, timezone.utc
                                )
                                if alert.active_period
                                else None
                            ),
                        )
                    )
            await self._store_alerts(alerts)
            self._record_success()
            return alerts
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch alerts: {e}")
            return []

    def _serialize_dataclass(self, obj) -> dict[str, Any]:
        """Serialize a dataclass to a JSON-safe dict, converting datetime to ISO format"""
        result: dict[str, Any] = {}
        for key, value in obj.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, set):
                result[key] = list(value)
            else:
                result[key] = value
        return result

    async def _store_trip_updates(self, trip_updates: List[TripUpdate]):
        """Store trip updates in Valkey cache with stop-based indexing using batch writes."""
        if not trip_updates:
            return

        # Group updates by stop_id
        updates_by_stop: dict[str, List[dict[str, Any]]] = {}

        for tu in trip_updates:
            if tu.stop_id not in updates_by_stop:
                updates_by_stop[tu.stop_id] = []
            updates_by_stop[tu.stop_id].append(self._serialize_dataclass(tu))

        # Build batch of items to store
        # Key: trip_updates:stop:{stop_id} -> Value: List[TripUpdate]
        items_to_store: dict[str, Any] = {}
        for stop_id, updates in updates_by_stop.items():
            index_key = f"trip_updates:stop:{stop_id}"
            items_to_store[index_key] = updates

        await self.cache.mset_json(
            items_to_store,
            ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds,
        )

    async def _store_vehicle_positions(self, vehicle_positions: List[VehiclePosition]):
        """Store vehicle positions in Valkey cache with trip-based indexing using batch writes."""
        if not vehicle_positions:
            return

        items_to_store: dict[str, Any] = {}

        for vp in vehicle_positions:
            # Store by vehicle_id
            vehicle_key = f"vehicle_position:{vp.vehicle_id}"
            items_to_store[vehicle_key] = self._serialize_dataclass(vp)

            # Create trip-to-vehicle index if trip_id is available
            if vp.trip_id:
                trip_vehicle_key = f"vehicle_position:trip:{vp.trip_id}"
                items_to_store[trip_vehicle_key] = self._serialize_dataclass(vp)

        # Batch write all vehicle positions and indexes
        await self.cache.mset_json(
            items_to_store,
            ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds,
        )

    async def _store_alerts(self, alerts: List[ServiceAlert]):
        """Store service alerts in Valkey cache with route-based indexing using batch writes."""
        if not alerts:
            return

        # Track alerts by route for the secondary index
        route_to_alerts: dict[str, set[str]] = {}
        items_to_store: dict[str, Any] = {}

        for alert in alerts:
            key = f"service_alert:{alert.alert_id}"
            items_to_store[key] = self._serialize_dataclass(alert)

            # Build route-to-alerts index
            for route_id in alert.affected_routes:
                if route_id not in route_to_alerts:
                    route_to_alerts[route_id] = set()
                route_to_alerts[route_id].add(alert.alert_id)

        # Batch write all alerts
        await self.cache.mset_json(
            items_to_store,
            ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds,
        )

        # Batch write all route-based indexes
        index_items: dict[str, Any] = {}
        for route_id, alert_ids in route_to_alerts.items():
            index_key = f"service_alerts:route:{route_id}"
            index_items[index_key] = list(alert_ids)

        await self.cache.mset_json(
            index_items,
            ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds,
        )

    def _map_schedule_relationship(self, relationship) -> str:
        """Map GTFS-RT schedule relationship to string"""
        mapping = {0: "SCHEDULED", 1: "SKIPPED", 2: "NO_DATA", 3: "UNSCHEDULED"}
        return mapping.get(relationship, "SCHEDULED")

    def _map_cause(self, cause) -> str:
        """Map GTFS-RT cause to string"""
        mapping = {
            1: "UNKNOWN_CAUSE",
            2: "OTHER_CAUSE",
            3: "TECHNICAL_PROBLEM",
            4: "STRIKE",
            5: "DEMONSTRATION",
            6: "ACCIDENT",
            7: "HOLIDAY",
            8: "WEATHER",
            9: "MAINTENANCE",
            10: "CONSTRUCTION",
            11: "POLICE_ACTIVITY",
            12: "MEDICAL_EMERGENCY",
        }
        return mapping.get(cause, "UNKNOWN_CAUSE")

    def _map_effect(self, effect) -> str:
        """Map GTFS-RT effect to string"""
        mapping = {
            1: "NO_SERVICE",
            2: "REDUCED_SERVICE",
            3: "SIGNIFICANT_DELAYS",
            4: "DETOUR",
            5: "ADDITIONAL_SERVICE",
            6: "MODIFIED_SERVICE",
            7: "OTHER_EFFECT",
            8: "UNKNOWN_EFFECT",
            9: "STOP_MOVED",
        }
        return mapping.get(effect, "UNKNOWN_EFFECT")

    def _extract_text(self, translated_string) -> str:
        """Extract text from GTFS-RT TranslatedString message"""
        if not translated_string:
            return ""

        # Access the .translation repeated field of the TranslatedString message
        translations = translated_string.translation
        if not translations:
            return ""

        # Look for English or first available translation
        for translation in translations:
            if translation.language == "en" or not translation.language:
                return translation.text

        return translations[0].text if translations else ""

    async def get_trip_updates_for_stop(self, stop_id: str) -> List[TripUpdate]:
        """Get cached trip updates for a specific stop using the stop-based index"""
        try:
            # Get the list of trip updates directly
            key = f"trip_updates:stop:{stop_id}"
            data = await self.cache.get_json(key)

            if not data:
                return []

            return [TripUpdate(**item) for item in data]

        except Exception as e:
            logger.error(f"Failed to get trip updates for stop {stop_id}: {e}")
            return []

    async def get_vehicle_position(self, vehicle_id: str) -> Optional[VehiclePosition]:
        """Get cached vehicle position by vehicle ID"""
        try:
            key = f"vehicle_position:{vehicle_id}"
            data = await self.cache.get_json(key)

            if data:
                return VehiclePosition(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get vehicle position {vehicle_id}: {e}")
            return None

    async def get_vehicle_position_by_trip(
        self, trip_id: str
    ) -> Optional[VehiclePosition]:
        """Get cached vehicle position by trip ID"""
        try:
            key = f"vehicle_position:trip:{trip_id}"
            data = await self.cache.get_json(key)

            if data:
                return VehiclePosition(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get vehicle position for trip {trip_id}: {e}")
            return None

    async def get_vehicle_positions_by_trips(
        self, trip_ids: List[str]
    ) -> dict[str, VehiclePosition]:
        """Get cached vehicle positions for multiple trip IDs in a single batch call.

        Args:
            trip_ids: List of trip IDs to fetch vehicle positions for

        Returns:
            Dict mapping trip_id to VehiclePosition (only includes trips with positions)
        """
        try:
            if not trip_ids:
                return {}

            keys = [f"vehicle_position:trip:{trip_id}" for trip_id in trip_ids]
            data_map = await self.cache.mget_json(keys)

            result: dict[str, VehiclePosition] = {}
            for trip_id, key in zip(trip_ids, keys):
                data = data_map.get(key)
                if data:
                    result[trip_id] = VehiclePosition(**data)
            return result
        except Exception as e:
            logger.error(f"Failed to get vehicle positions for trips: {e}")
            return {}

    async def get_alerts_for_route(self, route_id: str) -> List[ServiceAlert]:
        """Get cached alerts for a specific route using the route-based index"""
        try:
            # Get the list of alert IDs for this route
            index_key = f"service_alerts:route:{route_id}"
            alert_ids = await self.cache.get_json(index_key)

            if not alert_ids:
                return []

            # Batch fetch all alerts
            alert_keys = [f"service_alert:{alert_id}" for alert_id in alert_ids]
            alerts_data = await self.cache.mget_json(alert_keys)

            alerts = []
            for data in alerts_data.values():
                if data:
                    # Convert lists back to sets for the ServiceAlert constructor
                    data["affected_routes"] = set(data["affected_routes"])
                    data["affected_stops"] = set(data["affected_stops"])
                    alerts.append(ServiceAlert(**data))

            return alerts

        except Exception as e:
            logger.error(f"Failed to get alerts for route {route_id}: {e}")
            return []
