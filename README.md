# BahnVision

Real-time German transit data API and dashboard. Live departures, station search, and heatmap visualization powered by GTFS data with Valkey caching for fast, reliable responses.

## Quick Start

### Docker (Recommended)
```bash
docker compose up --build
```
- **API**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000

### Local Development

**Quick Setup (Recommended):**
```bash
./scripts/setup-dev.sh   # Downloads Node.js LTS, sets up Python venv
source .dev-env          # Activate the environment
```

**Backend:**
```bash
cd backend
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm run dev
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/transit/stations/search?query=marienplatz` | Station search |
| `GET /api/v1/transit/departures?station=marienplatz` | Live departures |
| `GET /api/v1/transit/heatmap/data` | Heatmap activity data |
| `GET /api/v1/health` | Health check |
| `GET /metrics` | Prometheus metrics |

**Response Headers:**
- `X-Cache-Status`: `hit`, `miss`, `stale`, or `stale-refresh`
- `X-Request-Id`: Request correlation ID

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_URL` | `valkey://localhost:6379/0` | Cache connection |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Database connection |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend API URL |

See `docs/runtime-configuration.md` for all options.

## Testing

```bash
# Backend
pytest backend/tests/

# Frontend
cd frontend && npm test
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints
│   │   ├── services/     # Business logic, caching
│   │   ├── models/       # Pydantic schemas
│   │   └── persistence/  # Database layer
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── hooks/
│       └── services/
├── docs/                 # Documentation
```

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Frontend  │─────▶│   FastAPI   │─────▶│  GTFS Feed  │
│   (React)   │      │   Backend   │      │  (Germany)  │
└─────────────┘      └──────┬──────┘      └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌──────────┐  ┌──────────┐
         │ Valkey │  │ Postgres │  │ Fallback │
         │ Cache  │  │   (DB)   │  │  Cache   │
         └────────┘  └──────────┘  └──────────┘
```

**Caching:** Requests hit Valkey first. On miss, fetch from GTFS data and cache the result. Stale data is served while refreshing in the background. Circuit breaker falls back to in-memory cache if Valkey is unavailable.

## Security Considerations

This project implements several security best practices:

- **Container Security**: All containers run as non-root users (`appuser`, `nginx`)
- **Security Headers**: HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy
- **CORS Protection**: Strict mode available; wildcard origins rejected by default
- **Rate Limiting**: Configurable request limits per minute/hour/day
- **Production Safeguards**: Application refuses to start with default credentials in production mode
- **CI/CD Security Scanning**: Bandit, Safety, Semgrep, npm audit, and Trivy container scanning

**CSP Note**: The Content Security Policy currently allows `'unsafe-inline'` for compatibility with MapLibre GL's WebGL rendering pipeline. A future enhancement would implement nonce-based CSP with server-side nonce injection. See [`docs/planning/security-changes.md`](docs/planning/security-changes.md) for the planned approach.

## Contributing

- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`)
- Run tests before submitting PRs
- See `AGENTS.md` for AI coding guidelines
