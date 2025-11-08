#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

print_security() {
    echo -e "${BLUE}[SECURITY]${NC} $1"
}

# Check dependencies
check_dependencies() {
    local missing_deps=()

    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi

    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi

    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        echo "Please install the missing tools and try again."
        exit 1
    fi

    print_status "All dependencies found"
}

# Backend security scanning
scan_backend() {
    print_security "Scanning backend security..."

    # Install security tools if not present
    python3 -m pip install --quiet bandit safety semgrep 2>/dev/null || true

    # Run Bandit (Python security linter)
    print_security "Running Bandit security linter..."
    if bandit -r backend/app -f json -o bandit-report.json 2>/dev/null; then
        print_status "Bandit scan completed successfully"
    else
        print_warning "Bandit found security issues"
    fi

    # Run Safety (dependency vulnerability scanner)
    print_security "Running Safety dependency scanner..."
    if safety check --json --output safety-report.json 2>/dev/null; then
        print_status "Safety scan completed successfully"
    else
        print_warning "Safety found vulnerable dependencies"
    fi

    # Run Semgrep (SAST)
    print_security "Running Semgrep static analysis..."
    if semgrep --config=auto --json --output=semgrep-report.json backend/app 2>/dev/null; then
        print_status "Semgrep scan completed successfully"
    else
        print_warning "Semgrep found security issues"
    fi
}

# Frontend security scanning
scan_frontend() {
    print_security "Scanning frontend security..."

    cd frontend

    # Run npm audit
    print_security "Running npm audit..."
    if npm audit --json > ../npm-audit.json 2>/dev/null; then
        print_status "npm audit completed"
    else
        print_warning "npm audit found vulnerabilities"
    fi

    # Run npm audit fix (automated fixes)
    print_security "Attempting to fix vulnerabilities automatically..."
    npm audit fix || print_warning "Some vulnerabilities could not be fixed automatically"

    cd ..
}

# Container image scanning
scan_containers() {
    print_security "Scanning container images..."

    # Check if Trivy is available
    if ! command -v trivy &> /dev/null; then
        print_warning "Trivy not found. Installing..."
        sudo apt-get update && sudo apt-get install wget apt-transport-https gnupg lsb-release
        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
        echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
        sudo apt-get update
        sudo apt-get install trivy
    fi

    # Build images if they don't exist
    print_status "Building container images..."
    docker build -t bahnvision-backend:test -f backend/Dockerfile . || true
    docker build -t bahnvision-frontend:test -f frontend/Dockerfile frontend/ || true

    # Scan backend image
    print_security "Scanning backend image with Trivy..."
    if trivy image --format json --output backend-trivy.json bahnvision-backend:test 2>/dev/null; then
        print_status "Backend image scan completed"
    else
        print_warning "Backend image has vulnerabilities"
    fi

    # Scan frontend image
    print_security "Scanning frontend image with Trivy..."
    if trivy image --format json --output frontend-trivy.json bahnvision-frontend:test 2>/dev/null; then
        print_status "Frontend image scan completed"
    else
        print_warning "Frontend image has vulnerabilities"
    fi
}

# Infrastructure security scanning
scan_infrastructure() {
    print_security "Scanning infrastructure security..."

    # Check for hardcoded secrets
    print_security "Scanning for hardcoded secrets..."
    if command -v trufflehog &> /dev/null; then
        trufflehog --json --output=secrets-report.json . 2>/dev/null || true
    else
        print_warning "TruffleHog not found, skipping secret scanning"
    fi

    # Check Kubernetes manifests for security issues
    print_security "Scanning Kubernetes manifests..."
    if command -v kube-score &> /dev/null; then
        kube-score score k8s/*.yaml --output-format ci > kube-score-report.txt 2>/dev/null || true
    else
        print_warning "kube-score not found, skipping Kubernetes security scanning"
    fi

    # Check Dockerfiles for security issues
    print_security "Scanning Dockerfiles..."
    if command -v hadolint &> /dev/null; then
        hadolint backend/Dockerfile > dockerfile-lint.txt 2>/dev/null || true
        hadolint frontend/Dockerfile >> dockerfile-lint.txt 2>/dev/null || true
    else
        print_warning "hadolint not found, skipping Dockerfile linting"
    fi
}

# Generate security report
generate_report() {
    print_status "Generating security report..."

    cat > security-report.md << EOF
# BahnVision Security Scan Report

**Generated on:** $(date)
**Scanner version:** $(bash --version | head -n1)

## Executive Summary

EOF

    # Count issues from each scanner
    if [ -f "bandit-report.json" ]; then
        local bandit_issues=$(jq '.results | length' bandit-report.json 2>/dev/null || echo "0")
        echo "- Bandit (Python): $bandit_issues issues found" >> security-report.md
    fi

    if [ -f "safety-report.json" ]; then
        local safety_issues=$(jq '.vulnerabilities | length' safety-report.json 2>/dev/null || echo "0")
        echo "- Safety (Dependencies): $safety_issues vulnerabilities found" >> security-report.md
    fi

    if [ -f "npm-audit.json" ]; then
        local npm_issues=$(jq '.vulnerabilities | length' npm-audit.json 2>/dev/null || echo "0")
        echo "- npm audit (Frontend): $npm_issues vulnerabilities found" >> security-report.md
    fi

    if [ -f "backend-trivy.json" ]; then
        local backend_vulns=$(jq '.Results[]?.Vulnerabilities? | length // 0' backend-trivy.json 2>/dev/null | awk '{sum+=$1} END {print sum}')
        echo "- Trivy (Backend image): $backend_vulns vulnerabilities found" >> security-report.md
    fi

    if [ -f "frontend-trivy.json" ]; then
        local frontend_vulns=$(jq '.Results[]?.Vulnerabilities? | length // 0' frontend-trivy.json 2>/dev/null | awk '{sum+=$1} END {print sum}')
        echo "- Trivy (Frontend image): $frontend_vulns vulnerabilities found" >> security-report.md
    fi

    cat >> security-report.md << EOF

## Detailed Findings

### Backend Security (Bandit)
EOF

    if [ -f "bandit-report.json" ]; then
        echo '```json' >> security-report.md
        cat bandit-report.json >> security-report.md
        echo '```' >> security-report.md
    else
        echo "No Bandit report generated." >> security-report.md
    fi

    cat >> security-report.md << EOF

### Dependency Security (Safety)
EOF

    if [ -f "safety-report.json" ]; then
        echo '```json' >> security-report.md
        cat safety-report.json >> security-report.md
        echo '```' >> security-report.md
    else
        echo "No Safety report generated." >> security-report.md
    fi

    cat >> security-report.md << EOF

### Frontend Security (npm audit)
EOF

    if [ -f "npm-audit.json" ]; then
        echo '```json' >> security-report.md
        cat npm-audit.json >> security-report.md
        echo '```' >> security-report.md
    else
        echo "No npm audit report generated." >> security-report.md
    fi

    cat >> security-report.md << EOF

### Container Security (Trivy)
EOF

    if [ -f "backend-trivy.json" ]; then
        echo -e "\n#### Backend Image\n\`\`\`json" >> security-report.md
        cat backend-trivy.json >> security-report.md
        echo '```' >> security-report.md
    fi

    if [ -f "frontend-trivy.json" ]; then
        echo -e "\n#### Frontend Image\n\`\`\`json" >> security-report.md
        cat frontend-trivy.json >> security-report.md
        echo '```' >> security-report.md
    fi

    cat >> security-report.md << EOF

## Recommendations

1. **High Priority Issues**
   - Review and fix any CRITICAL or HIGH severity vulnerabilities
   - Update dependencies to secure versions
   - Address hardcoded credentials or secrets

2. **Medium Priority Issues**
   - Review security best practices in code
   - Implement secure coding guidelines
   - Regular dependency updates

3. **Low Priority Issues**
   - Code quality improvements
   - Documentation enhancements
   - Configuration hardening

## Next Steps

1. Review all findings in detail
2. Create tickets for high-priority issues
3. Update dependencies to secure versions
4. Implement security best practices
5. Set up regular scanning in CI/CD pipeline

---

*This report was generated automatically. Please review findings manually for context and impact assessment.*
EOF

    print_status "Security report generated: security-report.md"
}

# Clean up function
cleanup() {
    print_status "Cleaning up temporary files..."
    rm -f bandit-report.json safety-report.json npm-audit.json semgrep-report.json
    rm -f backend-trivy.json frontend-trivy.json secrets-report.json
    print_status "Cleanup completed"
}

# Show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  backend        Scan backend code only"
    echo "  frontend       Scan frontend code only"
    echo "  containers     Scan container images only"
    echo "  infrastructure Scan infrastructure files only"
    echo "  all            Run all scans (default)"
    echo "  report         Generate comprehensive report"
    echo "  cleanup        Clean up temporary files"
    echo "  help           Show this help message"
    echo
    echo "Examples:"
    echo "  $0                    # Run all security scans"
    echo "  $0 backend           # Scan backend only"
    echo "  $0 report            # Generate report only"
}

# Main execution
main() {
    local command="${1:-all}"

    case "$command" in
        backend)
            check_dependencies
            scan_backend
            ;;
        frontend)
            check_dependencies
            scan_frontend
            ;;
        containers)
            check_dependencies
            scan_containers
            ;;
        infrastructure)
            check_dependencies
            scan_infrastructure
            ;;
        all)
            check_dependencies
            scan_backend
            scan_frontend
            scan_containers
            scan_infrastructure
            generate_report
            ;;
        report)
            generate_report
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac

    if [ "$command" != "cleanup" ] && [ "$command" != "help" ]; then
        print_status "Security scan completed!"
        print_status "Review the generated reports for detailed findings:"
        print_status "  - security-report.md (comprehensive report)"
        [ -f "bandit-report.json" ] && print_status "  - bandit-report.json (Python security)"
        [ -f "safety-report.json" ] && print_status "  - safety-report.json (Dependency vulnerabilities)"
        [ -f "npm-audit.json" ] && print_status "  - npm-audit.json (Node.js vulnerabilities)"
        [ -f "backend-trivy.json" ] && print_status "  - backend-trivy.json (Container security)"
        [ -f "frontend-trivy.json" ] && print_status "  - frontend-trivy.json (Container security)"
    fi
}

# Handle script interruption
trap 'print_error "Script interrupted"; cleanup; exit 1' INT TERM

# Run main function
main "$@"