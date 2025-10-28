# BahnVision TODO

## Phase 1 – Data Foundation
- [x] Implement station search and route lookup endpoints so the backend exposes MVG features beyond departures. Reference the `mvg` nearby/lines APIs. (design-doc.md:21-23, backend/README.md:49)
- [x] Add deterministic cache-aside configuration with per-endpoint TTL controls to match the production-grade caching roadmap. (backend/README.md:66-72)
- [x] Introduce stampede protection (single-flight locks) plus soft-TTL background refresh for cached departures. (backend/README.md:70-75)
- [ ] Harden Valkey failure handling with circuit-breaker behaviour and graceful in-process/disk fallbacks, including stale-if-error responses. (backend/README.md:76-81)
- [x] Instrument cache and MVG client interactions with metrics/logging for hit/miss ratios, fetch latency, and error counts. (backend/README.md:78)
- [ ] Design the initial PostgreSQL schema and persistence layer to store historical transit and weather data, preparing for ML work. (design-doc.md:27-28, design-doc.md:50, design-doc.md:56-60)

## Phase 1 – Frontend & Visualization
- Bootstrap the Next.js frontend with Leaflet/Mapbox to render the Munich rail map fed by the `/api/v1/mvg/departures` endpoint. (design-doc.md:21, design-doc.md:48-49, design-doc.md:67)
- Build a station search UI that calls the new lookup endpoint and centers the map on the selected station. (design-doc.md:22)
- Create a route planning view that visualizes itineraries and integrates real-time status from the backend. (design-doc.md:22, design-doc.md:67)

## Phase 1 – Quality & Tooling
- Stand up a `pytest` suite covering health/departures endpoints (FastAPI `TestClient`) and cache edge cases with mocked Valkey. (AGENTS.md:19-22)
- Provide reusable Valkey test fixtures or fakes so service tests stay deterministic. (AGENTS.md:21)
- Add a `.env.example` plus configuration docs describing required secrets and defaults. (AGENTS.md:29-31)

## Phase 2 – AI & Predictive Features
- Implement ingestion jobs that capture historical departure delays alongside weather context for modeling. (design-doc.md:27-28, design-doc.md:56-60)
- Train and evaluate a baseline delay-prediction model (e.g., RandomForest/XGBoost) and persist model artifacts for serving. (design-doc.md:28, design-doc.md:65)
- Expose a prediction API endpoint and integrate it into the frontend so users see delay likelihoods. (design-doc.md:65, design-doc.md:67)
- Add an AI-generated travel advisory endpoint leveraging OpenAI or Aleph Alpha, then surface summaries in the UI. (design-doc.md:29, design-doc.md:68)

## Phase 3 – Personalization & Deployment
- Integrate user authentication (Auth0/Clerk) across frontend and backend. (design-doc.md:33)
- Allow users to save favourite routes and manage notification preferences, backed by persistent storage. (design-doc.md:34)
- Implement push/email alert delivery when predictions exceed thresholds or disruptions occur. (design-doc.md:34)
- Set up CI/CD (GitHub Actions) and container-based deployment to Render/Fly.io/AWS for both services. (design-doc.md:35, design-doc.md:53, docker-compose.yml:1)
- Add an analytics dashboard (Grafana or custom React view) showing system metrics and transit KPIs. (design-doc.md:36)

## Stretch / Optional Enhancements
- Merge bike routes for multimodal planning, introduce CO₂ savings insights, and publish a public historical data API as outlined in the optional roadmap. (design-doc.md:40-42)
- Deliver supporting assets—architecture diagrams, screenshots, and a hosted demo link—to satisfy the documented deliverables. (design-doc.md:83-88)
