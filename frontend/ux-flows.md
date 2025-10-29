# UX Flows & Screen Notes

## Personas
- **Daily commuter**: quickly checks departures and alternate routes on mobile.
- **Operations analyst**: desktop user monitoring cache freshness, metrics, and disruptions.

## Core Journeys

### 1. Station Search → Departures Board
```
[Landing] --tap--> [Station Search Field]
        --type--> [Autocomplete Results]
        --select--> [Departures Board]
                        |
                        v
                  [Cache Badge + Timestamp]
```
- Query: call `GET /api/v1/mvg/stations/search?q=...&limit=8` on every debounced input change.
- Display: list station name + place with highlight of query match; show icon per `transport_mode` once known.
- Upon selection: trigger `useDepartures` with station id (or name fallback), show spinner while waiting, reveal `X-Cache-Status` badge.

### 2. Departures Filtering & Refresh
- Controls: transport type chips, limit slider (default 10, max 40), walking offset selector (0–60 min).
- API: `GET /api/v1/mvg/departures?station=...&limit=...&offset=...&transport_type=...`.
- UI: table with line, destination, planned, realtime, delay, messages; highlight cancelled entries.
- Refresh CTA: manual refresh button invalidates query; auto-refresh every 30 s respecting backend lock throttling.

### 3. Route Planning Flow
```
[Planner Sheet]
    |-- origin input --> station search modal (reuse component)
    |-- destination input --> station search modal
    |-- optional times --> datetime pickers (mutually exclusive)
    '-- transport filters --> multi-select chips

Submit --> call tanstack mutation --> render itineraries list + map overlay
```
- API: `GET /api/v1/mvg/routes/plan` with origin/destination + either `departure_time` or `arrival_time`.
- Error states: show inline error if both times set; 404 with copy “No MVG routes available…”; propagate backend detail string.
- Display: vertical itinerary cards with summary (duration, transfers) and collapsible leg details; highlight legs on map.

### 4. System Health & Metrics Peek
- Sidebar badge uses `GET /api/v1/health` on load and every 60 s; green/amber/red indicator with uptime.
- Analyst view links to `/metrics` download to feed Grafana; provide instructions to copy endpoint for Prometheus scrape (no direct visualization yet).

### 5. Weather Overlay (Phase 2 placeholder)
- Greyed-out toggle with tooltip “Weather data coming soon”; ties into roadmap for future `/weather` endpoint.

## UI States & Feedback
- **Loading**: skeleton cards for departures and routes, shimmer effects to convey real-time nature.
- **Stale data**: when backend responds with `X-Cache-Status: stale` or `stale-refresh`, show yellow badge “Serving cached data”.
- **Empty**: explicit message when station search returns 404 or departures result contains zero entries.
- **Errors**: toast + inline message; route planning errors anchor near submit button.
- **Accessibility**: ensure screen reader announces cache status, delays, and cancellation reason via `aria-live` regions.

## Navigation Structure
- Top nav with tabs: `Departures`, `Planner`, `Insights` (future). Mobile uses bottom nav for quick access.
- Deep linking via query params (`/departures?station=...`) to allow bookmarks and kiosk configuration.
- Consider kiosk mode toggle that hides navigation chrome for wall displays.
