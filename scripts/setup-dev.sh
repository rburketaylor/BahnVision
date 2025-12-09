#!/usr/bin/env bash
#
# setup-dev.sh — Bootstrap local development environment
#
# Downloads Node.js LTS and sets up Python venv for BahnVision development.
# Run from the repository root: ./scripts/setup-dev.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_DIR="$REPO_ROOT/.node"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Detect OS and architecture
detect_platform() {
    local os arch

    case "$(uname -s)" in
        Darwin) os="darwin" ;;
        Linux)  os="linux" ;;
        *)      error "Unsupported OS: $(uname -s)"; exit 1 ;;
    esac

    case "$(uname -m)" in
        x86_64)  arch="x64" ;;
        aarch64) arch="arm64" ;;
        arm64)   arch="arm64" ;;
        *)       error "Unsupported architecture: $(uname -m)"; exit 1 ;;
    esac

    echo "${os}-${arch}"
}

# Fetch the latest Node.js LTS version from nodejs.org
get_node_lts_version() {
    # Send info to stderr so it doesn't get captured in the variable
    echo -e "${BLUE}[INFO]${NC} Fetching latest Node.js LTS version..." >&2
    local version
    
    # The index.json has entries with "lts":"Codename" for LTS versions
    # and "lts":false for non-LTS. Find the first LTS entry.
    version=$(curl -fsSL https://nodejs.org/dist/index.json 2>/dev/null \
        | grep -o '"version":"v[0-9.]*"[^}]*"lts":"[A-Za-z]*"' \
        | head -1 \
        | grep -o '"version":"v[0-9.]*"' \
        | cut -d'"' -f4)

    if [[ -z "$version" ]]; then
        error "Failed to fetch Node.js LTS version"
        exit 1
    fi

    echo "$version"
}

# Install Node.js locally
install_node() {
    local platform version node_archive node_url node_extracted

    platform=$(detect_platform)
    version=$(get_node_lts_version)

    info "Installing Node.js $version for $platform..."

    # Check if already installed with same version
    if [[ -f "$NODE_DIR/version" ]]; then
        local installed_version
        installed_version=$(cat "$NODE_DIR/version")
        if [[ "$installed_version" == "$version" ]]; then
            success "Node.js $version already installed"
            return 0
        fi
        warn "Upgrading from $installed_version to $version"
        rm -rf "$NODE_DIR"
    fi

    mkdir -p "$NODE_DIR"

    node_archive="node-${version}-${platform}.tar.gz"
    node_url="https://nodejs.org/dist/${version}/${node_archive}"
    node_extracted="node-${version}-${platform}"

    info "Downloading from $node_url..."
    curl -fsSL "$node_url" -o "$NODE_DIR/$node_archive"

    info "Extracting..."
    tar -xzf "$NODE_DIR/$node_archive" -C "$NODE_DIR"
    rm "$NODE_DIR/$node_archive"

    # Move contents to NODE_DIR root for cleaner paths
    mv "$NODE_DIR/$node_extracted"/* "$NODE_DIR/"
    rmdir "$NODE_DIR/$node_extracted"

    # Record installed version
    echo "$version" > "$NODE_DIR/version"

    success "Node.js $version installed to $NODE_DIR"
}

# Set up Python virtual environment
setup_python_venv() {
    info "Setting up Python virtual environment..."

    local venv_path="$BACKEND_DIR/.venv"

    # Check Python version
    local python_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local py_version
            py_version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            local major minor
            major=$(echo "$py_version" | cut -d. -f1)
            minor=$(echo "$py_version" | cut -d. -f2)
            if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        error "Python 3.11+ is required but not found"
        exit 1
    fi

    info "Using $python_cmd ($("$python_cmd" --version))"

    # Create venv if it doesn't exist
    if [[ ! -d "$venv_path" ]]; then
        info "Creating virtual environment..."
        "$python_cmd" -m venv "$venv_path"
    else
        success "Virtual environment already exists"
    fi

    # Upgrade pip and install requirements
    info "Installing Python dependencies..."
    "$venv_path/bin/pip" install --quiet --upgrade pip
    "$venv_path/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt"

    success "Python environment ready at $venv_path"
}

# Install frontend dependencies
setup_frontend() {
    info "Setting up frontend dependencies..."

    export PATH="$NODE_DIR/bin:$PATH"

    if ! command -v npm &>/dev/null; then
        error "npm not found. Node.js installation may have failed."
        exit 1
    fi

    cd "$FRONTEND_DIR"
    npm install --silent

    success "Frontend dependencies installed"
}

# Install pre-commit hooks
setup_precommit() {
    info "Installing pre-commit hooks..."

    local venv_path="$BACKEND_DIR/.venv"

    if [[ -f "$REPO_ROOT/.pre-commit-config.yaml" ]]; then
        "$venv_path/bin/pre-commit" install --install-hooks
        success "Pre-commit hooks installed"
    else
        warn "No .pre-commit-config.yaml found, skipping"
    fi
}

# Generate activation helper script
generate_activate_script() {
    local activate_script="$REPO_ROOT/.dev-env"

    cat > "$activate_script" << 'EOF'
# Source this file to activate the dev environment:
#   source .dev-env
#
# This adds local Node.js and Python venv to your PATH.

_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Add local Node.js to PATH
if [[ -d "$_REPO_ROOT/.node/bin" ]]; then
    export PATH="$_REPO_ROOT/.node/bin:$PATH"
    echo "Node.js $(node --version) activated"
fi

# Activate Python venv
if [[ -f "$_REPO_ROOT/backend/.venv/bin/activate" ]]; then
    source "$_REPO_ROOT/backend/.venv/bin/activate"
    echo "Python venv activated ($(python --version))"
fi

unset _REPO_ROOT
EOF

    success "Created .dev-env activation script"
    info "Run 'source .dev-env' to activate the environment"
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "  BahnVision Development Environment Setup"
    echo "=========================================="
    echo ""

    cd "$REPO_ROOT"

    install_node
    setup_python_venv
    setup_frontend
    setup_precommit
    generate_activate_script

    echo ""
    success "Setup complete!"
    echo ""
    info "To activate the environment, run:"
    echo "    source .dev-env"
    echo ""
    info "Then start development servers:"
    echo "    # Backend:  cd backend && uvicorn app.main:app --reload"
    echo "    # Frontend: cd frontend && npm run dev"
    echo ""
}

main "$@"
