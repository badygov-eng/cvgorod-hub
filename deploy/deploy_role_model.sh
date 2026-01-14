#!/bin/bash
# =============================================================================
# Deployment script for cvgorod-hub role model update
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== cvgorod-hub Deployment Script ===${NC}"
echo "Date: $(date)"
echo ""

# Configuration
PROJECT_DIR="~/cvgorod-hub"
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-cvgorod_hub}"
DB_USER="${DB_USER:-cvgorod}"
MIGRATION_FILE="$PROJECT_DIR/scripts/migrate_add_roles.sql"

# =============================================================================
# STEP 1: Backup Database
# =============================================================================
echo -e "${YELLOW}Step 1: Backing up database...${NC}"

if [ -n "$DB_PASSWORD" ]; then
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -f "backups/backup_pre_role_model_$(date +%Y%m%d_%H%M%S).sql" \
        --verbose
else
    echo -e "${RED}Error: DB_PASSWORD not set${NC}"
    exit 1
fi

echo -e "${GREEN}Backup completed!${NC}"
echo ""

# =============================================================================
# STEP 2: Apply Migration
# =============================================================================
echo -e "${YELLOW}Step 2: Applying database migration...${NC}"

if [ -n "$DB_PASSWORD" ]; then
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -f "$MIGRATION_FILE" \
        --verbose \
        2>&1 | tee "logs/migration_output_$(date +%Y%m%d_%H%M%S).log"
else
    echo -e "${RED}Error: DB_PASSWORD not set${NC}"
    exit 1
fi

echo -e "${GREEN}Migration applied!${NC}"
echo ""

# =============================================================================
# STEP 3: Verify Migration
# =============================================================================
echo -e "${YELLOW}Step 3: Verifying migration...${NC}"

VERIFY_QUERY="
SELECT 
    COUNT(*) FILTER (WHERE role IS NOT NULL) as messages_with_role,
    COUNT(*) FILTER (WHERE role IS NULL) as messages_without_role
FROM messages;
"

VERIFY_RESULT=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -t \
    -c "$VERIFY_QUERY")

echo "Messages with role: $(echo $VERIFY_RESULT | awk '{print $1}')"
echo "Messages without role: $(echo $VERIFY_RESULT | awk '{print $2}')"

if [ "$(echo $VERIFY_RESULT | awk '{print $2}')" -gt 0 ]; then
    echo -e "${YELLOW}Warning: Some messages still don't have role assigned${NC}"
fi

echo ""

# =============================================================================
# STEP 4: Build and Deploy API
# =============================================================================
echo -e "${YELLOW}Step 4: Building and deploying API...${NC}"

cd "$PROJECT_DIR"

# Build Docker image
echo "Building Docker image..."
docker build -t cvgorod-hub:latest .

# Stop old container
echo "Stopping old container..."
docker stop cvgorod-hub 2>/dev/null || true
docker rm cvgorod-hub 2>/dev/null || true

# Start new container
echo "Starting new container..."
docker run -d \
    --name cvgorod-hub \
    -p 8300:8300 \
    -e DATABASE_URL="$DATABASE_URL" \
    -e HUB_API_KEY="$HUB_API_KEY" \
    --restart unless-stopped \
    cvgorod-hub:latest

echo -e "${GREEN}API deployed!${NC}"
echo ""

# =============================================================================
# STEP 5: Health Check
# =============================================================================
echo -e "${YELLOW}Step 5: Health check...${NC}"

sleep 5

HEALTH_RESPONSE=$(curl -s http://localhost:8300/health)
echo "Health response: $HEALTH_RESPONSE"

if echo "$HEALTH_RESPONSE" | grep -q "ok"; then
    echo -e "${GREEN}Service is healthy!${NC}"
else
    echo -e "${RED}Warning: Health check failed${NC}"
fi

echo ""

# =============================================================================
# STEP 6: Run Tests (Optional)
# =============================================================================
echo -e "${YELLOW}Step 6: Running tests...${NC}"

cd "$PROJECT_DIR"
python -m pytest tests/ -v --tb=short 2>&1 | tee "logs/tests_output_$(date +%Y%m%d_%H%M%S).log"

echo -e "${GREEN}Tests completed!${NC}"
echo ""

# =============================================================================
# SUMMARY
# =============================================================================
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Summary:"
echo "  - Database backup: DONE"
echo "  - Migration applied: DONE"
echo "  - API deployed: DONE"
echo "  - Health check: DONE"
echo ""
echo "New API endpoints available:"
echo "  - GET /api/v1/users - List users with role filter"
echo "  - GET /api/v1/users/managers - List managers"
echo "  - GET /api/v1/users/{id}/statistics - User statistics"
echo "  - PATCH /api/v1/users/{id}/role - Update user role"
echo "  - GET /api/v1/messages?role=CLIENT - Filter messages by role"
echo "  - GET /api/v1/messages/stats/by-role - Stats by role"
echo "  - GET /api/v1/analytics/conversations - Conversation analytics"
echo "  - GET /api/v1/mailings - List mailing campaigns"
echo "  - GET /api/v1/chats/{id}/participants - Chat participants with roles"
echo ""
echo "Migration log: logs/migration_output_*.log"
echo "Tests log: logs/tests_output_*.log"
