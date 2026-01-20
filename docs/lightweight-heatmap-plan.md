# Lightweight Heatmap Implementation Plan

## Executive Summary

Replace the current "fat payload" heatmap (500 stations × ~400 bytes = ~200KB) with a lightweight "skeleton + on-demand details" approach that can show **all ~15,000 impacted stations** in ~120KB gzipped, with detailed statistics loaded on-demand when clicking individual stations.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Solution Architecture](#2-solution-architecture)
3. [Backend Changes](#3-backend-changes)
4. [Frontend Changes](#4-frontend-changes)
5. [Caching Strategy](#5-caching-strategy)
6. [Testing Plan](#6-testing-plan)
7. [Migration Strategy](#7-migration-strategy)
8. [File Change Summary](#8-file-change-summary)
9. [Implementation Checklist](#9-implementation-checklist)

---

## 1. Problem Statement

### Current State

- **Endpoint**: `GET /api/v1/heatmap/cancellations`
- **Returns**: Full `HeatmapDataPoint` objects with all statistics
- **Payload per station**: ~250-400 bytes (JSON)
- **Limit**: 500-2000 stations (based on zoom level)
- **Coverage**: Only ~3% of German rail network visible

### Issues

1. **Berlin dominance**: Even with spatial stratification, high-traffic Berlin stations crowd out rural areas
2. **Large payloads**: Including `by_transport` breakdown bloats each station to ~400 bytes
3. **Wasted bandwidth**: Full stats sent even though users rarely click every station

### Target State

- **Show ALL impacted stations** (~15,000) for complete network coverage
- **Initial payload**: ~120KB gzipped (lightweight points only)
- **On-demand details**: Fetch full stats only when user clicks a station (~300 bytes per click)

---

## 2. Solution Architecture

### Two-Tier Data Loading

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INITIAL PAGE LOAD                           │
├─────────────────────────────────────────────────────────────────────┤
│  GET /api/v1/heatmap/overview?time_range=live                       │
│                                                                     │
│  Response (~120KB gzipped):                                         │
│  {                                                                  │
│    "time_range": { "from": "...", "to": "..." },                    │
│    "points": [                                                      │
│      { "id": "de:11000:900100001", "lat": 52.52, "lon": 13.41,     │
│        "i": 0.15, "n": "Berlin Hbf" },                              │
│      // ... 15,000 more stations                                   │
│    ],                                                               │
│    "summary": { ... }                                               │
│  }                                                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      USER CLICKS A STATION                          │
├─────────────────────────────────────────────────────────────────────┤
│  GET /api/v1/transit/stops/{stop_id}/stats?time_range=live          │
│                                                                     │
│  Response (~500 bytes):                                             │
│  {                                                                  │
│    "station_id": "de:11000:900100001",                              │
│    "station_name": "Berlin Hbf",                                    │
│    "total_departures": 1234,                                        │
│    "cancelled_count": 45,                                           │
│    "cancellation_rate": 0.036,                                      │
│    "delayed_count": 150,                                            │
│    "delay_rate": 0.121,                                             │
│    "by_transport": [ ... ],                                         │
│    // ... full detail                                               │
│  }                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Changes

### 3.1 New Models

**File**: `backend/app/models/heatmap.py`

Add the following new models **after** the existing `HeatmapDataPoint` class:

```python
class HeatmapPointLight(BaseModel):
    """Lightweight heatmap point for overview display.

    Contains only the minimum data needed for map rendering:
    - Station identifier (for on-demand detail fetching)
    - Coordinates (for positioning)
    - Intensity (for heat visualization)
    - Name (for hover tooltip)
    """

    id: str = Field(..., description="GTFS stop_id identifier.")
    lat: float = Field(..., description="Station latitude (4 decimal precision).")
    lon: float = Field(..., description="Station longitude (4 decimal precision).")
    i: float = Field(
        ...,
        ge=0,
        le=1,
        description="Intensity score 0-1 (normalized impact for heatmap weight)."
    )
    n: str = Field(..., description="Station name (for hover tooltip).")


class HeatmapOverviewResponse(BaseModel):
    """Lightweight heatmap response for initial page load.

    Optimized for minimum payload size while showing all impacted stations.
    Use /transit/stops/{stop_id}/stats for full station details.
    """

    time_range: TimeRange = Field(..., description="Time range of the data.")
    points: list[HeatmapPointLight] = Field(
        default_factory=list,
        description="Lightweight station points for map rendering."
    )
    summary: HeatmapSummary = Field(..., description="Network-wide summary statistics.")
    last_updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when the snapshot was generated (live only)."
    )
    total_impacted_stations: int = Field(
        ...,
        description="Total count of stations with non-zero impact."
    )
```

### 3.2 New Service Method

**File**: `backend/app/services/heatmap_service.py`

Add a new method to `HeatmapService` class:

```python
async def get_heatmap_overview(
    self,
    time_range: TimeRangePreset | None = None,
    transport_modes: str | None = None,
    bucket_width_minutes: int = DEFAULT_BUCKET_WIDTH_MINUTES,
) -> HeatmapOverviewResponse:
    """Generate lightweight heatmap overview showing ALL impacted stations.

    Unlike get_cancellation_heatmap(), this method:
    - Returns ALL stations with non-zero impact (no max_points limit)
    - Uses minimal fields (id, lat, lon, intensity, name)
    - Skips the by_transport breakdown (fetched on-demand via /stats endpoint)

    Args:
        time_range: Time range preset (live, 1h, 6h, 24h, 7d, 30d)
        transport_modes: Comma-separated transport types to include
        bucket_width_minutes: Time bucket width for aggregation

    Returns:
        HeatmapOverviewResponse with lightweight points for all impacted stations
    """
    from_time, to_time = parse_time_range(time_range)
    transport_types = parse_transport_modes(transport_modes)
    route_type_filter = self._resolve_route_type_filter(transport_types)

    logger.info(
        "Generating heatmap overview for time range %s to %s, transport modes: %s",
        from_time.isoformat(),
        to_time.isoformat(),
        transport_modes or "all",
    )

    points = await self._get_all_impacted_stations_light(
        route_type_filter=route_type_filter,
        from_time=from_time,
        to_time=to_time,
        bucket_width_minutes=bucket_width_minutes,
    )

    summary = await self._calculate_network_summary_from_db(
        from_time=from_time,
        to_time=to_time,
        bucket_width_minutes=bucket_width_minutes,
        route_type_filter=route_type_filter,
        most_affected_station=_pick_most_affected_station_light(points),
    )

    return HeatmapOverviewResponse(
        time_range=TimeRange.model_validate({"from": from_time, "to": to_time}),
        points=points,
        summary=summary,
        total_impacted_stations=len(points),
    )


async def _get_all_impacted_stations_light(
    self,
    route_type_filter: list[int] | None,
    from_time: datetime,
    to_time: datetime,
    *,
    bucket_width_minutes: int,
) -> list[HeatmapPointLight]:
    """Query ALL impacted stations with minimal fields.

    Returns only stations where:
    - cancelled_count > 0 OR delayed_count > 0
    - Has valid coordinates

    No limit on number of stations returned.
    """
    if not self._session:
        raise RuntimeError("Heatmap overview requires an active database session")

    from app.models.gtfs import GTFSStop
    from app.models.heatmap import HeatmapPointLight

    total_departures_expr = func.coalesce(
        func.sum(RealtimeStationStats.trip_count), 0
    )
    cancelled_count_expr = func.coalesce(
        func.sum(RealtimeStationStats.cancelled_count), 0
    )
    delayed_count_expr = func.coalesce(
        func.sum(RealtimeStationStats.delayed_count), 0
    )

    # Intensity = (cancelled + delayed) / total, saturated at 25%
    # This gives a 0-1 value for heatmap weight
    intensity_expr = func.least(
        (cancelled_count_expr + delayed_count_expr)
        / func.nullif(total_departures_expr, 0)
        * 4.0,
        1.0
    ).label("intensity")

    stmt = (
        select(
            RealtimeStationStats.stop_id,
            GTFSStop.stop_name,
            func.round(GTFSStop.stop_lat.cast(Numeric), 4).label("lat"),
            func.round(GTFSStop.stop_lon.cast(Numeric), 4).label("lon"),
            intensity_expr,
            cancelled_count_expr.label("cancelled"),
            delayed_count_expr.label("delayed"),
        )
        .join(GTFSStop, RealtimeStationStats.stop_id == GTFSStop.stop_id)
        .where(RealtimeStationStats.bucket_start >= from_time)
        .where(RealtimeStationStats.bucket_start < to_time)
        .where(RealtimeStationStats.bucket_width_minutes == bucket_width_minutes)
        .where(GTFSStop.stop_lat.isnot(None))
        .where(GTFSStop.stop_lon.isnot(None))
    )

    if route_type_filter:
        stmt = stmt.where(RealtimeStationStats.route_type.in_(route_type_filter))

    stmt = stmt.group_by(
        RealtimeStationStats.stop_id,
        GTFSStop.stop_name,
        GTFSStop.stop_lat,
        GTFSStop.stop_lon,
    ).having(
        # Only include stations with at least 1 cancellation OR delay
        (cancelled_count_expr > 0) | (delayed_count_expr > 0)
    )

    result = await self._session.execute(stmt)
    rows = result.all()

    points = [
        HeatmapPointLight(
            id=row.stop_id,
            n=row.stop_name or row.stop_id,
            lat=float(row.lat),
            lon=float(row.lon),
            i=float(row.intensity) if row.intensity else 0.0,
        )
        for row in rows
    ]

    logger.info("Retrieved %d impacted stations for heatmap overview", len(points))
    return points


def _pick_most_affected_station_light(points: list[HeatmapPointLight]) -> str | None:
    """Pick the most affected station from lightweight points."""
    if not points:
        return None
    most_affected = max(points, key=lambda p: p.i)
    return most_affected.n
```

### 3.3 New Endpoint

**File**: `backend/app/api/v1/endpoints/heatmap.py`

Add a new endpoint **after** the existing `get_cancellation_heatmap` function:

```python
@router.get(
    "/overview",
    response_model=HeatmapOverviewResponse,
    summary="Get lightweight heatmap overview",
    description="""
    Get a lightweight heatmap overview showing ALL impacted stations.

    This endpoint is optimized for initial page load:
    - Returns only minimal data (id, coordinates, intensity, name)
    - No limit on number of stations (shows entire network)
    - Payload is ~10x smaller than /cancellations endpoint

    Use /api/v1/transit/stops/{stop_id}/stats to fetch full details
    when a user clicks on a station.
    """,
    responses={
        200: {
            "description": "Lightweight heatmap overview data",
            "content": {
                "application/json": {
                    "example": {
                        "time_range": {
                            "from": "2024-01-14T00:00:00Z",
                            "to": "2024-01-14T23:59:59Z"
                        },
                        "points": [
                            {"id": "de:11000:900100001", "lat": 52.5219, "lon": 13.4115, "i": 0.15, "n": "Berlin Hbf"}
                        ],
                        "summary": {"total_stations": 15000, "...": "..."},
                        "total_impacted_stations": 15000
                    }
                }
            }
        }
    }
)
@limiter.limit("30/minute")
async def get_heatmap_overview(
    request: Request,
    response: Response,
    time_range: Annotated[
        TimeRangePreset | None,
        Query(
            description="Time range preset. Use 'live' for real-time data.",
        ),
    ] = None,
    transport_modes: Annotated[
        str | None,
        Query(
            description="Comma-separated transport types to include (e.g., 'UBAHN,SBAHN').",
        ),
    ] = None,
    bucket_width: Annotated[
        int,
        Query(
            ge=15,
            le=1440,
            description="Bucket width in minutes for time aggregation (default: 60).",
        ),
    ] = 60,
    db: AsyncSession = Depends(get_session),
    gtfs_schedule: GTFSScheduleService = Depends(get_gtfs_schedule),
    cache: CacheService = Depends(get_cache_service),
) -> HeatmapOverviewResponse:
    """Get lightweight heatmap overview showing all impacted stations."""

    # Build cache key
    cache_key = f"heatmap:overview:{time_range or 'default'}:{transport_modes or 'all'}:{bucket_width}"

    # Check cache first
    try:
        cached = await cache.get_json(cache_key)
        if cached:
            response.headers["X-Cache-Status"] = "hit"
            return HeatmapOverviewResponse.model_validate(cached)

        stale = await cache.get_stale_json(cache_key)
        if stale:
            response.headers["X-Cache-Status"] = "stale"
            return HeatmapOverviewResponse.model_validate(stale)
    except Exception as e:
        logger.warning("Cache read failed for heatmap overview: %s", e)

    response.headers["X-Cache-Status"] = "miss"

    # Generate fresh data
    service = HeatmapService(gtfs_schedule, cache, session=db)
    result = await service.get_heatmap_overview(
        time_range=time_range,
        transport_modes=transport_modes,
        bucket_width_minutes=bucket_width,
    )

    # Cache the result
    settings = get_settings()
    try:
        await cache.set_json(
            cache_key,
            result.model_dump(mode="json"),
            ttl_seconds=settings.heatmap_cache_ttl_seconds,
            stale_ttl_seconds=settings.heatmap_cache_stale_ttl_seconds,
        )
    except Exception as e:
        logger.warning("Cache write failed for heatmap overview: %s", e)

    return result
```

### 3.4 Add Imports

**File**: `backend/app/api/v1/endpoints/heatmap.py`

Add to imports:

```python
from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapResponse,
    HeatmapSummary,
    HeatmapOverviewResponse,  # NEW
    HeatmapPointLight,         # NEW
    TimeRange,
    TimeRangePreset,
)
```

**File**: `backend/app/services/heatmap_service.py`

Add to imports:

```python
from sqlalchemy import func, select, Numeric  # Add Numeric

from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapOverviewResponse,  # NEW
    HeatmapPointLight,         # NEW
    HeatmapResponse,
    HeatmapSummary,
    TimeRange,
    TimeRangePreset,
    TransportStats,
)
```

---

## 4. Frontend Changes

### 4.1 New Types

**File**: `frontend/src/types/heatmap.ts`

Add the following new types:

```typescript
/** Lightweight heatmap point for overview display */
export interface HeatmapPointLight {
  /** GTFS stop_id identifier */
  id: string;
  /** Station latitude (4 decimal precision) */
  lat: number;
  /** Station longitude (4 decimal precision) */
  lon: number;
  /** Intensity score 0-1 (normalized impact for heatmap weight) */
  i: number;
  /** Station name (for hover tooltip) */
  n: string;
}

/** Lightweight heatmap overview response */
export interface HeatmapOverviewResponse {
  time_range: HeatmapTimeRange;
  points: HeatmapPointLight[];
  summary: HeatmapSummary;
  last_updated_at?: string;
  total_impacted_stations: number;
}

/** Parameters for heatmap overview API requests */
export interface HeatmapOverviewParams {
  time_range?: TimeRangePreset;
  transport_modes?: TransportType[];
  bucket_width?: number;
}
```

### 4.2 New API Method

**File**: `frontend/src/services/endpoints/transitApi.ts`

Add to `TransitApiClient` class:

```typescript
/**
 * Get lightweight heatmap overview (all impacted stations)
 */
async getHeatmapOverview(
  params: HeatmapOverviewParams = {}
): Promise<ApiResponse<HeatmapOverviewResponse>> {
  const apiParams: Record<string, unknown> = {
    time_range: params.time_range,
    bucket_width: params.bucket_width,
  }

  if (params.transport_modes && params.transport_modes.length > 0) {
    apiParams.transport_modes = params.transport_modes.join(',')
  }

  const queryString = buildQueryString(apiParams)
  return httpClient.request<HeatmapOverviewResponse>(
    `/api/v1/heatmap/overview${queryString}`,
    {
      timeout: 20000, // Slightly longer timeout for larger payload
    }
  )
}
```

Add imports at top:

```typescript
import type {
  HeatmapOverviewParams,
  HeatmapOverviewResponse,
} from "../../types/heatmap";
```

### 4.3 New Hook

**File**: `frontend/src/hooks/useHeatmapOverview.ts` (NEW FILE)

```typescript
/**
 * useHeatmapOverview Hook
 * Fetches lightweight heatmap overview with all impacted stations
 */

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/api";
import type { HeatmapOverviewParams } from "../types/heatmap";

interface UseHeatmapOverviewOptions {
  enabled?: boolean;
  /** Enable auto-refresh (live uses a faster cadence) */
  autoRefresh?: boolean;
}

export function useHeatmapOverview(
  params: HeatmapOverviewParams = {},
  options: UseHeatmapOverviewOptions = {},
) {
  const { enabled = true, autoRefresh = true } = options;
  const isLive = params.time_range === "live";
  const refetchIntervalMs = isLive ? 60 * 1000 : 5 * 60 * 1000;
  const staleTimeMs = isLive ? 30 * 1000 : 5 * 60 * 1000;

  return useQuery({
    queryKey: ["heatmap", "overview", params],
    queryFn: async () => {
      const response = await apiClient.getHeatmapOverview(params);

      // Validate response structure
      if (!response.data?.points || !Array.isArray(response.data.points)) {
        throw new Error("Invalid heatmap overview response structure");
      }

      // Validate each point has required fields
      const validData = response.data.points.every(
        (point) =>
          typeof point.lat === "number" &&
          typeof point.lon === "number" &&
          typeof point.i === "number" &&
          !isNaN(point.lat) &&
          !isNaN(point.lon) &&
          !isNaN(point.i),
      );

      if (!validData) {
        throw new Error("Invalid points in heatmap overview response");
      }

      return response.data;
    },
    enabled,
    placeholderData: keepPreviousData,
    staleTime: staleTimeMs,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    ...(autoRefresh
      ? { refetchInterval: refetchIntervalMs }
      : { refetchInterval: false }),
  });
}
```

### 4.4 Update MapLibreHeatmap Component

**File**: `frontend/src/components/heatmap/MapLibreHeatmap.tsx`

**Changes needed:**

1. **Add new prop** to accept lightweight points:

```typescript
interface MapLibreHeatmapProps {
  // Existing props (keep for backwards compatibility during migration)
  dataPoints?: HeatmapDataPoint[];

  // NEW: Lightweight points for overview mode
  overviewPoints?: HeatmapPointLight[];

  enabledMetrics: HeatmapEnabledMetrics;
  isLoading?: boolean;
  onStationSelect?: (stationId: string | null) => void;
  onZoomChange?: (zoom: number) => void;
  overlay?: ReactNode;

  // NEW: Callback when station detail is needed
  onStationDetailRequested?: (stationId: string) => void;
}
```

2. **Add new toGeoJSON function** for lightweight points:

```typescript
/**
 * Convert lightweight HeatmapPointLight array to GeoJSON
 */
function overviewToGeoJSON(
  points: HeatmapPointLight[],
  enabledMetrics: HeatmapEnabledMetrics,
): GeoJSONResult {
  if (!points || points.length === 0) {
    return {
      active: { type: "FeatureCollection", features: [] },
      coverage: { type: "FeatureCollection", features: [] },
    };
  }

  const features: GeoJSON.Feature[] = points
    .filter(
      (point) =>
        typeof point.lat === "number" &&
        typeof point.lon === "number" &&
        !isNaN(point.lat) &&
        !isNaN(point.lon),
    )
    .map((point) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: [point.lon, point.lat],
      },
      properties: {
        station_id: point.id,
        station_name: point.n,
        intensity: point.i,
        // These are approximations for backwards compat with existing styling
        rate: point.i * 0.25, // Intensity is 4x rate, so reverse
        is_coverage: point.i === 0,
      },
    }));

  // Separate into active vs coverage based on intensity
  const activeFeatures = features.filter(
    (f) => (f.properties?.intensity || 0) > 0,
  );
  const coverageFeatures = features.filter(
    (f) => (f.properties?.intensity || 0) === 0,
  );

  return {
    active: { type: "FeatureCollection", features: activeFeatures },
    coverage: { type: "FeatureCollection", features: coverageFeatures },
  };
}
```

3. **Update component logic** to handle both modes:

```typescript
// In the component body, add logic to handle overview mode:
const geoJsonData = useMemo(() => {
  // Prefer overview points if provided (lightweight mode)
  if (overviewPoints && overviewPoints.length > 0) {
    return overviewToGeoJSON(overviewPoints, enabledMetrics);
  }
  // Fall back to full dataPoints (backwards compat)
  if (dataPoints && dataPoints.length > 0) {
    return toGeoJSON(dataPoints, enabledMetrics);
  }
  return {
    active: { type: "FeatureCollection", features: [] },
    coverage: { type: "FeatureCollection", features: [] },
  };
}, [overviewPoints, dataPoints, enabledMetrics]);
```

4. **Update popup click handler** to request details:

```typescript
// In the click handler for 'unclustered-point':
map.on("click", "unclustered-point", (e: maplibregl.MapMouseEvent) => {
  const features = map.queryRenderedFeatures(e.point, {
    layers: ["unclustered-point"],
  });
  if (!features.length) return;

  const props = features[0].properties;
  if (!props) return;

  const stationId = props.station_id;

  // Trigger on-demand detail fetch
  onStationDetailRequested?.(stationId);

  // Show loading popup while details load
  const loadingHtml = `
    <div class="heatmap-popup-content">
      <h3 class="text-base font-semibold">${sanitize(
        props.station_name || "Station",
      )}</h3>
      <p class="text-sm text-muted-foreground">Loading details...</p>
    </div>
  `;

  popupRef.current
    ?.setLngLat(features[0].geometry.coordinates as [number, number])
    .setHTML(loadingHtml)
    .addTo(map);
});
```

### 4.5 Update Heatmap Page

**File**: `frontend/src/pages/HeatmapPage.tsx` (or equivalent page component)

```typescript
import { useHeatmapOverview } from '../hooks/useHeatmapOverview'
import { useStationStats } from '../hooks/useStationStats'

function HeatmapPage() {
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null)
  const [timeRange, setTimeRange] = useState<TimeRangePreset>('live')

  // Fetch lightweight overview (all stations)
  const { data: overviewData, isLoading: isOverviewLoading } = useHeatmapOverview({
    time_range: timeRange,
  })

  // Fetch details on-demand when station is selected
  const { data: stationDetails, isLoading: isDetailsLoading } = useStationStats(
    selectedStationId,
    timeRange,
    { enabled: !!selectedStationId }
  )

  const handleStationDetailRequested = useCallback((stationId: string) => {
    setSelectedStationId(stationId)
  }, [])

  return (
    <MapLibreHeatmap
      overviewPoints={overviewData?.points}
      enabledMetrics={enabledMetrics}
      isLoading={isOverviewLoading}
      onStationDetailRequested={handleStationDetailRequested}
      // ... other props
    />
  )
}
```

### 4.6 Update Station Popup

Create a new component or update existing popup logic to show details when loaded:

**File**: `frontend/src/components/heatmap/StationPopup.tsx` (NEW FILE)

```typescript
import type { StationStats } from '../../types/gtfs'
import type { HeatmapPointLight } from '../../types/heatmap'

interface StationPopupProps {
  station: HeatmapPointLight
  details?: StationStats
  isLoading: boolean
}

export function StationPopup({ station, details, isLoading }: StationPopupProps) {
  if (isLoading) {
    return (
      <div className="p-3">
        <h3 className="font-semibold text-base">{station.n}</h3>
        <div className="mt-2 flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
          <span className="text-sm text-muted-foreground">Loading...</span>
        </div>
      </div>
    )
  }

  if (!details) {
    return (
      <div className="p-3">
        <h3 className="font-semibold text-base">{station.n}</h3>
        <p className="text-sm text-muted-foreground mt-1">No data available</p>
      </div>
    )
  }

  return (
    <div className="p-3 min-w-[200px]">
      <h3 className="font-semibold text-base">{details.station_name}</h3>

      <div className="mt-3 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Departures</span>
          <span className="font-medium">{details.total_departures.toLocaleString()}</span>
        </div>

        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Cancellations</span>
          <span className="font-medium text-red-500">
            {details.cancelled_count} ({(details.cancellation_rate * 100).toFixed(1)}%)
          </span>
        </div>

        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Delays (&gt;5 min)</span>
          <span className="font-medium text-orange-500">
            {details.delayed_count} ({(details.delay_rate * 100).toFixed(1)}%)
          </span>
        </div>
      </div>

      {details.by_transport.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-xs text-muted-foreground mb-2">By Transport Type</p>
          {details.by_transport.map(t => (
            <div key={t.transport_type} className="flex justify-between text-xs">
              <span>{t.display_name}</span>
              <span>
                {((t.cancellation_rate + t.delay_rate) * 100).toFixed(1)}% issues
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

---

## 5. Caching Strategy

### 5.1 Backend Cache Keys

| Cache Key                      | TTL  | Stale TTL | Description                        |
| ------------------------------ | ---- | --------- | ---------------------------------- |
| `heatmap:overview:live:all:60` | 60s  | 300s      | Live overview, all transport types |
| `heatmap:overview:24h:all:60`  | 300s | 600s      | 24h overview                       |
| `heatmap:overview:7d:all:60`   | 600s | 1200s     | 7d overview                        |

### 5.2 Update Cache Warmer

**File**: `backend/app/jobs/heatmap_cache_warmup.py`

Add overview variants to the warmup job:

```python
def _build_targets(self) -> list[HeatmapWarmupTarget]:
    targets: list[HeatmapWarmupTarget] = []

    # Original targets (existing logic)
    for time_range in self._settings.heatmap_cache_warmup_time_ranges:
        # ... existing code ...

    # NEW: Add overview targets
    for time_range in self._settings.heatmap_cache_warmup_time_ranges:
        targets.append(
            HeatmapWarmupTarget(
                time_range=cast(TimeRangePreset, time_range),
                transport_modes=None,
                bucket_width_minutes=self._settings.heatmap_cache_warmup_bucket_width_minutes,
                max_points=0,  # 0 = overview mode
                is_overview=True,  # New flag
            )
        )

    return targets
```

### 5.3 Frontend Cache

The existing React Query caching in `useHeatmapOverview` handles this with:

- `staleTime`: 30s for live, 5min for historical
- `gcTime`: 10min (garbage collection time)

---

## 6. Testing Plan

### 6.1 Backend Unit Tests

**File**: `backend/tests/services/test_heatmap_service_overview.py` (NEW FILE)

```python
"""Tests for HeatmapService.get_heatmap_overview method."""

import pytest
from datetime import datetime, timezone

from app.models.heatmap import HeatmapOverviewResponse, HeatmapPointLight


class TestGetHeatmapOverview:
    """Tests for the lightweight heatmap overview endpoint."""

    async def test_returns_all_impacted_stations(self, heatmap_service, db_with_stations):
        """Should return all stations with non-zero impact, no limit."""
        result = await heatmap_service.get_heatmap_overview(time_range="24h")

        assert isinstance(result, HeatmapOverviewResponse)
        # Should include all stations with cancellations or delays
        assert result.total_impacted_stations > 0
        assert len(result.points) == result.total_impacted_stations

    async def test_lightweight_point_structure(self, heatmap_service, db_with_stations):
        """Each point should only contain minimal fields."""
        result = await heatmap_service.get_heatmap_overview(time_range="24h")

        for point in result.points:
            assert isinstance(point, HeatmapPointLight)
            assert hasattr(point, 'id')
            assert hasattr(point, 'lat')
            assert hasattr(point, 'lon')
            assert hasattr(point, 'i')
            assert hasattr(point, 'n')
            # Should NOT have detailed fields
            assert not hasattr(point, 'total_departures')
            assert not hasattr(point, 'by_transport')

    async def test_intensity_range(self, heatmap_service, db_with_stations):
        """Intensity should be between 0 and 1."""
        result = await heatmap_service.get_heatmap_overview(time_range="24h")

        for point in result.points:
            assert 0 <= point.i <= 1, f"Intensity {point.i} out of range for {point.id}"

    async def test_coordinate_precision(self, heatmap_service, db_with_stations):
        """Coordinates should be rounded to 4 decimal places."""
        result = await heatmap_service.get_heatmap_overview(time_range="24h")

        for point in result.points:
            lat_decimals = len(str(point.lat).split('.')[-1]) if '.' in str(point.lat) else 0
            lon_decimals = len(str(point.lon).split('.')[-1]) if '.' in str(point.lon) else 0
            assert lat_decimals <= 4, f"Lat has {lat_decimals} decimals"
            assert lon_decimals <= 4, f"Lon has {lon_decimals} decimals"

    async def test_excludes_zero_impact_stations(self, heatmap_service, db_with_healthy_stations):
        """Should not include stations with 0 cancellations AND 0 delays."""
        result = await heatmap_service.get_heatmap_overview(time_range="24h")

        for point in result.points:
            assert point.i > 0, f"Zero-impact station {point.id} should not be included"

    async def test_transport_mode_filter(self, heatmap_service, db_with_mixed_transport):
        """Should filter by transport mode when provided."""
        all_result = await heatmap_service.get_heatmap_overview(time_range="24h")
        sbahn_result = await heatmap_service.get_heatmap_overview(
            time_range="24h",
            transport_modes="SBAHN"
        )

        assert len(sbahn_result.points) <= len(all_result.points)
```

### 6.2 Backend Integration Tests

**File**: `backend/tests/api/test_heatmap_overview_endpoint.py` (NEW FILE)

```python
"""Integration tests for GET /api/v1/heatmap/overview endpoint."""

import pytest
from httpx import AsyncClient


class TestHeatmapOverviewEndpoint:

    async def test_returns_200_with_valid_response(self, client: AsyncClient):
        """Should return 200 with valid overview response."""
        response = await client.get("/api/v1/heatmap/overview?time_range=24h")

        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "summary" in data
        assert "time_range" in data
        assert "total_impacted_stations" in data

    async def test_gzip_compression(self, client: AsyncClient):
        """Response should be significantly smaller when gzipped."""
        response = await client.get(
            "/api/v1/heatmap/overview?time_range=24h",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        # Check content-encoding header or content-length

    async def test_cache_headers(self, client: AsyncClient):
        """Should include X-Cache-Status header."""
        response = await client.get("/api/v1/heatmap/overview?time_range=24h")

        assert response.status_code == 200
        assert "X-Cache-Status" in response.headers
```

### 6.3 Frontend Tests

**File**: `frontend/src/hooks/useHeatmapOverview.test.ts` (NEW FILE)

```typescript
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useHeatmapOverview } from './useHeatmapOverview'
import { apiClient } from '../services/api'

// Mock the API client
vi.mock('../services/api', () => ({
  apiClient: {
    getHeatmapOverview: vi.fn(),
  },
}))

describe('useHeatmapOverview', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    vi.clearAllMocks()
  })

  it('fetches lightweight overview data', async () => {
    const mockData = {
      points: [
        { id: 'stop-1', lat: 52.52, lon: 13.41, i: 0.15, n: 'Berlin Hbf' },
      ],
      summary: { total_stations: 1 },
      total_impacted_stations: 1,
    }

    vi.mocked(apiClient.getHeatmapOverview).mockResolvedValue({ data: mockData })

    const { result } = renderHook(
      () => useHeatmapOverview({ time_range: 'live' }),
      { wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )}
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.points).toHaveLength(1)
    expect(result.current.data?.points[0].id).toBe('stop-1')
  })

  it('validates response structure', async () => {
    const invalidData = { points: null } // Invalid
    vi.mocked(apiClient.getHeatmapOverview).mockResolvedValue({ data: invalidData })

    const { result } = renderHook(
      () => useHeatmapOverview({ time_range: 'live' }),
      { wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )}
    )

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toContain('Invalid')
  })
})
```

---

## 7. Migration Strategy

### Phase 1: Backend Only (Non-Breaking)

1. Deploy new `/heatmap/overview` endpoint
2. Add cache warming for overview variants
3. Monitor performance and payload sizes
4. **No frontend changes yet**

### Phase 2: Frontend Migration

1. Add `useHeatmapOverview` hook
2. Update heatmap page to use overview + on-demand pattern
3. Keep old `useHeatmap` hook for backwards compatibility
4. A/B test if needed

### Phase 3: Cleanup (After Validation)

1. Remove `max_points` limit from UI (users see all stations)
2. Deprecate old `/heatmap/cancellations` heavy usage
3. Update cache warmer to prioritize overview
4. Update documentation

### Rollback Plan

- Old endpoint (`/heatmap/cancellations`) remains fully functional
- Frontend can switch back to `useHeatmap` hook if issues
- Feature flag can control which mode is used

---

## 8. File Change Summary

### New Files

| File                                                      | Purpose                         |
| --------------------------------------------------------- | ------------------------------- |
| `backend/tests/services/test_heatmap_service_overview.py` | Unit tests for overview service |
| `backend/tests/api/test_heatmap_overview_endpoint.py`     | Integration tests for endpoint  |
| `frontend/src/hooks/useHeatmapOverview.ts`                | React Query hook for overview   |
| `frontend/src/hooks/useHeatmapOverview.test.ts`           | Hook tests                      |
| `frontend/src/components/heatmap/StationPopup.tsx`        | Popup with loading state        |

### Modified Files

| File                                                  | Changes                                                            |
| ----------------------------------------------------- | ------------------------------------------------------------------ |
| `backend/app/models/heatmap.py`                       | Add `HeatmapPointLight`, `HeatmapOverviewResponse`                 |
| `backend/app/services/heatmap_service.py`             | Add `get_heatmap_overview()`, `_get_all_impacted_stations_light()` |
| `backend/app/api/v1/endpoints/heatmap.py`             | Add `/overview` endpoint                                           |
| `backend/app/jobs/heatmap_cache_warmup.py`            | Warm overview variants                                             |
| `frontend/src/types/heatmap.ts`                       | Add `HeatmapPointLight`, `HeatmapOverviewResponse`                 |
| `frontend/src/services/endpoints/transitApi.ts`       | Add `getHeatmapOverview()`                                         |
| `frontend/src/components/heatmap/MapLibreHeatmap.tsx` | Support `overviewPoints` prop                                      |
| `frontend/src/pages/HeatmapPage.tsx`                  | Use overview + on-demand pattern                                   |

---

## 9. Implementation Checklist

### Backend

- [ ] Add `HeatmapPointLight` model to `models/heatmap.py`
- [ ] Add `HeatmapOverviewResponse` model to `models/heatmap.py`
- [ ] Add `get_heatmap_overview()` method to `HeatmapService`
- [ ] Add `_get_all_impacted_stations_light()` method to `HeatmapService`
- [ ] Add `_pick_most_affected_station_light()` helper function
- [ ] Add `/overview` endpoint to `api/v1/endpoints/heatmap.py`
- [ ] Add cache key logic for overview endpoint
- [ ] Update cache warmer to include overview variants
- [ ] Write unit tests for new service method
- [ ] Write integration tests for new endpoint
- [ ] Run `pre-commit run --all-files` to lint/format
- [ ] Run `pytest backend/tests` to verify all tests pass

### Frontend

- [ ] Add `HeatmapPointLight` type to `types/heatmap.ts`
- [ ] Add `HeatmapOverviewResponse` type to `types/heatmap.ts`
- [ ] Add `HeatmapOverviewParams` type to `types/heatmap.ts`
- [ ] Add `getHeatmapOverview()` to `transitApi.ts`
- [ ] Create `useHeatmapOverview.ts` hook
- [ ] Create `StationPopup.tsx` component
- [ ] Add `overviewToGeoJSON()` function to `MapLibreHeatmap.tsx`
- [ ] Update `MapLibreHeatmapProps` interface
- [ ] Update heatmap page to use overview pattern
- [ ] Write tests for new hook
- [ ] Run `npm run lint` to verify linting
- [ ] Run `npm run test -- --run` to verify tests pass
- [ ] Run `npm run type-check` to verify types

### Validation

- [ ] Deploy to staging environment
- [ ] Verify overview endpoint returns all impacted stations
- [ ] Verify payload size is ~120KB gzipped for full Germany
- [ ] Verify station click loads details in <100ms
- [ ] Verify cache hit rate on overview endpoint
- [ ] Verify no regression in existing heatmap functionality

---

## Appendix: Payload Size Calculation

**Lightweight point JSON (average)**:

```json
{
  "id": "de:11000:900100001",
  "lat": 52.5219,
  "lon": 13.4115,
  "i": 0.15,
  "n": "Berlin Hauptbahnhof"
}
```

≈ 85 bytes per station (including commas/brackets in array context)

**15,000 stations**:

- Raw JSON: 15,000 × 85 = 1,275,000 bytes ≈ **1.27 MB**
- Gzipped (~90% compression on JSON): ≈ **127 KB**

**Current full payload comparison**:

- 500 stations × 400 bytes = 200,000 bytes ≈ 200 KB raw, ~35 KB gzipped
- Shows only 3% of network

**Improvement**:

- 3.6× more data transferred (127KB vs 35KB)
- 30× more stations shown (15,000 vs 500)
- Net benefit: **8× better efficiency per station**
