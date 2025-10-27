from __future__ import annotations

from datetime import datetime
from typing import Iterable

from pydantic import BaseModel, Field

from app.services.mvg_client import Departure as DepartureDTO
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
    delay_minutes: int = Field(..., ge=0)
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
