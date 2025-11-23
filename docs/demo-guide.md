# Demo Guide

This guide provides scripted demonstrations of BahnVision's features, including monitoring, tracing, and resilience testing using the chaos engineering tools.

## Prerequisites

Complete the [Local Development Setup](./local-setup.md) first, then start the demo environment:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
```

Note: The examples use `open` (macOS). On Linux, replace `open` with `xdg-open`.

Wait for all services to be healthy:
```bash
docker compose ps
```

## Demo 1: Application Overview (5 minutes)

### Objective
Showcase the core functionality and performance characteristics of BahnVision.

### Script

```bash
# 1. Show the application
echo "🚆 Welcome to BahnVision Demo"
echo "==============================="
echo
echo "Opening the frontend application..."
open http://localhost:3000

echo "1. Frontend: Munich public transit data visualization"
echo "   - Real-time departure information"
echo "   - Route planning capabilities"
echo "   - Station search functionality"
echo

# 2. Show backend API
echo "2. Backend API: FastAPI with comprehensive observability"
open http://localhost:8000/docs
echo "   - Interactive API documentation"
echo "   - RESTful endpoints"
echo "   - Comprehensive error handling"
echo

# 3. Show metrics endpoint
echo "3. Metrics: Prometheus-compatible metrics endpoint"
curl -s http://localhost:8000/metrics | head -20
echo "   - Cache performance metrics"
echo "   - MVG client latency and outcome metrics"
echo "   - Transport-type breakdown counters"
echo

read -p "Press Enter to continue to monitoring demo..."
```

## Demo 2: Monitoring Stack (10 minutes)

### Objective
Demonstrate the comprehensive monitoring capabilities.

### Script

```bash
echo "📊 Monitoring Demo"
echo "=================="

# 1. Prometheus
echo "1. Prometheus: Metrics collection and storage"
echo "   Opening Prometheus web UI..."
open http://localhost:9090

echo "   Key metrics to explore:"
echo "   - bahnvision_cache_events_total"
echo "   - bahnvision_mvg_request_seconds_bucket"
echo "   - bahnvision_mvg_requests_total"
echo "   - bahnvision_mvg_transport_requests_total"
echo

echo "Example PromQL queries:"
echo "   - Cache hit ratio: sum(rate(bahnvision_cache_events_total{event=\"hit\"}[5m])) / (sum(rate(bahnvision_cache_events_total{event=\"hit\"}[5m])) + sum(rate(bahnvision_cache_events_total{event=\"miss\"}[5m])))"
echo "   - P95 latency: histogram_quantile(0.95, sum(rate(bahnvision_mvg_request_seconds_bucket[5m])) by (le, endpoint))"
echo

read -p "Press Enter to continue to Grafana..."

# 2. Grafana
echo "2. Grafana: Visualization dashboards"
echo "   Opening Grafana..."
open http://localhost:3001

echo "   Login credentials: admin / admin"
echo
echo "   Available dashboards:"
echo "   - BahnVision Overview: Cache hit ratios, MVG latency"
echo "   - System metrics: Resource utilization"
echo "   - Custom panels: Real-time performance monitoring"
echo

# Generate some traffic for better metrics
echo "3. Generating sample traffic..."
for i in {1..10}; do
  curl -s "http://localhost:8000/api/v1/stations/search?query=Hauptbahnhof" > /dev/null &
  curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof" > /dev/null &
done
wait

echo "   Traffic generated. Check Grafana for updated metrics!"
echo

read -p "Press Enter to continue to distributed tracing..."
```

## Demo 3: Distributed Tracing (10 minutes)

### Objective
Show how OpenTelemetry tracing provides end-to-end visibility.

### Script

```bash
echo "🔍 Distributed Tracing Demo"
echo "==========================="

echo "Note: Tracing is enabled only when OTEL is configured (use docker-compose.demo.yml which sets OTEL_ENABLED=true and Jaeger)."
echo
echo "1. Jaeger: Distributed tracing platform"
echo "   Opening Jaeger UI..."
open http://localhost:16686

echo "   Features to explore:"
echo "   - Service topology visualization"
echo "   - Trace timeline analysis"
echo "   - Performance bottleneck identification"
echo

# 2. Generate some traced requests
echo "2. Generating traced requests..."
echo "   Each request will be traced through the system:"
echo "   - HTTP request → FastAPI → Service layer → Cache/DB (when tracing is enabled)"
echo

for i in {1..5}; do
  echo "   Request $i: Searching for 'Marienplatz'..."
  curl -s "http://localhost:8000/api/v1/stations/search?query=Marienplatz" > /dev/null
  sleep 1
done

echo
echo "3. Analyze traces in Jaeger:"
echo "   - Look for complete request flows"
echo "   - Identify cache hits vs. misses"
echo "   - Check database query timing"
echo "   - Verify OpenTelemetry propagation"
echo

echo "   In Jaeger UI:"
echo "   - Select 'bahnvision-backend' service"
echo "   - Click 'Find Traces'"
echo "   - Click on individual traces to see details"
echo

read -p "Press Enter to continue to resilience testing..."
```

## Demo 4: Resilience Testing (15 minutes)

### Objective
Demonstrate the system's resilience under various failure conditions.

### Script

```bash
echo "🛡️  Resilience Testing Demo"
echo "=========================="

echo "This demo shows how BahnVision gracefully handles failures:"
echo "   - Cache failures with stale data fallback and Valkey circuit breaker"
echo "   - Database latency impact (no circuit breaker today)"
echo "   - Network latency and bandwidth limitations"
echo

read -p "Press Enter to start chaos scenarios..."

# 1. Baseline - Normal operation
echo "1. Establishing baseline performance..."
echo "   Testing API performance under normal conditions:"

time curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=5" > /dev/null
echo "   ✅ Normal operation completed"
echo

read -p "Press Enter to simulate Valkey cache failures..."

# 2. Cache failure scenario
echo "2. Cache failure scenario:"
echo "   Simulating complete Valkey cache failure..."

./scripts/chaos-scenarios.sh valkey-outage

echo "   Testing API with cache unavailable:"
time curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=5" > /dev/null

echo "   Expected: Service continues with direct MVG API calls; cache circuit breaker prevents cascading failures."
echo

read -p "Press Enter to simulate PostgreSQL latency..."

# 3. Database latency scenario
echo "3. Database latency scenario:"
echo "   Adding 2-second latency to PostgreSQL connections..."

./scripts/chaos-scenarios.sh reset
./scripts/chaos-scenarios.sh postgres-latency 2000

echo "   Testing API with database latency:"
time curl -s "http://localhost:8000/api/v1/stations/search?query=Sendlinger" > /dev/null

echo "   Observe: Cache may still serve warm keys; DB queries may slow down when cold."
echo

read -p "Press Enter to simulate bandwidth limitations..."

# 4. Bandwidth limitation scenario
echo "4. Bandwidth limitation scenario:"
echo "   Limiting network bandwidth to 1KB/s..."

./scripts/chaos-scenarios.sh reset
./scripts/chaos-scenarios.sh bandwidth-limit 1000

echo "   Testing API with limited bandwidth:"
time curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=10" > /dev/null

echo "   Observe: Requests should complete with higher latency; verify timeout handling and recovery."
echo

# 5. Recovery demonstration
echo "5. Recovery demonstration:"
echo "   Removing all chaos conditions..."

./scripts/chaos-scenarios.sh reset

echo "   Testing recovery:"
time curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=5" > /dev/null

echo "   ✅ System returns to normal performance"
echo "   ✅ All components fully operational"
echo "   ✅ No manual intervention required"
echo

read -p "Press Enter to continue to interactive chaos testing..."
```

## Demo 5: Interactive Chaos Testing (10 minutes)

### Objective
Let participants experiment with different failure scenarios.

### Script

```bash
echo "🎮 Interactive Chaos Testing"
echo "=========================="

echo "Now you can experiment with different failure scenarios!"
echo "   Launch interactive mode:"
echo

./scripts/chaos-scenarios.sh interactive

echo
echo "Suggested experiments:"
echo "1. Try different latency values (500ms, 2000ms, 5000ms)"
echo "2. Combine multiple failures (latency + packet loss)"
echo "3. Test partial failures vs. complete outages"
echo "4. Observe how different components respond"
echo

echo "Commands to try in separate terminals:"
echo "   # Monitor API responses"
echo "   watch -n 1 'curl -s http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=1'"
echo
echo "   # Monitor cache metrics"
echo "   curl -s http://localhost:8000/metrics | grep bahnvision_cache"
echo
echo "   # Check system health"
echo "   curl -s http://localhost:8000/health"
echo

read -p "Press Enter to continue to performance analysis..."
```

## Demo 6: Performance Analysis (10 minutes)

### Objective
Analyze performance characteristics and optimization opportunities.

### Script

```bash
echo "📈 Performance Analysis Demo"
echo "==========================="

echo "1. Cache Performance Analysis:"
echo "   Let's analyze cache effectiveness..."

# Generate cacheable requests
echo "   Generating cacheable requests..."
for i in {1..20}; do
  curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=5" > /dev/null &
done
wait

echo "   Cache metrics after repeated requests:"
curl -s http://localhost:8000/metrics | grep bahnvision_cache_events_total | sort
echo

echo "   Key observations:"
echo "   - First request: cache miss, fetches from MVG API"
echo "   - Subsequent requests: cache hits, served from memory"
echo "   - TTL-based expiration ensures fresh data"
echo

read -p "Press Enter to analyze API performance..."

# 2. API Performance Analysis
echo "2. API Performance Analysis:"
echo "   Testing different endpoint types..."

echo "   Station search (typically cached):"
time curl -s "http://localhost:8000/api/v1/stations/search?query=Marienplatz" > /dev/null

echo "   Route calculation (computationally intensive):"
time curl -s "http://localhost:8000/api/v1/route?from=Hauptbahnhof&to=Sendlinger%20Tor" > /dev/null

echo "   Large departure list (data transfer):"
time curl -s "http://localhost:8000/api/v1/departures?station=Hauptbahnhof&limit=50" > /dev/null

echo
echo "   Performance characteristics:"
echo "   - Cached responses: <50ms"
echo "   - API calls: 200-750ms (within SLA)"
echo "   - Large data transfers: 100-300ms"
echo

read -p "Press Enter to show monitoring best practices..."
```

## Demo 7: Monitoring Best Practices (5 minutes)

### Objective
Demonstrate monitoring best practices and observability patterns.

### Script

```bash
echo "🔧 Monitoring Best Practices"
echo "=========================="

echo "1. Key Metrics to Monitor:"
echo "   Open Grafana dashboard..."
open http://localhost:3001

echo "   Essential metrics:"
echo "   - Cache hit ratio (target: >70%)"
echo "   - API P95 latency (target: <750ms)"
echo "   - Error rate (target: <5/min)"
echo "   - Circuit breaker state"
echo "   - Resource utilization"
echo

echo "2. Alerting Patterns:"
echo "   Set up alerts for:"
echo "   - Cache hit ratio < 60%"
echo "   - API P95 latency > 1s"
echo "   - Error rate > 10/min"
echo "   - Circuit breaker activation"
echo "   - Database availability/latency (watch for sustained 5xx responses)"
echo

echo "3. Observability Strategy:"
echo "   - Metrics: Quantitative data (what's happening)"
echo "   - Tracing: Request flows (why it's happening)"
echo "   - Logging: Event details (context for issues)"
echo "   - Health checks: Service availability (can it serve traffic)"
echo

echo "4. Performance Optimization:"
echo "   - Monitor cache effectiveness"
echo "   - Identify database query bottlenecks"
echo "   - Track external API performance"
echo "   - Analyze resource utilization patterns"
echo

read -p "Press Enter for final summary..."
```

## Demo 8: Summary and Q&A (5 minutes)

### Objective
Recap key features and answer questions.

### Script

```bash
echo "🎯 Demo Summary"
echo "==============="

echo "Key Features Demonstrated:"
echo
echo "✅ High-Performance Backend"
echo "   - FastAPI with async SQLAlchemy"
echo "   - Valkey caching with stale fallbacks"
echo "   - Circuit breaker resilience patterns"
echo "   - Comprehensive error handling"
echo

echo "✅ Production-Ready Monitoring"
echo "   - Prometheus metrics collection"
echo "   - Grafana visualization dashboards"
echo "   - OpenTelemetry distributed tracing"
echo "   - Real-time performance monitoring"
echo

echo "✅ Chaos Engineering"
echo "   - Simulated failure scenarios"
echo "   - Graceful degradation testing"
echo "   - Resilience validation"
echo "   - Recovery testing"
echo

echo "✅ Developer Experience"
echo "   - Local development setup"
echo "   - Hot reload capabilities"
echo "   - Comprehensive observability"
echo "   - Debugging tooling"
echo

echo "Key Architectural Decisions:"
echo
echo "🏗️  Caching Strategy"
echo "   - Redis/Valkey for high-performance caching"
echo "   - Stale data fallbacks for resilience"
echo "   - Single-flight locking to prevent stampedes"
echo "   - TTL-based expiration for freshness"
echo

echo "🔒 Resilience Patterns"
echo "   - Circuit breakers for external dependencies"
echo "   - Graceful degradation vs. hard failures"
echo "   - Timeout handling for network operations"
echo "   - Retry logic with exponential backoff"
echo

echo "📊 Observability First"
echo "   - Metrics-driven development"
echo "   - End-to-end tracing"
echo "   - Structured logging"
echo "   - Real-time monitoring"
echo

echo "Next Steps:"
echo "1. Try the interactive chaos testing: ./scripts/chaos-scenarios.sh interactive"
echo "2. Explore the Grafana dashboards: http://localhost:3001"
echo "3. Check out the distributed traces: http://localhost:16686"
echo "4. Review the code structure and architecture"
echo "5. Deploy to Kubernetes using the provided manifests"
echo

echo "🙏 Thank you for your attention!"
echo "📧 Questions and Discussion"
```

## Reset Demo Environment

After completing the demo, reset the environment:

```bash
# Reset chaos scenarios
./scripts/chaos-scenarios.sh reset

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.demo.yml down

# Optional: Remove volumes to start fresh
docker compose -f docker-compose.yml -f docker-compose.demo.yml down -v
```

## Customization Tips

### Adjusting Demo Complexity

- **Simple demo**: Skip chaos testing, focus on monitoring
- **Technical demo**: Add code walkthrough, architecture discussion
- **Performance demo**: Generate more traffic, focus on metrics analysis
- **Resilience demo**: Spend more time on chaos scenarios

### Adding Custom Scenarios

Create new chaos scenarios in `scripts/chaos-scenarios.sh`:

```bash
scenario_custom_failure() {
    # Your custom failure scenario
    print_chaos "Custom scenario: ..."

    # Add your toxiproxy configuration
    curl -s -X POST "$TOXIPROXY_API/proxies/..." -d '...' > /dev/null
}
```

### Performance Benchmarking

For performance-focused demos, generate realistic load:

```bash
# Install hey (HTTP load generator)
go install github.com/rakyll/hey@latest

# Generate load
hey -n 100 -c 10 -m GET "http://localhost:8000/api/v1/departures?station=Hauptbahnhof"
```

## Troubleshooting Demos

### Common Issues

- **Services not healthy**: Check `docker compose ps` and wait longer
- **No traces in Jaeger**: Verify OTEL_ENABLED=true in environment
- **Chaos scenarios not working**: Ensure toxiproxy container is running
- **Metrics not updating**: Check Prometheus targets in web UI

### Recovery Commands

```bash
# Reset chaos scenarios
./scripts/chaos-scenarios.sh reset

# Restart specific services
docker compose restart backend

# Clear all data and restart fresh
docker compose -f docker-compose.yml -f docker-compose.demo.yml down -v
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
```
