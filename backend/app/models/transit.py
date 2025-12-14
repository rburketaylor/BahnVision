"""
Transit API Pydantic models for GTFS-based endpoints.

These models provide the API response schema for Germany-wide GTFS transit data.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TransitStop(BaseModel):
    """A transit stop from GTFS data."""

    id: str = Field(..., description="GTFS stop_id")
    name: str = Field(..., description="Stop name")
    latitude: float = Field(..., description="Stop latitude")
    longitude: float = Field(..., description="Stop longitude")
    zone_id: str | None = Field(None, description="Fare zone identifier")
    wheelchair_boarding: int = Field(
        0,
        description="Wheelchair accessibility: 0=unknown, 1=accessible, 2=not accessible",
    )


class TransitRoute(BaseModel):
    """A transit route from GTFS data."""

    id: str = Field(..., description="GTFS route_id")
    short_name: str = Field(..., description="Route short name (e.g., 'S1', 'U6')")
    long_name: str = Field(
        ..., description="Route long name (e.g., 'Freising - Munich Airport')"
    )
    route_type: int = Field(
        ...,
        description=(
            "GTFS route_type: 0=Tram, 1=Metro/Subway, 2=Rail, 3=Bus, "
            "4=Ferry, 5=Cable car, 6=Gondola, 7=Funicular"
        ),
    )
    color: str | None = Field(None, description="Route color as hex (e.g., 'FF0000')")
    text_color: str | None = Field(None, description="Route text color as hex")


class TransitDeparture(BaseModel):
    """A departure with combined schedule and real-time data."""

    trip_id: str = Field(..., description="GTFS trip_id")
    route_id: str = Field(..., description="GTFS route_id")
    route_short_name: str = Field(..., description="Route short name")
    route_long_name: str = Field("", description="Route long name")
    headsign: str = Field(..., description="Trip destination/headsign")
    stop_id: str = Field(..., description="GTFS stop_id")
    stop_name: str = Field(..., description="Stop name")
    scheduled_departure: datetime = Field(
        ..., description="Scheduled departure time (UTC)"
    )
    scheduled_arrival: datetime | None = Field(
        None, description="Scheduled arrival time (UTC)"
    )
    realtime_departure: datetime | None = Field(
        None, description="Real-time predicted departure time (UTC)"
    )
    realtime_arrival: datetime | None = Field(
        None, description="Real-time predicted arrival time (UTC)"
    )
    departure_delay_seconds: int | None = Field(
        None, description="Departure delay in seconds (positive=late)"
    )
    arrival_delay_seconds: int | None = Field(
        None, description="Arrival delay in seconds (positive=late)"
    )
    schedule_relationship: str = Field(
        "SCHEDULED",
        description="Schedule status: SCHEDULED, SKIPPED, NO_DATA, UNSCHEDULED",
    )
    vehicle_id: str | None = Field(None, description="Vehicle identifier if available")
    alerts: list[str] = Field(default_factory=list, description="Active service alerts")


class TransitDeparturesResponse(BaseModel):
    """Response for transit departures endpoint."""

    stop: TransitStop
    departures: list[TransitDeparture]
    realtime_available: bool = Field(
        True, description="Whether real-time data was available for this request"
    )


class TransitStopSearchResponse(BaseModel):
    """Response for transit stop search endpoint."""

    query: str = Field(..., description="Original search query")
    results: list[TransitStop] = Field(
        default_factory=list, description="Matching stops"
    )


class TransitRouteResponse(BaseModel):
    """Response for transit route info endpoint."""

    route: TransitRoute
    alerts: list[str] = Field(default_factory=list, description="Active service alerts")
