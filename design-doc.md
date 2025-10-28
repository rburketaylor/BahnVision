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
