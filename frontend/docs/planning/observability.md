# Frontend Observability Plan

## Goals
- Provide visibility into client health that complements backend Prometheus metrics.
- Detect regressions in cache freshness, API failures, and interaction latency impacting riders.

## Telemetry Stack
- **Error Tracking**: Sentry (browser SDK) with release tags matching build hash. Capture console errors, unhandled promise rejections, and network failures.
- **Performance Monitoring**: Web Vitals via `@sentry/tracing` or `web-vitals` package feeding custom backend endpoint (Phase 2) or third-party dashboard.
- **Analytics**: Minimal event schema piped to privacy-compliant provider (e.g., Plausible) to measure feature adoption.

## Key Events & Metrics
- `station_search_submitted` – includes `query_length`, `result_count`, `latency_ms`, `cache_status`.
- `departures_view_loaded` – includes `station_id`, `transport_filters`, `cache_status`, `delay_count`.
- `route_plan_requested` – logs `origin_id`, `destination_id`, `has_departure_time`, `has_arrival_time`.
- `api_error` – include `endpoint`, `status_code`, `detail`, `retry` flag.
- `stale_data_displayed` – triggered when `X-Cache-Status` is `stale` or `stale-refresh`.

## Logs & Diagnostics
- Structured console logs behind debug flag (disabled in production) for developers.
- Build-time feature flag `VITE_ENABLE_DEBUG_LOGS` toggles log verbosity.

## Correlation With Backend Metrics
- Include `X-Request-Id` header from backend responses (add to API client) to correlate with FastAPI logs and Prometheus labels.
- Display last successful fetch timestamp to align with backend cache refresh duration metrics.

## Alerting Hooks
- Configure Sentry alerts for:
  - Error rate >2% over 5 min in production.
  - API 5xx spikes (tagged by endpoint) to notify ops Slack channel.
- Optional webhook to backend service that increments custom Prometheus counter for frontend error rate (future integration).

## Privacy & Compliance
- Do not log raw queries containing PII; hash station search queries before sending analytics.
- Respect EU cookies/GDPR: analytics opt-in banner with local storage persistence.

## Future Enhancements
- Integrate real user monitoring (RUM) dashboards in Grafana by exporting metrics to Prometheus via `prometheus-query` bridge.
- Add synthetic monitoring (Checkly) hitting key flows hourly with expected cache headers.
