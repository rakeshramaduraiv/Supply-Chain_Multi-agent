# AMASCI - Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Nginx (Port 80)                       │
│              Reverse Proxy + Static Files                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Frontend   │  │   Backend    │  │   Neo4j      │ │
│  │   (React)    │  │  (FastAPI)   │  │  (Graph DB)  │ │
│  │   Static     │  │  Port 8000   │  │  Port 7687   │ │
│  └──────────────┘  └──────┬───────┘  └──────────────┘ │
│                            │                            │
│                    ┌───────┴───────┐                    │
│                    │  PostgreSQL   │                    │
│                    │  Port 5432    │                    │
│                    └───────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker 24+ and Docker Compose v2
- 4GB RAM minimum (8GB recommended)
- 20GB disk space
- Git

## Quick Start

### Development

```bash
# Clone and start
git clone <repository-url>
cd supply-chain

# Start backend services
./deployment/scripts/deploy.sh dev

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Production

```bash
# Configure environment
cp .env.production .env.production.local
# Edit .env.production.local with real secrets

# Build and deploy
./deployment/scripts/deploy.sh build
./deployment/scripts/deploy.sh prod
```

## Environment Configuration

| Environment | File | Purpose |
|-------------|------|---------|
| Development | `.env.development` | Local development with debug |
| Testing | `.env.testing` | CI/CD pipeline tests |
| Production | `.env.production` | Production deployment |

### Required Production Secrets

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key (64+ chars) |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `NEO4J_PASSWORD` | Neo4j password |
| `CORS_ORIGINS` | Allowed frontend origins |
| `VITE_API_BASE_URL` | Public API URL |

## Docker Commands

```bash
# Development
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.dev.yml down

# Production
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml down
```

## Database Management

### Migrations

```bash
# Run migrations
docker exec amasci-api alembic upgrade head

# Create new migration
docker exec amasci-api alembic revision --autogenerate -m "description"
```

### Backups

```bash
# Manual backup
./deployment/backup/backup-postgres.sh
./deployment/backup/backup-neo4j.sh

# Restore
./deployment/backup/restore.sh postgres /path/to/backup.sql.gz
./deployment/backup/restore.sh neo4j /path/to/backup.dump.gz
```

## Monitoring

### Health Checks

```bash
# Full health check
./deployment/monitoring/health-check.sh

# Individual services
curl http://localhost:8000/api/v1/health
curl http://localhost:80/health
```

### Logs

```bash
# All services
./deployment/scripts/deploy.sh logs

# Specific service
./deployment/scripts/deploy.sh logs api
./deployment/scripts/deploy.sh logs nginx
./deployment/scripts/deploy.sh logs postgres
```

## Security

### Headers (Nginx)
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security: max-age=31536000
- Content-Security-Policy: configured
- Referrer-Policy: strict-origin-when-cross-origin

### Rate Limiting
- API: 30 requests/second per IP
- Auth: 5 requests/second per IP
- Connection limit: 100 per IP

### Authentication
- JWT with HS256
- Token expiry: 8 hours (production)
- Refresh token rotation
- RBAC with 5 role levels

## CI/CD Pipeline

The GitHub Actions workflow runs on push to `main` and `develop`:

1. **Backend Lint** - Ruff, Black, isort
2. **Backend Tests** - pytest with PostgreSQL service
3. **Frontend Lint** - TypeScript type check
4. **Frontend Build** - Vite production build
5. **Security Scan** - Safety + Bandit
6. **Docker Build** - Multi-stage build + push to GHCR
7. **Deploy** - Production deployment (main only)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port conflict | Check `docker ps` and stop conflicting containers |
| Database connection | Verify health checks: `docker exec amasci-postgres pg_isready` |
| Neo4j OOM | Increase `NEO4J_dbms_memory_heap_max__size` |
| Build fails | Clear cache: `docker builder prune` |
| Permission denied | Check file ownership matches container user |

## Performance Tuning

### PostgreSQL
- `shared_buffers`: 25% of available RAM
- `effective_cache_size`: 75% of available RAM
- `work_mem`: 16MB per connection
- `max_connections`: 100

### Neo4j
- `heap_max_size`: 50% of available RAM (max 4G)
- `pagecache_size`: 25% of available RAM

### Nginx
- `worker_processes`: auto (matches CPU cores)
- `worker_connections`: 4096
- Gzip compression enabled
- Static asset caching: 1 year (immutable)
