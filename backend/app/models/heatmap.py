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


class HeatmapDataPoint(BaseModel):
    """A single data point representing cancellation data for a station."""

    station_id: str = Field(..., description="Global MVG station identifier.")
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
    by_transport: dict[str, TransportStats] = Field(
        default_factory=dict,
        description="Breakdown of cancellations by transport type.",
    )


class TimeRange(BaseModel):
    """Time range specification."""

    from_time: datetime = Field(
        ..., alias="from", description="Start of time range (UTC)."
    )
    to_time: datetime = Field(..., alias="to", description="End of time range (UTC).")

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
    most_affected_station: str | None = Field(
        None, description="Station with highest cancellation rate."
    )
    most_affected_line: str | None = Field(
        None, description="Line with highest cancellation rate."
    )


class HeatmapResponse(BaseModel):
    """Response model for the heatmap cancellations endpoint."""

    time_range: TimeRange = Field(..., description="Time range of the data.")
    data_points: list[HeatmapDataPoint] = Field(
        default_factory=list, description="List of station data points."
    )
    summary: HeatmapSummary = Field(..., description="Summary statistics.")


# Query parameter types
TimeRangePreset = Literal["1h", "6h", "24h", "7d", "30d"]
