#!/bin/bash
# =============================================================================
# cvgorod-hub Production Deploy Script
# =============================================================================
# Deploy with automatic backup and health checks
# Usage: ./deploy/deploy-prod.sh [--no-backup]
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/badygovdaniil/cvgorod-hub"
BACKUP_DIR="/home/badygovdaniil/.backups/cvgorod-hub"
SERVICE_NAME="cvgorod-hub"
SERVER="158.160.153.14"
SSH_KEY="~/.ssh/yandex_vm_key"

# Parse arguments
SKIP_BACKUP=false
for arg in "$@"; do
    case $arg in
        --no-backup)
            SKIP_BACKUP=true
            shift
            ;;
    esac
done

echo_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Pre-flight checks
# =============================================================================

echo_step "Starting deployment of cvgorod-hub..."

# Check if we're in the right directory
if [[ ! -f "main.py" ]] || [[ ! -f "docker-compose.yml" ]]; then
    echo_error "Not in cvgorod-hub project directory!"
    echo_error "Expected to find main.py and docker-compose.yml"
    exit 1
fi

# Check for uncommitted changes
if [[ -n "$(git status --porcelain)" ]]; then
    echo_warn "You have uncommitted changes:"
    git status --short
    echo_warn "Consider committing before deployment"
fi

# =============================================================================
# Backup (if not skipped)
# =============================================================================

if [[ "$SKIP_BACKUP" == "false" ]]; then
    echo_step "Creating backup..."

    # Create backup directory with timestamp
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"

    # Create archive
    tar -czf "$BACKUP_DIR/cvgorod-hub-backup-$TIMESTAMP.tar.gz" \
        --exclude='.git' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='.pytest_cache' \
        --exclude='logs' \
        --exclude='data' \
        --exclude='backups' \
        --exclude='node_modules' \
        -C "$PROJECT_DIR" .

    echo -e "${GREEN}[OK]${NC} Backup created: $BACKUP_DIR/cvgorod-hub-backup-$TIMESTAMP.tar.gz"

    # Keep only last 10 backups
    ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm
    echo -e "${GREEN}[OK]${NC} Old backups cleaned up"
else
    echo_warn "Skipping backup (--no-backup flag)"
fi

# =============================================================================
# Run tests
# =============================================================================

echo_step "Running tests..."
if python3 -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/test_output.txt; then
    echo -e "${GREEN}[OK]${NC} All tests passed"
else
    echo_error "Tests failed!"
    cat /tmp/test_output.txt
    exit 1
fi

# =============================================================================
# Deploy via SSH
# =============================================================================

echo_step "Deploying to server..."

# Build and deploy using docker compose
ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
    cd $PROJECT_DIR

    # Pull latest changes
    git pull origin main 2>/dev/null || echo 'No git changes to pull'

    # Copy environment file if exists
    if [[ -f .env.prod ]]; then
        cp .env.prod .env
    fi

    # Build and restart services
    docker compose down --remove-orphans
    docker compose build --no-cache
    docker compose up -d

    # Wait for service to be healthy
    echo 'Waiting for service to start...'
    for i in {1..30}; do
        if curl -sf http://127.0.0.1:8300/health > /dev/null 2>&1; then
            echo 'Service is healthy!'
            exit 0
        fi
        sleep 2
    done

    echo 'Service health check failed!'
    exit 1
"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}[OK]${NC} Deployment successful!"
else
    echo_error "Deployment failed!"
    echo_step "Rolling back..."

    # Rollback to previous version
    ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
        cd $PROJECT_DIR
        docker compose down
        docker compose up -d
    "

    echo_warn "Rolled back to previous version"
    exit 1
fi

# =============================================================================
# Final verification
# =============================================================================

echo_step "Final verification..."

# Check service status
STATUS=$(ssh -i "$SSH_KEY" badygovdaniil@$SERVER "systemctl is-active $SERVICE_NAME" 2>/dev/null || echo "unknown")
if [[ "$STATUS" == "active" ]]; then
    echo -e "${GREEN}[OK]${NC} Service is active"
else
    echo_warn "Service status: $STATUS"
fi

# Check health endpoint
HEALTH=$(ssh -i "$SSH_KEY" badygovdaniil@$SERVER "curl -sf http://127.0.0.1:8300/health 2>/dev/null" || echo "{}")
if echo "$HEALTH" | grep -q '"status": "ok"'; then
    echo -e "${GREEN}[OK]${NC} Health check passed"
else
    echo_warn "Health check response: $HEALTH"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Service URL: http://158.160.153.14:8300"
echo "Health check: http://158.160.153.14:8300/health"
echo ""
