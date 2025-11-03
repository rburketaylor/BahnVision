from __future__ import annotations

from datetime import datetime
from typing import Iterable

from pydantic import BaseModel, Field

from app.services.mvg_client import Departure as DepartureDTO
from app.services.mvg_client import (
    RouteLeg as RouteLegDTO,
    RoutePlan as RoutePlanDTO,
    RouteStop as RouteStopDTO,
)
from app.services.mvg_client import Station as StationDTO


class Station(BaseModel):
    id: str = Field(..., description="Global MVG station identifier.")
    name: str
    place: str
    latitude: float
    longitude: float

    @classmethod
    def from_dto(cls, dto: StationDTO) -> "Station":
        return cls(**dto.__dict__)


class Departure(BaseModel):
    planned_time: datetime | None = Field(
        None, description="Planned departure time in UTC."
    )
    realtime_time: datetime | None = Field(
        None, description="Real-time departure time in UTC."
    )
    delay_minutes: int = Field(..., ge=-1440)
    platform: str | None
    realtime: bool
    line: str
    destination: str
    transport_type: str
    icon: str | None = Field(None, description="Suggested icon identifier.")
    cancelled: bool
    messages: list[str]

    @classmethod
    def from_dto(cls, dto: DepartureDTO) -> "Departure":
        return cls(**dto.__dict__)


class DeparturesResponse(BaseModel):
    station: Station
    departures: list[Departure]

    @classmethod
    def from_dtos(
        cls, station: StationDTO, departures: Iterable[DepartureDTO]
    ) -> "DeparturesResponse":
        return cls(
            station=Station.from_dto(station),
            departures=[Departure.from_dto(dep) for dep in departures],
        )


class StationSearchResponse(BaseModel):
    query: str = Field(..., description="Original station query string.")
    results: list[Station] = Field(
        default_factory=list, description="Stations returned by the MVG search API."
    )

    @classmethod
    def from_dtos(
        cls, query: str, stations: Iterable[StationDTO]
    ) -> "StationSearchResponse":
        return cls(
            query=query,
            results=[Station.from_dto(dto) for dto in stations],
        )


class RouteStop(BaseModel):
    id: str | None = Field(None, description="Stop identifier if available.")
    name: str | None = None
    place: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    planned_time: datetime | None = None
    realtime_time: datetime | None = None
    platform: str | None = None
    transport_type: str | None = None
    line: str | None = None
    destination: str | None = None
    delay_minutes: int | None = Field(None, ge=0)
    messages: list[str] = Field(default_factory=list)

    @classmethod
    def from_dto(cls, dto: RouteStopDTO | None) -> RouteStop | None:
        if dto is None:
            return None
        return cls(**dto.__dict__)


class RouteLeg(BaseModel):
    origin: RouteStop | None
    destination: RouteStop | None
    transport_type: str | None
    line: str | None
    direction: str | None
    duration_minutes: int | None = Field(None, ge=0)
    distance_meters: int | None = Field(None, ge=0)
    intermediate_stops: list[RouteStop] = Field(default_factory=list)

    @classmethod
    def from_dto(cls, dto: RouteLegDTO) -> RouteLeg:
        return cls(
            origin=RouteStop.from_dto(dto.origin),
            destination=RouteStop.from_dto(dto.destination),
            transport_type=dto.transport_type,
            line=dto.line,
            direction=dto.direction,
            duration_minutes=dto.duration_minutes,
            distance_meters=dto.distance_meters,
            intermediate_stops=[
                stop for stop in (RouteStop.from_dto(item) for item in dto.intermediate_stops)
                if stop is not None
            ],
        )


class RoutePlan(BaseModel):
    duration_minutes: int | None = Field(None, ge=0)
    transfers: int | None = Field(None, ge=0)
    departure: RouteStop | None
    arrival: RouteStop | None
    legs: list[RouteLeg] = Field(default_factory=list)

    @classmethod
    def from_dto(cls, dto: RoutePlanDTO) -> RoutePlan:
        return cls(
            duration_minutes=dto.duration_minutes,
            transfers=dto.transfers,
            departure=RouteStop.from_dto(dto.departure),
            arrival=RouteStop.from_dto(dto.arrival),
            legs=[RouteLeg.from_dto(leg) for leg in dto.legs],
        )


class RouteResponse(BaseModel):
    origin: Station
    destination: Station
    plans: list[RoutePlan] = Field(default_factory=list)

    @classmethod
    def from_dtos(
        cls,
        origin: StationDTO,
        destination: StationDTO,
        plans: Iterable[RoutePlanDTO],
    ) -> RouteResponse:
        return cls(
            origin=Station.from_dto(origin),
            destination=Station.from_dto(destination),
            plans=[RoutePlan.from_dto(plan) for plan in plans],
        )
