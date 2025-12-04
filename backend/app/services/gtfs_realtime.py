"""
GTFS Real-Time Stream Processing Service

Handles fetching, parsing, and storing GTFS-RT data including:
- Trip updates (delays, cancellations)
- Vehicle positions
- Alerts
- Service alerts
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Set
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.services.cache import CacheService

# Import GTFS-RT bindings with fallback
try:
    import gtfs_realtime_bindings

    GTFS_RT_AVAILABLE = True
except ImportError:
    gtfs_realtime_bindings = None
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
        self.client = httpx.AsyncClient(
            timeout=self.settings.gtfs_rt_timeout_seconds,
            headers={"User-Agent": "BahnVision-GTFS-RT/1.0"},
        )
        self._circuit_breaker_state = {
            "failures": 0,
            "last_failure": None,
            "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows requests"""
        state = self._circuit_breaker_state

        if state["state"] == "OPEN":
            # Check if we should try half-open
            if (
                state["last_failure"]
                and (datetime.now(timezone.utc) - state["last_failure"]).seconds
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

    async def fetch_trip_updates(self) -> List[TripUpdate]:
        """Fetch and process trip updates from GTFS-RT feed"""
        if not GTFS_RT_AVAILABLE:
            logger.warning("GTFS-RT bindings not available, skipping trip updates")
            return []

        if not self._check_circuit_breaker():
            logger.warning("Circuit breaker OPEN, skipping trip updates fetch")
            return []

        try:
            response = await self.client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            feed = gtfs_realtime_bindings.FeedMessage()
            feed.ParseFromString(response.content)

            trip_updates = []
            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                tu = entity.trip_update
                if not tu.trip.trip_id:
                    continue

                for stop_time_update in tu.stop_time_update:
                    if not stop_time_update.stop_id:
                        continue

                    trip_update = TripUpdate(
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
                    trip_updates.append(trip_update)

            # Store in cache
            await self._store_trip_updates(trip_updates)
            self._record_success()

            logger.info(f"Processed {len(trip_updates)} trip updates")
            return trip_updates

        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch trip updates: {e}")
            return []

    async def fetch_vehicle_positions(self) -> List[VehiclePosition]:
        """Fetch and process vehicle positions from GTFS-RT feed"""
        if not GTFS_RT_AVAILABLE:
            logger.warning("GTFS-RT bindings not available, skipping vehicle positions")
            return []

        if not self._check_circuit_breaker():
            logger.warning("Circuit breaker OPEN, skipping vehicle positions fetch")
            return []

        try:
            response = await self.client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            feed = gtfs_realtime_bindings.FeedMessage()
            feed.ParseFromString(response.content)

            vehicle_positions = []
            for entity in feed.entity:
                if not entity.HasField("vehicle"):
                    continue

                v = entity.vehicle
                if not v.vehicle.id:
                    continue

                vehicle_position = VehiclePosition(
                    trip_id=v.trip.trip_id if v.HasField("trip") else "",
                    vehicle_id=v.vehicle.id,
                    route_id=v.trip.route_id if v.HasField("trip") else "",
                    latitude=v.position.latitude if v.HasField("position") else 0.0,
                    longitude=v.position.longitude if v.HasField("position") else 0.0,
                    bearing=v.position.bearing if v.HasField("position") else None,
                    speed=v.position.speed if v.HasField("position") else None,
                )
                vehicle_positions.append(vehicle_position)

            # Store in cache
            await self._store_vehicle_positions(vehicle_positions)
            self._record_success()

            logger.info(f"Processed {len(vehicle_positions)} vehicle positions")
            return vehicle_positions

        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch vehicle positions: {e}")
            return []

    async def fetch_alerts(self) -> List[ServiceAlert]:
        """Fetch and process service alerts from GTFS-RT feed"""
        if not GTFS_RT_AVAILABLE:
            logger.warning("GTFS-RT bindings not available, skipping alerts")
            return []

        if not self._check_circuit_breaker():
            logger.warning("Circuit breaker OPEN, skipping alerts fetch")
            return []

        try:
            response = await self.client.get(self.settings.gtfs_rt_feed_url)
            response.raise_for_status()

            feed = gtfs_realtime_bindings.FeedMessage()
            feed.ParseFromString(response.content)

            alerts = []
            for entity in feed.entity:
                if not entity.HasField("alert"):
                    continue

                alert = entity.alert
                alert_id = entity.id or f"alert_{len(alerts)}"

                # Extract affected routes and stops
                affected_routes = set()
                affected_stops = set()

                for informed_entity in alert.informed_entity:
                    if (
                        informed_entity.HasField("route_id")
                        and informed_entity.route_id
                    ):
                        affected_routes.add(informed_entity.route_id)
                    if informed_entity.HasField("stop_id") and informed_entity.stop_id:
                        affected_stops.add(informed_entity.stop_id)

                service_alert = ServiceAlert(
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
                        datetime.fromtimestamp(alert.active_period[0].end, timezone.utc)
                        if alert.active_period
                        else None
                    ),
                )
                alerts.append(service_alert)

            # Store in cache
            await self._store_alerts(alerts)
            self._record_success()

            logger.info(f"Processed {len(alerts)} service alerts")
            return alerts

        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to fetch alerts: {e}")
            return []

    async def _store_trip_updates(self, trip_updates: List[TripUpdate]):
        """Store trip updates in Valkey cache"""
        if not trip_updates:
            return

        # Store by trip_id for quick lookup
        for tu in trip_updates:
            key = f"trip_update:{tu.trip_id}:{tu.stop_id}"
            await self.cache.set_json(
                key, tu.__dict__, ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds
            )

    async def _store_vehicle_positions(self, vehicle_positions: List[VehiclePosition]):
        """Store vehicle positions in Valkey cache"""
        if not vehicle_positions:
            return

        # Store by vehicle_id for quick lookup
        for vp in vehicle_positions:
            key = f"vehicle_position:{vp.vehicle_id}"
            await self.cache.set_json(
                key, vp.__dict__, ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds
            )

    async def _store_alerts(self, alerts: List[ServiceAlert]):
        """Store service alerts in Valkey cache"""
        if not alerts:
            return

        # Store by alert_id
        for alert in alerts:
            key = f"service_alert:{alert.alert_id}"
            # Convert sets to lists for JSON serialization
            alert_dict = alert.__dict__.copy()
            alert_dict["affected_routes"] = list(alert.affected_routes)
            alert_dict["affected_stops"] = list(alert.affected_stops)
            await self.cache.set_json(
                key, alert_dict, ttl_seconds=self.settings.gtfs_rt_cache_ttl_seconds
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

    def _extract_text(self, translations) -> str:
        """Extract text from GTFS-RT translated string"""
        if not translations:
            return ""

        # Look for English or first available translation
        for translation in translations:
            if translation.language == "en" or not translation.language:
                return translation.text

        return translations[0].text if translations else ""

    async def get_trip_updates_for_stop(self, stop_id: str) -> List[TripUpdate]:
        """Get cached trip updates for a specific stop"""
        # Note: This is a simplified implementation
        # In a production system, you might want to maintain an index
        # of trip updates by stop_id for efficient lookups
        logger.warning(
            f"get_trip_updates_for_stop not fully implemented for stop {stop_id}"
        )
        return []

    async def get_vehicle_position(self, vehicle_id: str) -> Optional[VehiclePosition]:
        """Get cached vehicle position"""
        try:
            key = f"vehicle_position:{vehicle_id}"
            data = await self.cache.get_json(key)

            if data:
                return VehiclePosition(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get vehicle position {vehicle_id}: {e}")
            return None

    async def get_alerts_for_route(self, route_id: str) -> List[ServiceAlert]:
        """Get cached alerts for a specific route"""
        # Note: This is a simplified implementation
        # In a production system, you might want to maintain an index
        # of alerts by route_id for efficient lookups
        logger.warning(
            f"get_alerts_for_route not fully implemented for route {route_id}"
        )
        return []
