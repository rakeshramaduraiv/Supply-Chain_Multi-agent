# AMASCI - Troubleshooting Guide

## Quick Diagnostics

```bash
# Check all services
make status

# Full health check
make health

# View logs
make logs

# Specific service logs
docker compose -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.dev.yml logs -f postgres
docker compose -f docker-compose.dev.yml logs -f neo4j
```

## Common Issues

### 1. Port Already in Use

**Symptom**: `Error: bind: address already in use`

**Solution**:
```bash
# Find process using the port
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in .env
kill -9 <PID>
```

### 2. Database Connection Failed

**Symptom**: `ConnectionRefusedError` or `could not connect to server`

**Solution**:
```bash
# Check if PostgreSQL is running
docker exec amasci-postgres pg_isready

# Check container health
docker inspect amasci-postgres --format='{{.State.Health.Status}}'

# Restart database
docker compose -f docker-compose.dev.yml restart postgres

# Check logs
docker logs amasci-postgres --tail 50
```

### 3. Neo4j Connection Timeout

**Symptom**: `ServiceUnavailable: Failed to establish connection`

**Solution**:
```bash
# Neo4j takes 30-45s to start
docker logs amasci-neo4j --tail 20

# Check status
docker exec amasci-neo4j neo4j status

# Verify bolt port
curl http://localhost:7474

# If OOM, increase memory
# Edit docker-compose: NEO4J_dbms_memory_heap_max__size: 1G
```

### 4. Frontend Build Fails

**Symptom**: TypeScript errors or Vite build failure

**Solution**:
```bash
cd frontend

# Clear cache
rm -rf node_modules/.vite

# Reinstall dependencies
rm -rf node_modules
npm ci

# Check TypeScript
npx tsc --noEmit

# Build with verbose output
npm run build -- --debug
```

### 5. Docker Build Context Too Large

**Symptom**: Slow builds, large context transfer

**Solution**:
```bash
# Check .dockerignore is present at project root
cat .dockerignore

# Check context size
docker build --no-cache -f deployment/docker/Dockerfile.backend . 2>&1 | head -5

# Ensure node_modules and data dirs are excluded
```

### 6. Permission Denied in Container

**Symptom**: `PermissionError` or `EACCES`

**Solution**:
```bash
# Check container user
docker exec amasci-api whoami

# Fix volume permissions
docker exec -u root amasci-api chown -R amasci:amasci /app/data

# Rebuild with correct ownership
docker compose -f docker-compose.dev.yml build --no-cache api
```

### 7. JWT Token Expired

**Symptom**: `401 Unauthorized` after period of inactivity

**Solution**:
- Development: Token expires in 24 hours (1440 min)
- Production: Token expires in 8 hours (480 min)
- Re-login via `/api/v1/auth/login`
- Check `JWT_EXPIRATION_MINUTES` in environment

### 8. ML Model Training Fails

**Symptom**: `ValueError` or `MemoryError` during training

**Solution**:
```bash
# Check available memory
docker stats amasci-api

# Increase container memory limit in docker-compose
# deploy.resources.limits.memory: 4G

# Check dataset size
docker exec amasci-api ls -la /app/data/uploads/

# Reduce dataset or model complexity
```

### 9. CORS Errors in Browser

**Symptom**: `Access-Control-Allow-Origin` errors in console

**Solution**:
```bash
# Check CORS_ORIGINS in environment
echo $CORS_ORIGINS

# Must include frontend URL exactly
# Development: http://localhost:3000,http://localhost:5173
# Production: https://app.amasci.io

# Restart backend after changing
docker compose restart api
```

### 10. Nginx 502 Bad Gateway

**Symptom**: Browser shows 502 error

**Solution**:
```bash
# Check if backend is running
docker ps | grep amasci-api

# Check backend health
curl http://localhost:8000/api/v1/health

# Check nginx upstream config
docker exec amasci-nginx cat /etc/nginx/conf.d/default.conf

# Verify network connectivity
docker network inspect amasci-net
```

## Performance Issues

### Slow API Responses

```bash
# Check response times
curl -w "@-" -o /dev/null -s http://localhost:8000/api/v1/health <<'EOF'
    time_namelookup:  %{time_namelookup}s\n
    time_connect:     %{time_connect}s\n
    time_total:       %{time_total}s\n
EOF

# Check database query times
docker exec amasci-postgres psql -U amasci_user -d amasci_db \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"

# Check Neo4j query times
# Access Neo4j browser at http://localhost:7474
# Run: CALL db.stats.retrieve("QUERIES")
```

### High Memory Usage

```bash
# Check container stats
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"

# Check for memory leaks in Python
docker exec amasci-api python -c "import tracemalloc; tracemalloc.start()"
```

## Recovery Procedures

### Full System Recovery

```bash
# 1. Stop all services
make stop

# 2. Restore from backup
./deployment/backup/restore.sh postgres /path/to/postgres.sql.gz
./deployment/backup/restore.sh neo4j /path/to/neo4j.dump.gz

# 3. Start services
make prod  # or make dev

# 4. Run migrations
make migrate

# 5. Verify health
make health
```

### Reset Development Environment

```bash
# Nuclear option - removes everything
make clean-all

# Rebuild from scratch
make dev
make migrate
```

## Log Locations

| Service | Container Path | Host Access |
|---------|---------------|-------------|
| Backend | `/app/data/logs/` | `docker logs amasci-api` |
| Nginx | `/var/log/nginx/` | `docker logs amasci-nginx` |
| PostgreSQL | stdout | `docker logs amasci-postgres` |
| Neo4j | `/logs/` | `docker logs amasci-neo4j` |

## Getting Help

1. Check this troubleshooting guide
2. Review service logs: `make logs`
3. Run health check: `make health`
4. Check GitHub Issues
5. Review deployment docs: `deployment/docs/DEPLOYMENT.md`
