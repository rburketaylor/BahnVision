"""
Station statistics models for station details page.

Provides Pydantic models for station-specific statistics and trends API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TransportBreakdown(BaseModel):
    """Breakdown of statistics by transport type."""

    transport_type: str = Field(..., description="Transport type (e.g., UBAHN, SBAHN)")
    display_name: str = Field(..., description="Human-readable transport type name")
    total_departures: int = Field(..., ge=0, description="Total departures")
    cancelled_count: int = Field(..., ge=0, description="Number of cancellations")
    cancellation_rate: float = Field(
        ..., ge=0, le=1, description="Cancellation rate (0-1)"
    )
    delayed_count: int = Field(..., ge=0, description="Number of delays")
    delay_rate: float = Field(..., ge=0, le=1, description="Delay rate (0-1)")


class StationStats(BaseModel):
    """Current station statistics for a given time range."""

    station_id: str = Field(..., description="GTFS stop_id identifier")
    station_name: str = Field(..., description="Human-readable station name")
    time_range: str = Field(..., description="Time range preset (e.g., '24h')")

    # Core metrics
    total_departures: int = Field(..., ge=0, description="Total departures")
    cancelled_count: int = Field(..., ge=0, description="Number of cancellations")
    cancellation_rate: float = Field(..., ge=0, le=1, description="Cancellation rate")
    delayed_count: int = Field(..., ge=0, description="Number of delays (>5 min)")
    delay_rate: float = Field(..., ge=0, le=1, description="Delay rate")

    # Comparison to network average
    network_avg_cancellation_rate: float | None = Field(
        None, description="Network average cancellation rate for comparison"
    )
    network_avg_delay_rate: float | None = Field(
        None, description="Network average delay rate for comparison"
    )

    # Performance score (100 = perfect, 0 = worst)
    performance_score: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Overall performance score based on delays and cancellations",
    )

    # Breakdown by transport type
    by_transport: list[TransportBreakdown] = Field(
        default_factory=list, description="Statistics broken down by transport type"
    )

    # Time metadata
    data_from: datetime = Field(..., description="Start of data range (UTC)")
    data_to: datetime = Field(..., description="End of data range (UTC)")


class TrendDataPoint(BaseModel):
    """A single data point in a trend time series."""

    timestamp: datetime = Field(..., description="Bucket timestamp (UTC)")
    total_departures: int = Field(..., ge=0, description="Total departures in bucket")
    cancelled_count: int = Field(..., ge=0, description="Cancellations in bucket")
    cancellation_rate: float = Field(..., ge=0, le=1, description="Cancellation rate")
    delayed_count: int = Field(..., ge=0, description="Delays in bucket")
    delay_rate: float = Field(..., ge=0, le=1, description="Delay rate")


class StationTrends(BaseModel):
    """Historical trend data for a station."""

    station_id: str = Field(..., description="GTFS stop_id identifier")
    station_name: str = Field(..., description="Human-readable station name")
    time_range: str = Field(..., description="Time range preset")
    granularity: str = Field(..., description="Data granularity (hourly, daily)")

    # Trend data points
    data_points: list[TrendDataPoint] = Field(
        default_factory=list, description="Time series data points"
    )

    # Summary stats over the trend period
    avg_cancellation_rate: float = Field(
        ..., ge=0, le=1, description="Average cancellation rate over period"
    )
    avg_delay_rate: float = Field(
        ..., ge=0, le=1, description="Average delay rate over period"
    )
    peak_cancellation_rate: float = Field(
        ..., ge=0, le=1, description="Peak cancellation rate"
    )
    peak_delay_rate: float = Field(..., ge=0, le=1, description="Peak delay rate")

    # Time metadata
    data_from: datetime = Field(..., description="Start of trend data (UTC)")
    data_to: datetime = Field(..., description="End of trend data (UTC)")


# Query parameter types for station stats endpoints
TrendGranularity = Literal["hourly", "daily"]
