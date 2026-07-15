#!/bin/bash
# ============================================================
# AMASCI - Health Check & Monitoring Script
# Checks all services and reports status
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"
NGINX_URL="${NGINX_URL:-http://localhost:80}"
NEO4J_URL="${NEO4J_URL:-http://localhost:7474}"

REPORT_FILE="/tmp/amasci-health-$(date +%Y%m%d-%H%M%S).json"

check_service() {
    local name=$1
    local url=$2
    local start_time=$(date +%s%N)

    if response=$(curl -sf -o /dev/null -w "%{http_code}|%{time_total}" "$url" 2>/dev/null); then
        local http_code=$(echo "$response" | cut -d'|' -f1)
        local response_time=$(echo "$response" | cut -d'|' -f2)
        echo -e "${GREEN}✓${NC} $name: HTTP $http_code (${response_time}s)"
        echo "{\"service\":\"$name\",\"status\":\"healthy\",\"code\":$http_code,\"response_time\":$response_time}"
    else
        echo -e "${RED}✗${NC} $name: UNREACHABLE"
        echo "{\"service\":\"$name\",\"status\":\"down\",\"code\":0,\"response_time\":0}"
    fi
}

check_postgres() {
    if docker exec amasci-postgres pg_isready -U "${POSTGRES_USER:-amasci_user}" -d "${POSTGRES_DB:-amasci_db}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PostgreSQL: Ready"
        echo "{\"service\":\"postgresql\",\"status\":\"healthy\"}"
    else
        echo -e "${RED}✗${NC} PostgreSQL: Not Ready"
        echo "{\"service\":\"postgresql\",\"status\":\"down\"}"
    fi
}

check_neo4j() {
    if docker exec amasci-neo4j neo4j status 2>/dev/null | grep -q "running"; then
        echo -e "${GREEN}✓${NC} Neo4j: Running"
        echo "{\"service\":\"neo4j\",\"status\":\"healthy\"}"
    else
        echo -e "${RED}✗${NC} Neo4j: Not Running"
        echo "{\"service\":\"neo4j\",\"status\":\"down\"}"
    fi
}

check_resources() {
    echo ""
    echo "=== System Resources ==="

    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' 2>/dev/null || echo "N/A")
    local mem_info=$(free -m 2>/dev/null | awk 'NR==2{printf "%.1f%% (%dMB/%dMB)", $3*100/$2, $3, $2}' || echo "N/A")
    local disk_info=$(df -h / 2>/dev/null | awk 'NR==2{print $5 " (" $3 "/" $2 ")"}' || echo "N/A")

    echo "  CPU Usage: $cpu_usage%"
    echo "  Memory: $mem_info"
    echo "  Disk: $disk_info"
}

check_docker_containers() {
    echo ""
    echo "=== Docker Containers ==="
    docker ps --filter "name=amasci" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Docker not available"
}

echo "============================================================"
echo "  AMASCI Platform Health Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""
echo "=== Service Health ==="

results=()
results+=("$(check_service 'Backend API' "${API_URL}/api/v1/health")")
results+=("$(check_service 'Nginx' "${NGINX_URL}/health")")
results+=("$(check_postgres)")
results+=("$(check_neo4j)")

check_resources
check_docker_containers

echo ""
echo "=== Report saved to: $REPORT_FILE ==="

cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "services": [${results[*]}]
}
EOF

echo ""
echo "============================================================"
