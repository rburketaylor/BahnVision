# Cloud Emulation Plan (AWS-Compatible, Free, Local)

This plan delivers an AWS-like development and demo environment using only free/OSS components. It keeps the compose-first developer experience lightweight while offering optional add-ons for Kubernetes and GitOps parity.

Key goals
- Compose-first demo: start everything with one overlay file and showcase metrics, tracing, and chaos testing.
- Cloud parity optics: map local services to AWS counterparts using OSS tooling (Prometheus/Grafana, Jaeger, Toxiproxy).
- Optional depth: advanced modules (kind + ArgoCD, CI add-ons) are opt-in so the core remains lean.

Out of scope (for now)
- Multi-AZ PostgreSQL HA within Docker Compose. Use a single Postgres. Explore HA only in Kubernetes if required later.
- Heavy meshes or service-to-service encryption. Stick to tracing + ingress for observability.
- Connection proxies (PgBouncer/RDS Proxy). Local poolers add noise without improving the demo story.

Phasing overview
- Phase 0: Prereqs and conventions
- Phase 1: Compose observability stack (Prometheus, Grafana, Redis Commander, Toxiproxy)
- Phase 2: Tracing enablement (OpenTelemetry + Jaeger)
- Phase 3: Failure & resilience drills (chaos scripts + dashboards)
- Optional Module A: Kubernetes parity (kind, ingress-nginx, ArgoCD)
- Optional Module B: CI/CD & documentation polish

AWS mapping
- RDS (PostgreSQL) → local Postgres container (single instance)
- ElastiCache → Valkey + Redis Commander
- CloudWatch/Prometheus → Prometheus + Grafana dashboards
- AWS X-Ray → Jaeger via OTLP exporter
- Fault injection / resilience → Toxiproxy chaos scripts
- EKS + GitOps (optional) → kind cluster + ArgoCD applications

---

## Phase 0 — Prereqs and conventions

- Compose overlay: run with `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d`.
- Core ports: frontend `3000`, backend `8000`, Postgres `5432`, Valkey `6379`.
- New ports: Prometheus `9090`, Grafana `3001`, Jaeger `16686`, Redis Commander `5540`.
- Environment toggles:
  - `DATABASE_URL` defaults to the Postgres service through Toxiproxy (`postgresql+asyncpg://bahnvision:bahnvision@toxiproxy:5432/bahnvision`).
  - `VALKEY_URL` defaults to Valkey via Toxiproxy (`valkey://toxiproxy:6379/0`).
  - Chaos scripts target the Toxiproxy admin API at `http://localhost:8474`.
- Secrets live in `.env` (not committed).

---

## Phase 1 — Compose observability stack (Week 1)

Deliverables
- `docker-compose.demo.yml` overlay with:
  - Prometheus scraping backend `/metrics`.
  - Grafana provisioned with Prometheus datasource and starter dashboards.
  - Redis Commander for Valkey inspection.
  - Toxiproxy proxies for Postgres and Valkey (pre-wired for chaos scenarios).
  - Jaeger all-in-one for tracing UI (enabled in Phase 2).
- Monitoring config under `examples/monitoring/`:
  - `examples/monitoring/prometheus.yml` scraping backend metrics.
  - `examples/monitoring/grafana/provisioning/datasources/prometheus.yaml`.
  - `examples/monitoring/grafana/dashboards/*.json` visualising cache/transit metrics.

Notes & pitfalls
- Compose ignores `deploy.resources`; resource limits are demonstrated later in Kubernetes, not locally.
- Keep the overlay optional: default `docker compose up` still runs the minimal stack.

---

## Phase 2 — Tracing enablement (Week 2)

Goal: produce meaningful traces before adding Jaeger to dashboards.

Deliverables
- Backend OpenTelemetry wiring:
  - FastAPI and `httpx` instrumentation.
  - OTLP exporter configuration via env (`OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317`).
  - Optional header propagation helper for outbound GTFS requests.
- Compose overlay: Jaeger service runs alongside Prometheus/Grafana.
- Documentation updates describing how to toggle tracing with `OTEL_ENABLED`.

---

## Phase 3 — Failure & resilience drills (Week 3)

Deliverables
- `examples/toxiproxy/toxiproxy.json` defining Postgres + Valkey proxies.
- `scripts/chaos-scenarios.sh` with latency, failure, outage, and bandwidth scenarios.
- Demo scripts (`docs/demo-guide.md`) showing how to:
  - Invoke chaos scripts.
  - Watch Prometheus/Grafana/Jaeger for impact.
  - Demonstrate graceful degradation (cache stale reads, circuit breakers).

Optional extensions
- Document how to simulate resource pressure (CPU/memory) using Docker Desktop or K8s limits (see Module A).

---

## Optional Module A — Kubernetes parity (Week 4+)

Focus: show EKS-style deployment without bloating the default demo.

Deliverables (opt-in)
- `examples/k8s/kind-config.yaml` with ingress port mappings.
- `scripts/setup-kind.sh` to create a kind cluster, install ingress-nginx, deploy ArgoCD, and apply manifests.
- K8s manifests under `examples/k8s/` covering backend/frontend Deployments and StatefulSets for Postgres/Valkey.
- `examples/k8s/argocd/*.yaml` applications pointing at this repo (update `repoURL` to your fork).

Notes
- Frontend containers should be built with `VITE_API_BASE_URL=/api` for cluster usage; document the build flag.
- Add Jaeger/Tempo to the cluster only if tracing parity is required.

---

## Optional Module B — CI/CD & documentation (Week 4+)

Deliverables (opt-in)
- GitHub Actions jobs for Bandit, `npm audit`, Trivy image scan, optional Semgrep.
- Optional kind-based integration test job (build images, deploy manifests, run health checks).
- Documentation updates:
  - `docs/local-setup.md` (compose quick start + optional K8s).
  - `docs/demo-guide.md` (scripted walkthrough + chaos scenarios).
  - `docs/aws-migration.md` (map local services to AWS).

---

## File/folder layout

```
docker-compose.demo.yml                 # overlay services: prometheus, grafana, toxiproxy, redis-commander, jaeger
monitoring/
  prometheus.yml
  grafana/
    provisioning/
      datasources/prometheus.yaml
      dashboards/dashboards.yaml
    dashboards/
      bahnvision-overview.json
scripts/
  setup-kind.sh                         # optional module A
  security-scan.sh                      # optional module B
  chaos-scenarios.sh
k8s/                                     # optional module A
  kind-config.yaml
  backend-deployment.yaml
  frontend-deployment.yaml
  postgres-statefulset.yaml
  valkey-statefulset.yaml
  ingress.yaml
  argocd/
    app-backend.yaml
    app-frontend.yaml
toxiproxy/
  toxiproxy.json
docs/
  local-setup.md
  demo-guide.md
  aws-migration.md
  devops/cloud-emulation-plan.md
```

---

## Demo commands

- Start the full demo overlay: `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d`
- Run chaos scenarios: `./scripts/chaos-scenarios.sh postgres-latency 2000`
- Tear down the demo stack: `docker compose -f docker-compose.yml -f docker-compose.demo.yml down -v`
- Optional (kind): `./scripts/setup-kind.sh`
- Optional (security scans): `./scripts/security-scan.sh`

Default endpoints
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)
- Jaeger: http://localhost:16686
- Redis Commander: http://localhost:5540

---

## Risks & mitigations

- **Tracing disabled**: make tracing opt-in (`OTEL_ENABLED=false` by default) to avoid Jaeger hard dependency in lean demos.
- **Chaos tooling**: ensure backend points to Toxiproxy (already configured) so scenarios visibly affect requests.
- **Compose portability**: avoid privileged containers (cAdvisor) to keep Mac/Windows support intact.
- **Optional modules drift**: clearly mark kind/ArgoCD/CI as opt-in so they don’t block the core demo.

---

## Minimal code impact

- Backend OpenTelemetry setup (FastAPI + httpx instrumentation).
- Chaos script helpers (already present) and docs.
- No API contract changes; metrics remain under `bahnvision_*` names.

