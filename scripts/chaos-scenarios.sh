#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Toxiproxy API endpoint
TOXIPROXY_API="http://localhost:8474"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_chaos() {
    echo -e "${BLUE}[CHAOS]${NC} $1"
}

# Check if Toxiproxy is running
check_toxiproxy() {
    print_status "Checking Toxiproxy connectivity..."
    if ! curl -s "$TOXIPROXY_API/version" > /dev/null; then
        print_error "Toxiproxy is not running at $TOXIPROXY_API"
        print_status "Start the demo environment first: docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d"
        exit 1
    fi
    print_status "Toxiproxy is running"
}

# Reset all proxies to clean state
reset_proxies() {
    print_status "Resetting all proxies to clean state..."
    curl -s -X POST "$TOXIPROXY_API/reset" > /dev/null || true

    print_status "All proxies reset to clean state"
}

# Scenario 1: Add latency to PostgreSQL
scenario_postgres_latency() {
    local latency_ms=${1:-1000}
    print_chaos "Scenario: Adding ${latency_ms}ms latency to PostgreSQL connection"

    curl -s -X POST "$TOXIPROXY_API/proxies/postgres_proxy/toxics" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"postgres_latency\",
            \"type\": \"latency\",
            \"stream\": \"downstream\",
            \"attributes\": {
                \"latency\": ${latency_ms},
                \"jitter\": 0
            }
        }" > /dev/null

    print_status "PostgreSQL latency injection applied (${latency_ms}ms)"
    print_warning "Expect slower API response times and potential timeout errors"
}

# Scenario 2: Add latency to Valkey
scenario_valkey_latency() {
    local latency_ms=${1:-500}
    print_chaos "Scenario: Adding ${latency_ms}ms latency to Valkey connection"

    curl -s -X POST "$TOXIPROXY_API/proxies/valkey_proxy/toxics" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"valkey_latency\",
            \"type\": \"latency\",
            \"stream\": \"downstream\",
            \"attributes\": {
                \"latency\": ${latency_ms},
                \"jitter\": 0
            }
        }" > /dev/null

    print_status "Valkey latency injection applied (${latency_ms}ms)"
    print_warning "Expect cache miss behavior and slower cache operations"
}

# Scenario 3: Simulate PostgreSQL connection failures
scenario_postgres_failures() {
    local failure_rate=${1:-0.3}  # 30% failure rate
    local percent
    percent=$(awk -v r="$failure_rate" 'BEGIN{printf "%.0f", r*100}')
    print_chaos "Scenario: Simulating ${percent}% PostgreSQL connection failures"

    curl -s -X POST "$TOXIPROXY_API/proxies/postgres_proxy/toxics" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"postgres_timeout\",
            \"type\": \"timeout\",
            \"stream\": \"downstream\",
            \"attributes\": {
                \"timeout\": 1000
            },
            \"toxicity\": ${failure_rate}
        }" > /dev/null

    print_status "PostgreSQL failure injection applied (${percent}% failure rate)"
    print_warning "Expect database errors and circuit breaker activation"
}

# Scenario 4: Simulate Valkey connection failures
scenario_valkey_failures() {
    local failure_rate=${1:-0.5}  # 50% failure rate
    local percent
    percent=$(awk -v r="$failure_rate" 'BEGIN{printf "%.0f", r*100}')
    print_chaos "Scenario: Simulating ${percent}% Valkey connection failures"

    curl -s -X POST "$TOXIPROXY_API/proxies/valkey_proxy/toxics" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"valkey_timeout\",
            \"type\": \"timeout\",
            \"stream\": \"downstream\",
            \"attributes\": {
                \"timeout\": 1000
            },
            \"toxicity\": ${failure_rate}
        }" > /dev/null

    print_status "Valkey failure injection applied (${percent}% failure rate)"
    print_warning "Expect cache fallback behavior and stale cache usage"
}

# Scenario 5: Complete PostgreSQL outage
scenario_postgres_outage() {
    print_chaos "Scenario: Complete PostgreSQL outage (disable proxy)"

    curl -s -X POST "$TOXIPROXY_API/proxies/postgres_proxy" -d '{"enabled": false}' > /dev/null

    print_status "PostgreSQL connection severed"
    print_warning "Expect complete database unavailability and service degradation"
}

# Scenario 6: Complete Valkey outage
scenario_valkey_outage() {
    print_chaos "Scenario: Complete Valkey outage (disable proxy)"

    curl -s -X POST "$TOXIPROXY_API/proxies/valkey_proxy" -d '{"enabled": false}' > /dev/null

    print_status "Valkey connection severed"
    print_warning "Expect cache bypass behavior and increased upstream API calls"
}

# Scenario 7: Bandwidth limitation (slow connection)
scenario_bandwidth_limit() {
    local throughput=${1:-1000}  # 1KB/s
    print_chaos "Scenario: Limiting bandwidth to ${throughput} bytes/second"

    # Apply to both proxies
    for proxy in postgres_proxy valkey_proxy; do
        curl -s -X POST "$TOXIPROXY_API/proxies/$proxy/toxics" \
            -H "Content-Type: application/json" \
            -d "{
                \"name\": \"${proxy}_bandwidth\",
                \"type\": \"bandwidth\",
                \"stream\": \"downstream\",
                \"attributes\": {
                    \"rate\": ${throughput}
                }
            }" > /dev/null
    done

    print_status "Bandwidth limitation applied (${throughput} bytes/s)"
    print_warning "Expect slow data transfer and potential timeouts"
}

# Scenario 8: Slow read/close timeout
scenario_slow_close() {
    local timeout_ms=${1:-5000}
    print_chaos "Scenario: Adding ${timeout_ms}ms timeout to slow reads"

    for proxy in postgres_proxy valkey_proxy; do
        curl -s -X POST "$TOXIPROXY_API/proxies/$proxy/toxics" \
            -H "Content-Type: application/json" \
            -d "{
                \"name\": \"${proxy}_slow_close\",
                \"type\": \"slow_close\",
                \"stream\": \"downstream\",
                \"attributes\": {
                    \"delay\": ${timeout_ms}
                }
            }" > /dev/null
    done

    print_status "Slow read timeout applied (${timeout_ms}ms)"
    print_warning "Expect connection timeout behavior"
}

# Show current proxy status
show_status() {
    print_status "Current Toxiproxy status:"
    echo

    for proxy in postgres_proxy valkey_proxy; do
        echo "=== $proxy ==="
        proxy_info=$(curl -s "$TOXIPROXY_API/proxies/$proxy")

        enabled=$(echo "$proxy_info" | jq -r '.enabled')
        name=$(echo "$proxy_info" | jq -r '.name')
        upstream=$(echo "$proxy_info" | jq -r '.upstream')
        downstream=$(echo "$proxy_info" | jq -r '.downstream')

        echo "Enabled: $enabled"
        echo "Upstream: $upstream"
        echo "Downstream: $downstream"

        # Show active toxics
        toxics=$(curl -s "$TOXIPROXY_API/proxies/$proxy/toxics")
        if echo "$toxics" | jq -e '. | length > 0' > /dev/null; then
            echo "Active toxics:"
            echo "$toxics" | jq -r '.[] | "  - \(.type): \(.attributes | to_entries[] | select(.key != "stream") | "\(.key)=\(.value)")"'
        else
            echo "No active toxics"
        fi
        echo
    done
}

# Interactive mode
interactive_mode() {
    while true; do
        echo
        print_status "Chaos Testing Interactive Mode"
        echo "0) Show current status"
        echo "1) Reset all proxies"
        echo "2) PostgreSQL latency (1000ms)"
        echo "3) Valkey latency (500ms)"
        echo "4) PostgreSQL failures (30%)"
        echo "5) Valkey failures (50%)"
        echo "6) PostgreSQL outage"
        echo "7) Valkey outage"
        echo "8) Bandwidth limit (1KB/s)"
        echo "9) Slow close timeout (5s)"
        echo "q) Quit"
        echo -n "Select an option: "

        read -r choice
        case $choice in
            0) show_status ;;
            1) reset_proxies ;;
            2) scenario_postgres_latency ;;
            3) scenario_valkey_latency ;;
            4) scenario_postgres_failures ;;
            5) scenario_valkey_failures ;;
            6) scenario_postgres_outage ;;
            7) scenario_valkey_outage ;;
            8) scenario_bandwidth_limit ;;
            9) scenario_slow_close ;;
            q|Q) break ;;
            *) print_warning "Invalid option" ;;
        esac
    done
}

# Show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  status                    Show current proxy status"
    echo "  reset                     Reset all proxies to clean state"
    echo "  postgres-latency [MS]     Add latency to PostgreSQL (default: 1000ms)"
    echo "  valkey-latency [MS]       Add latency to Valkey (default: 500ms)"
    echo "  postgres-failures [RATE]  Add failures to PostgreSQL (default: 0.3)"
    echo "  valkey-failures [RATE]    Add failures to Valkey (default: 0.5)"
    echo "  postgres-outage           Complete PostgreSQL outage"
    echo "  valkey-outage             Complete Valkey outage"
    echo "  bandwidth-limit [RATE]    Limit bandwidth (default: 1000 bytes/s)"
    echo "  slow-close [MS]           Add slow close timeout (default: 5000ms)"
    echo "  interactive               Interactive chaos testing mode"
    echo "  help                      Show this help message"
    echo
    echo "Examples:"
    echo "  $0 reset                    # Reset everything"
    echo "  $0 postgres-latency 2000    # Add 2s latency to PostgreSQL"
    echo "  $0 interactive              # Enter interactive mode"
}

# Main execution
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi

    check_toxiproxy

    case "${1:-}" in
        status)
            show_status
            ;;
        reset)
            reset_proxies
            ;;
        postgres-latency)
            reset_proxies
            scenario_postgres_latency "${2:-1000}"
            ;;
        valkey-latency)
            reset_proxies
            scenario_valkey_latency "${2:-500}"
            ;;
        postgres-failures)
            reset_proxies
            scenario_postgres_failures "${2:-0.3}"
            ;;
        valkey-failures)
            reset_proxies
            scenario_valkey_failures "${2:-0.5}"
            ;;
        postgres-outage)
            reset_proxies
            scenario_postgres_outage
            ;;
        valkey-outage)
            reset_proxies
            scenario_valkey_outage
            ;;
        bandwidth-limit)
            reset_proxies
            scenario_bandwidth_limit "${2:-1000}"
            ;;
        slow-close)
            reset_proxies
            scenario_slow_close "${2:-5000}"
            ;;
        interactive)
            interactive_mode
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Check dependencies
if ! command -v curl &> /dev/null; then
    print_error "curl is required but not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    print_error "jq is required but not installed"
    exit 1
fi

# Run main function
main "$@"
