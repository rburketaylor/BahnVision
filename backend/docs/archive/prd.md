# Product Requirements Document (PRD)
## 1. Problem & Goals
- Munich riders and visitors lack a single real-time view of MVG departures, delay risk, and alternate routes; the BahnVision vision targets this gap.
- The backend already brokers MVG departures, station search, route planning, and metrics, but reliability must be productized to power the dashboard frontend.
- Goal – deliver a resilient API that serves live departures, station search, and journey planning with consistent latency while respecting MVG rate limits documented in backend guidance.
- Goal – capture historical departures and weather context so Phase 2 predictive models and AI travel guidance become feasible using the existing persistence layer.
- Goal – expose operational health via Prometheus metrics so engineering and PM collaborators can monitor cache efficiency and MVG dependency without extra plumbing.

## 2. Target Users & Personas
- Primary persona – Munich commuter: relies on timely departures, seeks delay alerts, and needs quick station lookup while mobile; expects responses under one second to decide before leaving home.
- Secondary persona – Visiting traveler: plans routes across unfamiliar stations and values AI guidance recommending alternates; expects itineraries with transfers, durations, and delay context.
- Operations persona – Product and DevOps team: monitors cache hit ratios, MVG latency, and stale fallbacks to uphold SLAs and plan capacity.
- Assumption: Personas consume data through a React/Leaflet frontend still under construction and tracked historically in `backend/docs/archive/TODO.md`.

## 3. Use Cases & User Stories
- Commuter requests `GET /api/v1/mvg/departures` with station and limit to view accurate delays and platforms before boarding.
- Frontend performs type-ahead `GET /api/v1/mvg/stations/search` for “Marienplatz” and centers the map on the top suggestion.
- Traveler plans a trip using `GET /api/v1/mvg/routes/plan` with origin, destination, and transport filters to compare legs and transfers.
- DevOps scrapes `GET /metrics` to graph cache hit/miss and MVG latency trends for alerting.
- Assumption: Future Phase 2 ingestion jobs push historical departures and weather into PostgreSQL to feed predictive features.

## 4. Scope
### In-Scope
- FastAPI endpoints for departures, station search, route planning, health, and metrics as already implemented.
- Valkey-backed cache with single-flight locking, stale reads, and circuit breaker fallback delivered by the cache service.
- Configurable TTLs, Valkey URL, and database settings via environment variables and Docker Compose defaults.
- Persistence layer capturing stations, departures, weather, and ingestion runs for analytical and ML readiness.
- Prometheus instrumentation covering outbound MVG requests and cache events.

### Out-of-Scope
- React/Leaflet frontend map, saved routes UI, and alerting flows pending implementation.
- Model training, prediction API, and AI summaries targeted for Phase 2 and beyond.
- Authentication, authorization, user preferences storage, and notification delivery.
- Integrations with non-MVG data sources beyond the planned weather enrichment.

## 5. UX Flow (brief)
- User lands on the dashboard (assumption: Next.js + Leaflet) and sees nearby departures pulled via `/api/v1/mvg/departures`.
- Search input hits `/api/v1/mvg/stations/search`, updates map pins, and persists the query for future favorites.
- Selecting origin and destination triggers `/api/v1/mvg/routes/plan`; the UI highlights legs, transfers, and delay badges.
- Metrics panel for operations visualizes cache health using `/metrics`.
- Assumption: Offline fallback shows stale departures when MVG is unreachable, matching cache stale-return behavior.

## 6. Success Metrics (leading/lagging)
- Leading: Maintain >=70% cache hit ratio for departures over 24-hour windows using `bahnvision_cache_events_total` hits divided by total events.
- Leading: Keep 95th percentile API response time <=750 ms for departures and station search at 20 requests per second load, validated by synthetic tests.
- Lagging: Ensure >=90% of route plan requests return at least one itinerary, measured via `bahnvision_mvg_requests_total` route_lookup success share.
- Lagging: Achieve >=99.5% monthly availability for public endpoints as observed by external uptime monitoring.
- Assumption: Synthetic load testing environment and uptime monitor will be provisioned during QA.

## 7. Non-Functional Requirements (perf, sec, privacy)
- Performance: Cache TTL defaults (30 s live, 300–900 s stale) must keep average MVG calls per station under one per minute to stay inside rate limits.
- Reliability: Circuit breaker fallback serves stale data from the in-process store for up to 10 s to avoid hard downtime during Valkey issues.
- Observability: `/metrics` endpoint must remain scrapeable under load and include cache plus MVG histograms for Grafana alerts.
- Security: Secrets remain in environment variables or external stores; no credentials are committed to the repository.
- Privacy: Persisted data is limited to transit and weather telemetry, with no personal identifiers processed in the backend scope.

## 8. Constraints & Assumptions
- Depends on external MVG API availability and rate limits; outages degrade freshness regardless of caching.
- Valkey must be reachable at the configured URL; Docker Compose bundles a local instance for development.
- Database access requires PostgreSQL configured via `DATABASE_URL`; defaults target local environments.
- Assumption: Weather provider credentials and ingestion jobs will be provisioned before Phase 2 launch.
- Assumption: Frontend will surface cache status indicators using the `X-Cache-Status` header emitted today.

## 9. Acceptance Criteria (feature-level, testable)
- `GET /api/v1/health` returns `{"status": "ok"}` within 100 ms under nominal load.
- `GET /api/v1/mvg/departures` validates transport type filters, returns 404 for unknown stations, and sets `X-Cache-Status` to `hit`, `miss`, `stale`, or `stale-refresh` based on cache path.
- Stale cache paths trigger background refresh tasks without dropping responses; concurrent requests respect single-flight locking with <5 s lock wait.
- Station search with no matches returns 404 within 500 ms and records a `not_found` cache event for observability.
- Route planning rejects requests with both departure and arrival times provided, returns 404 when MVG lacks routes, and caches not-found markers for 15 s.
- `/metrics` exposes a Prometheus payload containing `bahnvision_cache_events_total`, `bahnvision_mvg_requests_total`, and corresponding histograms.

## 10. Open Questions
- What SLA and alert thresholds should operations enforce for MVG latency versus cache fallback?
- Which frontend states should visualize stale data versus live data when MVG or Valkey degrade?
- How will weather ingestion be scheduled and retried when external APIs fail?
- Do we require authentication or rate limiting before exposing the API publicly?
- What data retention window is acceptable for production cost and compliance, given the 18-month target in the design vision?
