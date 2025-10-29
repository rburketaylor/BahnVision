# API Integration Overview

All requests hit the FastAPI backend served at `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`). REST endpoints live under `/api/v1` except for Prometheus metrics.

## Shared Conventions
- Responses may include `X-Cache-Status` (`hit`, `miss`, `stale`, `stale-refresh`); expose this in the UI for freshness indicators.
- 404 errors often arrive with JSON `{"detail": "..."}`. Preserve the message for UX copy.
- Time fields are ISO 8601 UTC strings; convert to local timezone for display (Munich: `Europe/Berlin`).
- Backend accepts either station IDs (e.g., `de:09162:6`) or fuzzy names; prefer IDs after search selection to avoid ambiguity.

## `GET /api/v1/health`
- **Query params**: none.
- **Success (200)**:
  ```json
  {"status": "ok"}
  ```
  > Spec (`backend/docs/tech-spec.md:103-107`) mentions `version` and `uptime_seconds`; implementation currently returns only `status`. Surface current behavior and track spec gap in roadmap.
- **Error**: non-200 indicates backend outage; show critical banner.

## `GET /api/v1/mvg/stations/search`
- **Query params**:
  - `q` (string, required, min 1)
  - `limit` (int, optional, default 8, max 20)
- **Success (200)**:
  ```json
  {
    "query": "marienplatz",
    "results": [
      {
        "id": "de:09162:6",
        "name": "Marienplatz",
        "place": "München",
        "latitude": 48.13743,
        "longitude": 11.57549
      }
    ]
  }
  ```
- **Errors**:
  - 404 when no stations found (`{"detail": "No stations found for query 'foo'."}`)
  - 503 on cache lock timeout; retry with exponential backoff.

## `GET /api/v1/mvg/departures`
- **Query params** (`backend/app/api/v1/endpoints/mvg.py:42-139`):
  - `station` (string, required) – station ID or search term.
  - `limit` (int, default 10, range 1–40).
  - `offset` (int, default 0, range 0–60) – minutes to shift schedule.
  - `transport_type` (repeatable string) – filter list (validated enum names like `UBAHN`, `SBAHN`, `BUS`, `TRAM`, `REGIONAL`).
- **Success (200)**:
  ```json
  {
    "station": {
      "id": "de:09162:6",
      "name": "Marienplatz",
      "place": "München",
      "latitude": 48.13743,
      "longitude": 11.57549
    },
    "departures": [
      {
        "planned_time": "2025-10-29T07:30:00+00:00",
        "realtime_time": "2025-10-29T07:32:00+00:00",
        "delay_minutes": 2,
        "platform": "Gleis 2",
        "realtime": true,
        "line": "U3",
        "destination": "Fürstenried West",
        "transport_type": "UBAHN",
        "icon": "mvg-u3",
        "cancelled": false,
        "messages": ["Bauarbeiten zwischen Odeonsplatz und Giselastraße"]
      }
    ]
  }
  ```
- **Errors**:
  - 404 if station not found (cache stores not-found marker).
  - 502 on upstream MVG error without stale cache.
  - 503 when cache single-flight lock times out.

## `GET /api/v1/mvg/routes/plan`
- **Query params** (`backend/app/api/v1/endpoints/mvg.py:164-318`):
  - `origin` (string, required)
  - `destination` (string, required)
  - `departure_time` (ISO datetime, optional) **xor** `arrival_time` (ISO datetime, optional)
  - `transport_type` (repeatable string, optional)
- **Success (200)**:
  ```json
  {
    "origin": {"id": "de:09162:6", "name": "Marienplatz", "place": "München", "latitude": 48.13743, "longitude": 11.57549},
    "destination": {"id": "de:09184:17", "name": "Garching Forschungszentrum", "place": "Garching", "latitude": 48.2646, "longitude": 11.6713},
    "plans": [
      {
        "duration_minutes": 27,
        "transfers": 1,
        "departure": {"planned_time": "2025-10-29T07:40:00+00:00", "realtime_time": "2025-10-29T07:40:00+00:00", "platform": "Gleis 1", "line": "U6", "transport_type": "UBAHN"},
        "arrival": {"planned_time": "2025-10-29T08:07:00+00:00", "realtime_time": "2025-10-29T08:09:00+00:00", "platform": "Gleis 2"},
        "legs": [
          {
            "origin": {"name": "Marienplatz", "planned_time": "2025-10-29T07:40:00+00:00"},
            "destination": {"name": "Odeonsplatz", "planned_time": "2025-10-29T07:43:00+00:00"},
            "transport_type": "UBAHN",
            "line": "U6",
            "direction": "Garching Forschungszentrum",
            "duration_minutes": 3,
            "distance_meters": 2000,
            "intermediate_stops": []
          }
        ]
      }
    ]
  }
  ```
- **Errors**:
  - 422 if both `departure_time` and `arrival_time` supplied.
  - 404 when MVG cannot find a route (detail message reused).
  - 502/503 similar to departures for upstream/cache issues.

## `GET /metrics`
- **Purpose**: expose Prometheus metrics (`text/plain; version=0.0.4`).
- **Usage**: primarily for analysts; UI link should download or copy endpoint. No JSON parsing necessary.

## Future Integration Hooks
- Weather ingestion APIs do not exist yet; keep feature flag for future `/api/v1/weather/...` endpoints per spec.
- Persistence-backed history endpoints (e.g., route snapshots) planned for MS1-T2—design client architecture to accommodate without major refactor.
