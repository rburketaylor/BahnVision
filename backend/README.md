# BahnVision Backend

This directory contains the Python/FastAPI backend for BahnVision. The service
uses the [`mvg`](https://github.com/mondbaron/mvg) package to fetch live data
from Münchner Verkehrsgesellschaft (MVG) and exposes it through a REST API that
the frontend can consume.

## Getting Started

1. **Create a virtual environment (recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Run the API**
   ```bash
   uvicorn app.main:app --reload --app-dir backend/app
   ```

   The service will listen on `http://127.0.0.1:8000` by default. Open
   `http://127.0.0.1:8000/docs` to explore the interactive Swagger UI.

## Key Endpoints

- `GET /api/v1/health` – readiness probe.
- `GET /api/v1/mvg/departures` – upcoming departures for a station. Parameters:
  - `station` (required): station name or global MVG station id (e.g.
    `de:09162:6` for München Hauptbahnhof).
  - `limit` (optional): number of departures to retrieve (default 10, max 40).
  - `offset` (optional): minutes to offset departures (e.g. walking time).
  - `transport_type` (optional, repeatable): filter by transport mode, accepts
    values like `UBAHN`, `SBAHN`, `tram`, `bus`.

Example request:
```bash
curl "http://127.0.0.1:8000/api/v1/mvg/departures?station=de:09162:6&transport_type=UBAHN"
```

## Notes

- The MVG API enforces rate limits; consider adding caching when wiring this
  endpoint to the frontend.
- The `mvg` client offers additional endpoints (`nearby`, `lines`, etc.) that
  can be wrapped in similar fashion when needed.

## Run with Docker

1. **Build the image**
   ```bash
   docker build -f backend/Dockerfile -t bahnvision-backend .
   ```

2. **Start the container**
   ```bash
   docker run --rm -p 8000:8000 bahnvision-backend
   ```

   The API will be available on `http://127.0.0.1:8000`. Pass environment
   variables with `-e KEY=value` or mount config files as needed.

When composing multiple services, add this container to a `docker-compose.yml`
and map the `backend` image alongside dependencies like Redis or PostgreSQL.
