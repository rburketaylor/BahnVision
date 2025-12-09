# Local Development Setup

This guide covers setting up BahnVision for local development, including the demo environment with monitoring and chaos testing capabilities.

## Prerequisites

### Required Tools
- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- [Git](https://git-scm.com/)
- [Python](https://www.python.org/) (v3.11+) for local backend development
- [Node.js](https://nodejs.org/) (v20+) for local frontend development

### Optional Tools (for Kubernetes development)
- [kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [make](https://www.gnu.org/software/make/)

## Quick Start

### Option 1: Docker Compose (Recommended)

The fastest way to get started with all monitoring and chaos testing tools:

```bash
# Clone the repository
git clone https://github.com/your-username/BahnVision.git
cd BahnVision

# Start the full demo environment
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d

# Wait for services to be healthy (30-60 seconds)
docker compose ps

# Access the applications
open http://localhost:3000              # Frontend
open http://localhost:8000              # Backend API
open http://localhost:3001              # Grafana (admin/admin)
open http://localhost:9090              # Prometheus
open http://localhost:16686             # Jaeger
open http://localhost:5540              # Redis Commander
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

## Demo Environment Features

The demo environment includes:

### Core Services
- **Frontend**: React application at `http://localhost:3000`
- **Backend**: FastAPI application at `http://localhost:8000`
- **PostgreSQL**: Database at `localhost:5432`
- **Valkey**: Cache at `localhost:6379`

### Monitoring Stack
- **Prometheus**: Metrics collection at `http://localhost:9090`
  - Scrapes backend `/metrics` endpoint
  - Stores time-series data
- **Grafana**: Visualization dashboard at `http://localhost:3001`
  - Default credentials: admin/admin
  - Pre-configured BahnVision dashboards
  - Prometheus datasource auto-configured
- **Jaeger**: Distributed tracing at `http://localhost:16686`
  - Collects OpenTelemetry traces
  - Shows request flows and latency

### Admin Tools
- **Redis Commander**: Valkey admin interface at `http://localhost:5540`
  - Browse cache contents
  - Monitor cache operations

### Chaos Testing
- **Toxiproxy**: Chaos proxy at `http://localhost:8474` (admin API)
  - Simulates network failures
  - Adds latency and bandwidth limits
  - Tests system resilience

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root:

```bash
# Database configuration
# For local hot-reload dev
DATABASE_URL=postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision

# Cache configuration
VALKEY_URL=valkey://localhost:6379/0

# CORS configuration (for local development)
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173

# Optional: Override cache TTLs
MVG_DEPARTURES_CACHE_TTL_SECONDS=30
MVG_DEPARTURES_CACHE_STALE_TTL_SECONDS=300
```

### OpenTelemetry Configuration (Demo Environment)

The demo environment automatically configures OpenTelemetry tracing:

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=bahnvision-backend
OTEL_SERVICE_VERSION=0.1.0
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
OTEL_PROPAGATORS=tracecontext,baggage,b3
```

> **Note**
> When you run the compose demo overlay, the backend container automatically overrides `DATABASE_URL` and `VALKEY_URL` to point at `toxiproxy` so chaos scenarios affect both Postgres and Valkey. No manual changes are required for the demo stack.

## Chaos Testing

### Using the Chaos Scenarios Script

The demo environment includes a comprehensive chaos testing script:

```bash
# Interactive mode
./scripts/chaos-scenarios.sh interactive

# Individual scenarios
./scripts/chaos-scenarios.sh reset                    # Reset everything
./scripts/chaos-scenarios.sh postgres-latency 2000    # Add 2s latency to PostgreSQL
./scripts/chaos-scenarios.sh valkey-outage           # Complete Valkey outage
./scripts/chaos-scenarios.sh status                  # Show current status
```

### Available Chaos Scenarios

1. **Latency Injection**: Add delays to database/cache connections
2. **Failure Simulation**: Introduce random connection failures
3. **Complete Outages**: Simulate service unavailability
4. **Bandwidth Limitation**: Slow down data transfer
5. **Timeout Issues**: Simulate connection timeout problems

### Testing Resilience Features

When chaos scenarios are active, test:

- **Circuit Breaker**: Automatic fallback when cache fails
- **Stale Cache**: Continued operation with expired data
- **Graceful Degradation**: Reduced functionality vs. complete failure
- **Recovery**: Automatic healing when issues are resolved

## Monitoring and Observability

### Key Metrics to Monitor

**Cache Performance** (in Grafana):
- Cache hit ratio (>70% target)
- Cache refresh latency
- Cache events (hits, misses, stale reads)

**API Performance**:
- MVG API latency (<750ms P95 target)
- Request success rate
- Error rates by endpoint

**Infrastructure**:
- Resource utilization (CPU, memory)
- Container health / readiness

### Distributed Tracing

**Jaeger Tracing** shows:
- Request flows through the system
- Database query timing
- Cache operation timing
- External API call timing

**Trace Analysis**:
- Identify performance bottlenecks
- Understand request propagation
- Debug complex request flows

## Development Workflow

### Making Changes

1. **Code Changes**: Edit source files
2. **Local Testing**: Use local development mode with hot reload
3. **Integration Testing**: Use demo environment for full-stack testing
4. **Chaos Testing**: Verify resilience under failure conditions
5. **Monitoring**: Check metrics and traces for regressions

### Environment-Specific Configurations

| Config | Local Development | Demo Environment |
|--------|-------------------|------------------|
| Database | localhost:5432 | toxiproxy:5432 → postgres |
| Cache | localhost:6379 | toxiproxy:6379 → valkey |
| Tracing | Disabled | Enabled (Jaeger) |
| Monitoring | None | Full stack |

## Troubleshooting

### Common Issues

**Services not starting**:
```bash
# Check container logs
docker compose logs backend
docker compose logs postgres

# Check service health
docker compose ps
```

**Port conflicts**:
```bash
# Check what's using ports
lsof -i :3000
lsof -i :8000

# Stop conflicting services
docker compose down
```

**Cache issues**:
```bash
# Clear Valkey cache
redis-cli -h localhost -p 6379 FLUSHALL

# Check cache contents via Redis Commander
open http://localhost:5540
```

**Database issues**:
```bash
# Check PostgreSQL connection
docker compose exec postgres psql -U bahnvision -d bahnvision -c "SELECT 1;"

# Reset database
docker compose down -v
docker compose up -d postgres
```

### Performance Issues

**High latency**:
1. Check Grafana dashboards for bottlenecks
2. Review Jaeger traces for slow operations
3. Verify cache hit ratios
4. Check resource utilization

**Memory issues**:
1. Monitor container resource usage
2. Check for memory leaks in traces
3. Verify cache configuration TTLs

### Getting Help

1. **Check logs**: `docker compose logs [service]`
2. **Check metrics**: Grafana dashboards at `http://localhost:3001`
3. **Check traces**: Jaeger at `http://localhost:16686`
4. **Reset environment**: `docker compose down -v && docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d`

## Next Steps

- Explore the [demo guide](./demo-guide.md) for scripted demonstrations
- Read about [Kubernetes deployment](./k8s-deployment.md)
- Learn about [AWS migration](./aws-migration.md)
- Review the [architecture documentation](../backend/docs/architecture/)
