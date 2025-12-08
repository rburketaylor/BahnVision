# MVG Cancellation Heatmap Feature - Compiled Plan

## Overview

Add a "Heatmap" page that visualizes MVG cancellation data as an interactive heatmap overlay on a Munich map using Leaflet.js + OpenStreetMap (free, no API key required).

---

## 1. Mapping Solution

**Recommendation: Leaflet.js + OpenStreetMap**
- 100% free with no API keys required
- Lightweight (38KB), mobile-friendly
- Excellent Munich coverage and plugin ecosystem

---

## 2. Backend Implementation

### 2.1 New API Endpoint

**File:** `backend/app/api/v1/endpoints/heatmap.py`

```python
# GET /api/v1/heatmap/cancellations
# Query params:
#   - time_range: str (1h, 6h, 24h, 7d, 30d) - default: 24h
#   - transport_modes: str (CSV) - default: all
#   - bucket_width: int (minutes) - default: 60
#   - bounding_box: str (optional) - "lat,lon,lat,lon"
```

**Response Schema:**
```json
{
  "time_range": {"from": "...", "to": "..."},
  "data_points": [
    {
      "station_id": "de:09162:100",
      "station_name": "Marienplatz",
      "latitude": 48.137,
      "longitude": 11.576,
      "total_departures": 1250,
      "cancelled_count": 45,
      "cancellation_rate": 0.036,
      "by_transport": {
        "UBAHN": {"total": 500, "cancelled": 20},
        "SBAHN": {"total": 750, "cancelled": 25}
      }
    }
  ],
  "summary": {
    "total_stations": 150,
    "overall_cancellation_rate": 0.028,
    "most_affected_station": "...",
    "most_affected_line": "..."
  }
}
```

### 2.2 Pydantic Models

**File:** `backend/app/models/heatmap.py`

```python
class HeatmapDataPoint(BaseModel):
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    total_departures: int
    cancelled_count: int
    cancellation_rate: float
    by_transport: dict[str, TransportStats]

class HeatmapResponse(BaseModel):
    time_range: TimeRange
    data_points: list[HeatmapDataPoint]
    summary: HeatmapSummary
```

### 2.3 Service Layer

**File:** `backend/app/services/heatmap_service.py`

```python
class HeatmapService:
    async def get_cancellation_heatmap(
        self,
        time_range: TimeRange,
        transport_modes: list[TransportMode],
        bucket_width_minutes: int = 60,
        bounding_box: BoundingBox | None = None
    ) -> list[HeatmapDataPoint]:
        """Generate geospatial cancellation heatmap data"""

    async def get_cancellation_hotspots(
        self,
        time_range: TimeRange,
        limit: int = 50
    ) -> list[CancellationHotspot]:
        """Identify top cancellation locations"""
```

**Caching Strategy:**
- Use existing `CacheService` pattern
- Cache key: `heatmap:{time_range}:{transport_modes_hash}:{bucket_width}`
- TTL: 5 minutes (configurable via `HEATMAP_CACHE_TTL_SECONDS`)

### 2.4 Database Query

Leverage existing `departure_observations` table:

```sql
SELECT 
    s.station_id,
    s.name,
    s.latitude,
    s.longitude,
    COUNT(*) as total_departures,
    COUNT(*) FILTER (WHERE do.status = 'cancelled') as cancelled_count
FROM departure_observations do
JOIN stations s ON do.station_id = s.station_id
WHERE do.planned_departure BETWEEN :from_time AND :to_time
GROUP BY s.station_id, s.name, s.latitude, s.longitude
```

### 2.5 Configuration

**Environment Variables:**
```bash
HEATMAP_CACHE_TTL_SECONDS=300
HEATMAP_DEFAULT_LOOKBACK_HOURS=24
HEATMAP_MAX_LOOKBACK_DAYS=30
HEATMAP_MAX_DATA_POINTS=10000
```

---

## 3. Frontend Implementation

### 3.1 Dependencies

**File:** `frontend/package.json`

```json
{
  "dependencies": {
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "leaflet.heat": "^0.2.0"
  },
  "devDependencies": {
    "@types/leaflet": "^1.9.8"
  }
}
```

### 3.2 TypeScript Types

**File:** `frontend/src/types/heatmap.ts`

```typescript
export interface HeatmapDataPoint {
  station_id: string
  station_name: string
  latitude: number
  longitude: number
  total_departures: number
  cancelled_count: number
  cancellation_rate: number
  by_transport: Record<string, { total: number; cancelled: number }>
}

export interface HeatmapResponse {
  time_range: { from: string; to: string }
  data_points: HeatmapDataPoint[]
  summary: {
    total_stations: number
    overall_cancellation_rate: number
    most_affected_station: string
    most_affected_line: string
  }
}

export interface HeatmapParams {
  time_range?: string
  transport_modes?: TransportType[]
}
```

### 3.3 API Client

**File:** `frontend/src/services/endpoints/mvgApi.ts`

```typescript
async getHeatmapData(params: HeatmapParams): Promise<ApiResponse<HeatmapResponse>> {
  const queryString = buildQueryString(params as unknown as Record<string, unknown>)
  return httpClient.request<HeatmapResponse>(`/api/v1/heatmap/cancellations${queryString}`)
}
```

### 3.4 React Hook

**File:** `frontend/src/hooks/useHeatmap.ts`

```typescript
import { useQuery } from '@tanstack/react-query'

export function useHeatmap(params: HeatmapParams) {
  return useQuery({
    queryKey: ['heatmap', 'cancellations', params],
    queryFn: () => apiClient.getHeatmapData(params),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })
}
```

### 3.5 Map Component

**File:** `frontend/src/components/CancellationHeatmap.tsx`

**Features:**
- Interactive Leaflet map centered on Munich (48.137, 11.576)
- Dynamic heatmap layer with cancellation intensity
- Station click interactions showing detailed stats
- Transport mode color coding (existing patterns)

**Heatmap Configuration:**
```typescript
const heatmapConfig = {
  radius: 25,
  blur: 15,
  maxZoom: 17,
  max: 1.0,
  gradient: {
    0.0: 'rgba(0, 255, 0, 0.0)',    // Green = no cancellations
    0.3: 'rgba(255, 255, 0, 0.6)',  // Yellow = moderate
    0.7: 'rgba(255, 165, 0, 0.8)',  // Orange = high
    1.0: 'rgba(255, 0, 0, 1.0)',    // Red = severe
  }
}
```

### 3.6 Controls Component

**File:** `frontend/src/components/heatmap/HeatmapControls.tsx`

**Features:**
- Time range selector (1h, 6h, 24h, 7d presets)
- Transport mode filter toggles
- Severity intensity slider
- Export functionality (PNG, CSV, JSON)

### 3.7 Page Component

**File:** `frontend/src/pages/HeatmapPage.tsx`

```typescript
const HeatmapPage: React.FC = () => {
  return (
    <PageLayout>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3">
          <CancellationHeatmap />
        </div>
        <div className="lg:col-span-1">
          <HeatmapControls />
          <HeatmapLegend />
          <CancellationStats />
        </div>
      </div>
    </PageLayout>
  )
}
```

### 3.8 Router & Navigation

**File:** `frontend/src/App.tsx`
```typescript
<Route path="/heatmap" element={<HeatmapPage />} />
```

**File:** `frontend/src/components/Layout.tsx`
```typescript
{ path: '/heatmap', label: 'Heatmap', icon: '🗺️' }
```

---

## 4. File Structure Summary

```
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   └── heatmap.py              # NEW: API endpoints
│   ├── models/
│   │   └── heatmap.py              # NEW: Pydantic models
│   └── services/
│       └── heatmap_service.py      # NEW: Aggregation logic

frontend/
├── src/
│   ├── components/
│   │   ├── CancellationHeatmap.tsx # NEW: Map component
│   │   └── heatmap/
│   │       ├── HeatmapControls.tsx # NEW: Filter controls
│   │       └── HeatmapLegend.tsx   # NEW: Color legend
│   ├── hooks/
│   │   └── useHeatmap.ts           # NEW: Data hook
│   ├── pages/
│   │   └── HeatmapPage.tsx         # NEW: Page
│   └── types/
│       └── heatmap.ts              # NEW: Types
```

---

## 5. Testing Plan

### Backend Tests
- `backend/tests/api/v1/endpoints/test_heatmap.py`
- `backend/tests/services/test_heatmap_service.py`
- Unit tests for aggregation logic with mock data
- Integration tests with TestClient

### Frontend Tests
- `frontend/src/pages/HeatmapPage.test.tsx`
- `frontend/src/components/CancellationHeatmap.test.tsx`
- MSW handlers for heatmap endpoint
- E2E tests: `frontend/tests/e2e/heatmap.spec.ts`

---

## 6. Performance Targets

| Metric | Target |
|--------|--------|
| API response time (cached) | < 200ms |
| Map rendering (1000+ points) | < 500ms |
| Cache hit rate | > 90% |
| Real-time data lag | < 5 minutes |
| Map interaction responsiveness | < 100ms |

---

## 7. Data Considerations

**Current State:** The `departure_observations` table exists but historical data persistence is "planned (Phase 2)".

**Approach:**
1. **MVP:** Aggregate from current cached departures (limited time window)
2. **Phase 2:** Extend once departure observation recording is implemented
3. **Optional:** Generate sample historical data for demo purposes

---

## 8. Implementation Order

1. **Backend models & types** - Define data structures
2. **Backend service** - Implement aggregation (cache-based for MVP)
3. **Backend endpoint** - Wire up API route with caching
4. **Frontend types** - Mirror backend models
5. **Frontend API client** - Add endpoint method
6. **Frontend hook** - Create `useHeatmap`
7. **Frontend map component** - Build Leaflet integration
8. **Frontend controls** - Add filters and time range selector
9. **Frontend page** - Assemble full page layout
10. **Navigation** - Add to router and nav
11. **Tests** - Add coverage for both ends

---

## 9. Open Questions

- [ ] Data source: Cache-based aggregation vs historical ingestion?
- [ ] Time presets: Confirm 1h, 6h, 24h, 7d defaults
- [ ] Auto-refresh interval for real-time updates?
- [ ] Mobile: Touch-friendly controls priority?
- [ ] Advanced features: Weather correlation analysis scope?
