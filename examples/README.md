# Examples

This directory contains example configurations for production deployment and advanced use cases.

## Contents

### `k8s/`
Kubernetes manifests for deploying BahnVision to a cluster. Includes:
- Backend and frontend deployments
- Valkey and PostgreSQL StatefulSets
- ConfigMaps and Secrets
- Ingress configuration
- ArgoCD application definition

**Note:** These are example manifests. Customize for your environment before deploying.

### `monitoring/`
Prometheus and Grafana configuration for observability:
- `prometheus.yml` - Scrape configuration for BahnVision metrics
- `grafana/` - Dashboard definitions

### `toxiproxy/`
Chaos testing configuration for validating resilience:
- Simulate network latency and failures
- Test circuit breaker behavior
- Validate stale cache fallbacks

## Usage

These examples are not used by the default `docker compose up` workflow. They're provided as reference implementations for production deployments.

```bash
# Example: Deploy to local Kind cluster
kind create cluster --config examples/k8s/kind-config.yaml
kubectl apply -f examples/k8s/
```
