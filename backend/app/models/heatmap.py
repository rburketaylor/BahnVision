"""
Heatmap models for cancellation data visualization.

Provides Pydantic models for the heatmap API endpoint responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TransportStats(BaseModel):
    """Statistics for a single transport type."""

    total: int = Field(
        ..., ge=0, description="Total departures for this transport type."
    )
    cancelled: int = Field(..., ge=0, description="Number of cancelled departures.")
    delayed: int = Field(default=0, ge=0, description="Number of delayed departures.")


class HeatmapDataPoint(BaseModel):
    """A single data point representing delay/cancellation data for a station."""

    station_id: str = Field(..., description="GTFS stop_id identifier.")
    station_name: str = Field(..., description="Human-readable station name.")
    latitude: float = Field(..., ge=-90, le=90, description="Station latitude.")
    longitude: float = Field(..., ge=-180, le=180, description="Station longitude.")
    total_departures: int = Field(
        ..., ge=0, description="Total departures in the time range."
    )
    cancelled_count: int = Field(
        ..., ge=0, description="Number of cancelled departures."
    )
    cancellation_rate: float = Field(
        ..., ge=0, le=1, description="Cancellation rate (0.0 to 1.0)."
    )
    delayed_count: int = Field(
        default=0, ge=0, description="Number of delayed departures (>5 min)."
    )
    delay_rate: float = Field(
        default=0.0, ge=0, le=1, description="Delay rate (0.0 to 1.0)."
    )
    by_transport: dict[str, TransportStats] = Field(
        default_factory=dict,
        description="Breakdown by transport type.",
    )


class TimeRange(BaseModel):
    """Time range specification."""

    from_time: datetime = Field(
        ..., description="Start of time range (UTC).", alias="from"
    )
    to_time: datetime = Field(..., description="End of time range (UTC).", alias="to")

    model_config = {"populate_by_name": True}


class HeatmapSummary(BaseModel):
    """Summary statistics for the heatmap."""

    total_stations: int = Field(..., ge=0, description="Number of stations with data.")
    total_departures: int = Field(
        ..., ge=0, description="Total departures across all stations."
    )
    total_cancellations: int = Field(
        ..., ge=0, description="Total cancellations across all stations."
    )
    overall_cancellation_rate: float = Field(
        ..., ge=0, le=1, description="Overall cancellation rate."
    )
    total_delays: int = Field(
        default=0, ge=0, description="Total delayed departures across all stations."
    )
    overall_delay_rate: float = Field(
        default=0.0, ge=0, le=1, description="Overall delay rate."
    )
    most_affected_station: str | None = Field(
        None, description="Station with highest delay/cancellation impact."
    )
    most_affected_line: str | None = Field(
        None, description="Line with highest delay/cancellation rate."
    )


class HeatmapResponse(BaseModel):
    """Response model for the heatmap cancellations endpoint."""

    time_range: TimeRange = Field(..., description="Time range of the data.")
    data_points: list[HeatmapDataPoint] = Field(
        default_factory=list, description="List of station data points."
    )
    summary: HeatmapSummary = Field(..., description="Summary statistics.")
    last_updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when the snapshot was generated (live only).",
    )


# Query parameter types
TimeRangePreset = Literal["live", "1h", "6h", "24h", "7d", "30d"]
