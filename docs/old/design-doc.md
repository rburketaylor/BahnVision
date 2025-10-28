# BahnVision: AI-Assisted Munich Transit Dashboard

## Overview

BahnVision is a full-stack web application that visualizes Munich's S-Bahn and U-Bahn systems in real time, predicts delays using machine learning, and provides AI-generated travel recommendations. It is designed to demonstrate expertise in full-stack, data-driven, and AI-integrated development within a European urban context.

## Goals

* Showcase advanced full-stack and data engineering skills.
* Use real German transit data to create an intelligent, practical tool.
* Deploy a production-ready, cloud-native application.
* Build an impressive portfolio project aligned with relocation goals for Germany.

## Core Features

### Phase 1: Data Foundation & Visualization

* Integrate with **Deutsche Bahn (DB)** or **MVG** APIs to fetch live transit data.
* Use the Python [`mvg`](https://github.com/mondbaron/mvg) client inside FastAPI to broker MVG live data.
* Implement a production-grade caching strategy (cache-aside, single-flight, soft TTL, graceful fallback, observability).
* Visualize routes, stations, and real-time train status on a **Leaflet or Mapbox** map.
* Implement station search and route lookup.
* Cache API results to reduce rate limits and latency.

### Phase 2: AI & Predictive Features

* Collect and store historical train delay data.
* Train a simple **machine learning model** (e.g., RandomForest or XGBoost) to predict delay likelihood by line, time, and weather.
* Integrate **LLM-based summaries** (via OpenAI or Aleph Alpha API) for natural-language travel tips: e.g., *"Expect U2 delays between 8–10 AM; U5 may be faster today."*

### Phase 3: User Personalization & Deployment

* Add user authentication (Auth0 or Clerk).
* Enable users to save favorite routes and receive push/email alerts.
* Deploy backend and frontend using **Docker + Render/Fly.io/AWS**.
* Implement analytics dashboard (Grafana or custom React-based) for data insights.

## Optional Extensions

* **Bike Integration:** Merge OpenStreetMap bike routes with train data for multi-modal route planning.
* **CO₂ Tracker:** Show environmental benefits of public transit over driving.
* **API Gateway:** Offer a small REST API for developers to access historical delay and prediction data.

## Tech Stack

| Layer              | Tools/Tech                                      |
| ------------------ | ----------------------------------------------- |
| Frontend           | React (Next.js), TailwindCSS, Leaflet or Mapbox |
| Backend            | Python (FastAPI + `mvg` live data client + Valkey caching) |
| Database           | PostgreSQL (main data), Valkey (caching)         |
| Machine Learning   | scikit-learn, pandas, NumPy                     |
| AI/NLP Integration | OpenAI API, Aleph Alpha API (for German text)   |
| Deployment         | Docker, Render/Fly.io/AWS, GitHub Actions CI/CD |
| Visualization      | Mapbox GL JS, Recharts or Chart.js              |

## Data Sources

* **Deutsche Bahn API:** [https://developer.deutschebahn.com/](https://developer.deutschebahn.com/)
* **MVG Live API (Munich):** unofficial APIs available via GitHub.
* **Weather Data:** OpenWeatherMap or DWD (German Meteorological Service).

## Phase 1 Data Foundation

The backend now persists historical transit and weather context in PostgreSQL to enable downstream analytics and ML experimentation. Persistence is implemented with SQLAlchemy 2.x (async engine via `asyncpg`) and exposed through a `TransitDataRepository` to keep ingestion jobs decoupled from FastAPI routes.

### Database Schema Overview

```
stations ──┐          transit_lines ─┐
           │                         │
           ├─< departure_observations >─┬─ departure_weather_links ─> weather_observations
           │                         │
ingestion_runs ───────────────────────┘
```

- **stations**  
  Stores canonical MVG station metadata (`station_id`, `name`, `place`, geolocation, supported transport modes, canonical timezone). Updated via upserts to ensure naming/geo corrections are tracked; downstream tables reference the natural key directly.

- **transit_lines**  
  Catalog of MVG/U-Bahn/S-Bahn/Tram lines (`line_id`, `transport_mode`, `operator`, optional styling metadata). Supports future enrichment (e.g., service patterns) and prevents duplication across observations.

- **ingestion_runs**  
  Auditable log of ETL executions with timing and outcome fields (`job_name`, `source`, `status`, counts, `context` JSONB for ad-hoc metadata). Acts as parent for all batch inserts so we can trace problematic loads or replays.

- **departure_observations**  
  Core fact table with one row per observed departure. Captures scheduled vs. real-time timestamps, delay seconds, operational status, cancellation reasons, passenger-facing remarks, and the serialized raw payload for reproducibility. Indexed on `(station_id, planned_departure)` and `(line_id, planned_departure)` to support time-window scans. Links back to `ingestion_runs`, `stations`, and `transit_lines`.

- **weather_observations**  
  Hourly (or finer) weather snapshots near Munich stations. Includes temperature, humidity, wind metrics, precipitation detail, visibility, and provider-specific alerts. Stores raw JSONB payload, references an optional station (nearest stop) plus the associated ingestion run. Indexed by `(latitude, longitude, observed_at)` for geo-temporal lookups.

- **departure_weather_links**  
  Resolves the many-to-many relationship between departures and nearby weather readings. Stores the minute offset and link type (`closest`, `forecast`, etc.) so training pipelines can join without expensive spatial-temporal searches every time.

### Persistence Layer Responsibilities

- Repository API supports idempotent station/line upserts, ingestion-run bookkeeping, and bulk insert helpers for departures, weather records, and their associations.
- FastAPI receives a ready-made dependency (`get_transit_repository`) to wire ingestion jobs or admin endpoints directly onto the repository using a shared async session.
- Historical data retains raw payloads alongside normalized columns, allowing re-parsing as MVG/OpenWeather evolve without re-ingesting the raw feeds.
- Default retention target is **18 months** (configurable at the job level). Partitioning/archival will be revisited during Phase 2 once initial data volumes are known.

## Architecture

1. **Data Layer:** Fetch and cache real-time data from transit APIs.
2. **Prediction Service:** Periodically update ML models with historical data.
3. **API Layer:** Provide clean REST/GraphQL endpoints for the frontend.
4. **Frontend:** Dynamic map and route interface.
5. **AI Assistant:** Text-generation endpoint for travel summaries.

## Security & Compliance

* Use environment variables for API keys.
* GDPR-compliant data handling.
* Secure authentication and rate-limited public endpoints.

## Milestones

1. **M1: API Integration & Live Map** – basic transit map with live data.
2. **M2: Historical Data + Prediction Model** – collect and visualize delay trends.
3. **M3: AI Summaries + Auth System** – personalized AI features.
4. **M4: Deployment & Polish** – CI/CD, documentation, and public demo.

## Deliverables

* Public GitHub repository with code and README.
* Hosted demo (Render/Fly.io).
* Design doc and architecture diagrams.
* Screenshots or short demo video.

---

Future iterations could expand toward European-wide rail data integration, or even multimodal smart mobility (e-bikes + regional trains + DB Fernverkehr).
