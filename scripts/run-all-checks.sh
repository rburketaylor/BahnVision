#!/usr/bin/env bash
#
# run-all-checks.sh — Run the complete test suite, linting, and type checks
#
# Runs all quality checks for both backend and frontend in one call.
# Exit codes are accumulated to report all failures at the end.
#
# Usage:
#   ./scripts/run-all-checks.sh           # Run all checks
#   ./scripts/run-all-checks.sh --no-e2e  # Skip Playwright E2E tests
#   ./scripts/run-all-checks.sh --quick   # Skip coverage and E2E (fast mode)
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
NODE_DIR="$REPO_ROOT/.node"
VENV_DIR="$BACKEND_DIR/.venv"

# Track overall exit status
EXIT_CODE=0
FAILED_CHECKS=()

# Parse arguments
SKIP_E2E=false
QUICK_MODE=false

for arg in "$@"; do
    case $arg in
        --no-e2e)
            SKIP_E2E=true
            ;;
        --quick)
            QUICK_MODE=true
            SKIP_E2E=true
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-e2e   Skip Playwright E2E tests"
            echo "  --quick    Quick mode: skip coverage and E2E tests"
            echo "  --help     Show this help message"
            exit 0
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Output helpers
header()  { echo -e "\n${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BOLD}${CYAN}  $*${NC}"; echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }
section() { echo -e "\n${BLUE}▶ $*${NC}"; }
success() { echo -e "${GREEN}✓ $*${NC}"; }
fail()    { echo -e "${RED}✗ $*${NC}"; }
info()    { echo -e "${YELLOW}ℹ $*${NC}"; }

# Run a check and track its result
run_check() {
    local name="$1"
    shift
    local cmd=("$@")
    
    section "$name"
    if "${cmd[@]}"; then
        success "$name passed"
        return 0
    else
        fail "$name failed"
        FAILED_CHECKS+=("$name")
        EXIT_CODE=1
        return 1
    fi
}

# Ensure environment is set up
check_environment() {
    header "Checking Environment"
    
    # Check Node.js
    if [[ -d "$NODE_DIR/bin" ]]; then
        export PATH="$NODE_DIR/bin:$PATH"
        info "Using local Node.js: $(node --version)"
    elif command -v node &>/dev/null; then
        info "Using system Node.js: $(node --version)"
    else
        fail "Node.js not found. Run ./scripts/setup-dev.sh first."
        exit 1
    fi
    
    # Check Python venv
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        source "$VENV_DIR/bin/activate"
        info "Using Python venv: $(python --version)"
    else
        fail "Python venv not found. Run ./scripts/setup-dev.sh first."
        exit 1
    fi
    
    success "Environment ready"
}

# ============================================================================
# BACKEND CHECKS
# ============================================================================

run_backend_checks() {
    header "Backend Checks"
    cd "$BACKEND_DIR"
    
    # Ruff format check (don't modify, just check)
    run_check "Backend: Ruff Format Check" \
        ruff format --check app tests
    
    # Ruff lint
    run_check "Backend: Ruff Lint" \
        ruff check app tests
    
    # MyPy type checking
    run_check "Backend: MyPy Type Check" \
        mypy app --ignore-missing-imports --no-error-summary
    
    # Pytest
    if [[ "$QUICK_MODE" == "true" ]]; then
        run_check "Backend: Pytest" \
            pytest tests -v --tb=short
    else
        run_check "Backend: Pytest with Coverage" \
            pytest tests -v --tb=short --cov=app --cov-report=term-missing
    fi
}

# ============================================================================
# FRONTEND CHECKS
# ============================================================================

run_frontend_checks() {
    header "Frontend Checks"
    cd "$FRONTEND_DIR"
    
    # ESLint + Prettier
    run_check "Frontend: ESLint + Prettier" \
        npm run lint
    
    # TypeScript type checking
    run_check "Frontend: TypeScript Type Check" \
        npm run type-check
    
    # Vitest unit tests
    if [[ "$QUICK_MODE" == "true" ]]; then
        run_check "Frontend: Vitest Unit Tests" \
            npm run test -- --run
    else
        run_check "Frontend: Vitest with Coverage" \
            npm run test:coverage
    fi
    
    # Playwright E2E tests (optional)
    if [[ "$SKIP_E2E" == "false" ]]; then
        run_check "Frontend: Playwright E2E Tests" \
            npm run test:e2e
    else
        info "Skipping E2E tests (--no-e2e or --quick)"
    fi
}

# ============================================================================
# ADDITIONAL CHECKS
# ============================================================================

run_additional_checks() {
    header "Additional Checks"
    cd "$REPO_ROOT"
    
    # Test quality check (assertions in tests)
    if [[ -f "$REPO_ROOT/scripts/check_test_quality.py" ]]; then
        run_check "Test Quality: Backend" \
            python "$REPO_ROOT/scripts/check_test_quality.py" "$BACKEND_DIR/tests"
        
        run_check "Test Quality: Frontend" \
            python "$REPO_ROOT/scripts/check_test_quality.py" "$FRONTEND_DIR/src"
    fi
}

# ============================================================================
# SUMMARY
# ============================================================================

print_summary() {
    header "Summary"
    
    if [[ ${#FAILED_CHECKS[@]} -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}"
        echo "  ╔═══════════════════════════════════════╗"
        echo "  ║   ✓ All checks passed successfully!   ║"
        echo "  ╚═══════════════════════════════════════╝"
        echo -e "${NC}"
    else
        echo -e "${RED}${BOLD}"
        echo "  ╔═══════════════════════════════════════╗"
        echo "  ║   ✗ Some checks failed                ║"
        echo "  ╚═══════════════════════════════════════╝"
        echo -e "${NC}"
        echo ""
        echo -e "${RED}Failed checks:${NC}"
        for check in "${FAILED_CHECKS[@]}"; do
            echo -e "  ${RED}•${NC} $check"
        done
    fi
    
    echo ""
    return $EXIT_CODE
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    echo ""
    echo -e "${BOLD}${BLUE}"
    echo "  ____        _          __     ___     _             "
    echo " | __ )  __ _| |__  _ __ \ \   / (_)___(_) ___  _ __  "
    echo " |  _ \ / _\` | '_ \| '_ \ \ \ / /| / __| |/ _ \| '_ \ "
    echo " | |_) | (_| | | | | | | | \ V / | \__ \ | (_) | | | |"
    echo " |____/ \__,_|_| |_|_| |_|  \_/  |_|___/_|\___/|_| |_|"
    echo ""
    echo "              Full Test Suite Runner"
    echo -e "${NC}"
    
    if [[ "$QUICK_MODE" == "true" ]]; then
        info "Running in quick mode (no coverage, no E2E)"
    fi
    
    check_environment
    run_backend_checks
    run_frontend_checks
    run_additional_checks
    print_summary
}

main "$@"
