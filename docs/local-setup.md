# Local Development Setup

This guide covers setting up BahnVision for local development.

## Prerequisites

### Required Tools
- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- [Git](https://git-scm.com/)
- [Python](https://www.python.org/) (v3.11+) for backend development
- [Node.js](https://nodejs.org/) (v20+) for frontend development

## Quick Start

### Option 1: Docker Compose (Recommended)

The fastest way to get started:

```bash
# Clone the repository
git clone https://github.com/your-username/BahnVision.git
cd BahnVision

# Start all services
docker compose up --build

# Access the applications
open http://localhost:3000              # Frontend
open http://localhost:8000/docs         # Backend API (Swagger)
```

### Option 2: Local Development

For active development with hot reload:

```bash
# Quick setup (recommended)
./scripts/setup-dev.sh   # Downloads Node.js LTS, sets up Python venv, installs all deps
source .dev-env          # Activate the environment

# Start backend
uvicorn app.main:app --reload --app-dir backend

# Start frontend (in separate terminal)
source .dev-env
cd frontend
npm run dev
```

<details>
<summary>Manual setup (alternative)</summary>

```bash
# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Install pre-commit hooks (auto-runs black & ruff on commit)
pre-commit install

uvicorn app.main:app --reload

# Frontend setup (in separate terminal)
cd frontend
npm install
npm run dev
```

</details>

## Environment Configuration

Create a `.env` file in the project root:

```bash
# Database configuration
DATABASE_URL=postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision

# Cache configuration
VALKEY_URL=valkey://localhost:6379/0

# CORS configuration (for local development)
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173

# Optional: Override cache TTLs
TRANSIT_DEPARTURES_CACHE_TTL_SECONDS=30
TRANSIT_DEPARTURES_CACHE_STALE_TTL_SECONDS=300
```

See [runtime-configuration.md](./runtime-configuration.md) for all options.

## Troubleshooting

### Services not starting

```bash
# Check container logs
docker compose logs backend
docker compose logs postgres

# Check service health
docker compose ps
```

### Port conflicts

```bash
# Check what's using ports
lsof -i :3000
lsof -i :8000

# Stop conflicting services
docker compose down
```

### Database issues

```bash
# Check PostgreSQL connection
docker compose exec postgres psql -U bahnvision -d bahnvision -c "SELECT 1;"

# Reset database
docker compose down -v
docker compose up -d postgres
```

## Next Steps

- Read the [tech spec](./tech-spec.md) for architecture details
- Check the [runtime configuration](./runtime-configuration.md) for all env vars
