Metrics/Alerts

Alerts reference metrics that don’t exist yet in code: bahnvision_api_latency_high, bahnvision_database_connection_failure, bahnvision_valkey_circuit_breaker_open (docs/devops/pipeline-plan.md:206, docs/devops/pipeline-plan.md:211). Current metrics are only cache/MVG client histograms and counters (backend/app/core/metrics.py:1). Add:
API request latency/error metrics via ASGI middleware (e.g., labels per route/status).
DB connectivity metric and scrapeable health.
Circuit-breaker-open metric emitted when opening the breaker (backend/app/services/cache.py:155).
Terminology/Naming

Use “Valkey” consistently; avoid “Redis” to prevent confusion unless explicitly supporting Redis too (docs/devops/pipeline-plan.md:344). The code supports REDIS_URL aliases, but project naming is Valkey-first (backend/app/core/config.py:13).
Kubernetes/Infra

Avoid running PostgreSQL as a plain Deployment in production (docs/devops/pipeline-plan.md:264–276). Prefer managed Postgres (RDS/Cloud SQL) or a StatefulSet with proper HA/storage. Similarly, define whether Valkey is ephemeral (in-cluster) or managed.
If ArgoCD is in scope (docs/devops/pipeline-plan.md:335), clarify GitOps flow: GH Actions should build/push images and update a manifests repo; ArgoCD handles cluster sync. Don’t also “helm install” from Actions.
Deploy + Migrations

Blue/green with DB changes needs an expand/contract strategy and backward-compatible migrations, not just “migration with backup” (docs/devops/pipeline-plan.md:120–142). Add online migration steps, backfills, and rollback notes (alembic offline --sql dry-run can be part of pre-deploy checks).
Security Scanning

CodeQL is great, but GitHub Advanced Security may be paid for private repos; confirm licensing or scope it to public repos. If Snyk isn’t available, add fallbacks: pip-audit, osv-scanner, and npm audit with severity gates.
Monitoring/Observability

Add API-level metrics and error-rate counters to back “API latency” and “error rate” SLAs (docs/devops/pipeline-plan.md:198–205). Consider request middleware or prometheus-fastapi instrumentation.
Consider cert management in K8s (cert-manager) and mention TLS/ingress automation.
Backups/DR

Specify concrete Postgres backup/PITR strategy (cloud managed preferred). Clarify expectations for Valkey (treat as cache, not a source of truth).
If you want, I can update the doc to:

Align alert names with implemented metrics and add a short TODO list to instrument what’s missing.
Clarify GitOps vs. direct helm apply, and note managed Postgres.
Tighten Valkey/Redis terminology and add the expand/contract migration note.
# Pipeline Changes

> Status: Planned (aspirational). Use this to track desired CI/CD and observability improvements; current implementation details live in `docs/tech-spec.md`.

## Current state vs planned state
- Current: Cache and MVG client Prometheus metrics are exposed at `/metrics` (see `backend/app/api/metrics.py`); alerts are not yet wired; GitHub Actions and infra choices are still proposals.
- Planned: Add API latency/error metrics via ASGI middleware, a Valkey circuit-breaker-open counter, and a database connectivity metric; solidify GitOps flow and managed data stores.

## Metrics & Alerts
- Align alert names with emitted metrics and add TODOs for missing signals:
  - API request latency/error metrics via middleware (label per route/status).
  - Database connectivity metric and scrapeable health endpoint.
  - Circuit-breaker-open metric emitted when opening the breaker (see `backend/app/services/cache.py`).
- Reference the existing cache/MVG counters and histograms instead of flagging them as missing.

## Terminology/Naming
- Use “Valkey” consistently; mention Redis only for compatibility (aliases supported via `REDIS_URL`).

## Kubernetes/Infra
- Prefer managed Postgres (or a StatefulSet with HA) instead of a plain Deployment.
- If ArgoCD is in scope, clarify GitOps flow: GitHub Actions builds/pushes images and updates a manifests repo; ArgoCD handles cluster sync. Avoid `helm install` directly from Actions.

## Deploy & Migrations
- For blue/green with DB changes, follow expand/contract migrations with backups and rollback notes (include `alembic` offline `--sql` dry runs in pre-deploy checks).

## Security Scanning
- Verify CodeQL licensing for private repos; fallbacks include `pip-audit`, `osv-scanner`, and `npm audit` with severity gates.

## Monitoring/Observability
- Add API-level metrics and error-rate counters to back “API latency” and “error rate” SLAs; consider request middleware or `prometheus-fastapi` instrumentation.
- Consider cert management in Kubernetes (cert-manager) and document TLS/ingress automation.

## Backups/DR
- Specify a concrete Postgres backup/PITR strategy (managed service preferred).
- Clarify expectations for Valkey (treat as cache, not a source of truth).
