#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check dependencies
check_dependencies() {
    print_status "Checking dependencies..."

    if ! command -v kind &> /dev/null; then
        print_error "kind is not installed. Please install kind first."
        echo "Visit: https://kind.sigs.k8s.io/docs/user/quick-start/"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        echo "Visit: https://kubernetes.io/docs/tasks/tools/"
        exit 1
    fi

    print_status "Dependencies found: kind, kubectl"
}

# Create kind cluster
create_cluster() {
    print_status "Creating kind cluster..."

    if kind get clusters | grep -q "bahnvision-cluster"; then
        print_warning "Cluster 'bahnvision-cluster' already exists. Deleting it first..."
        kind delete cluster --name bahnvision-cluster
    fi

    kind create cluster --config examples/k8s/kind-config.yaml --wait 300s
    print_status "Kind cluster created successfully"
}

# Install ingress-nginx
install_ingress() {
    print_status "Installing ingress-nginx..."

    # Add the ingress-nginx repository
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

    # Wait for the ingress controller to be ready
    print_status "Waiting for ingress-nginx to be ready..."
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s

    print_status "ingress-nginx is ready"
}

# Install ArgoCD
install_argocd() {
    print_status "Installing ArgoCD..."

    # Create the argocd namespace
    kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

    # Install ArgoCD using the official manifest
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

    # Wait for ArgoCD to be ready
    print_status "Waiting for ArgoCD to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-repo-server -n argocd
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-application-controller -n argocd
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-dex-server -n argocd

    print_status "ArgoCD is ready"
}

# Apply application manifests
apply_app_manifests() {
    print_status "Applying BahnVision application manifests..."

    # Apply all manifests in examples/k8s directory except argocd and kind-config
    for manifest in examples/k8s/*.yaml; do
        if [[ "$manifest" != *"argocd"* ]] && [[ "$manifest" != *"kind-config"* ]]; then
            print_status "Applying $manifest"
            kubectl apply -f "$manifest"
        fi
    done

    print_status "Application manifests applied"
}

# Wait for application pods to be ready
wait_for_app_pods() {
    print_status "Waiting for application pods to be ready..."

    # Wait for deployments to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/bahnvision-backend
    kubectl wait --for=condition=available --timeout=300s deployment/bahnvision-frontend

    # Wait for statefulsets to be ready
    kubectl wait --for=condition=ready --timeout=300s pod/bahnvision-postgres-0
    kubectl wait --for=condition=ready --timeout=300s pod/bahnvision-valkey-0

    print_status "Application pods are ready"
}

# Print access information
print_access_info() {
    print_status "Cluster setup complete!"
    echo
    echo "Access Information:"
    echo "=================="
    echo "Kubernetes cluster: kind bahnvision-cluster"
    echo "Kubernetes context: kind-bahnvision-cluster"
    echo
    echo "Applications:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend API: http://localhost:8000"
    echo "  Ingress (HTTP): http://localhost"
    echo "  Ingress (HTTPS): https://localhost"
    echo
    echo "ArgoCD:"
    echo "  URL: http://localhost:8080"
    echo "  Username: admin"
    echo "  Password: (run 'kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath={.data.password} | base64 -d')"
    echo
    echo "Useful commands:"
    echo "  kubectl get pods"
    echo "  kubectl get svc"
    echo "  kubectl get ingress"
    echo "  kubectl port-forward svc/argocd-server 8080:443 -n argocd"
}

# Main execution
main() {
    print_status "Setting up BahnVision Kubernetes cluster with kind..."

    # Change to project root directory
    cd "$(dirname "$0")/.."

    check_dependencies
    create_cluster
    install_ingress
    install_argocd
    apply_app_manifests
    wait_for_app_pods
    print_access_info
}

# Handle script interruption
trap 'print_error "Script interrupted"; exit 1' INT TERM

# Run main function
main "$@"