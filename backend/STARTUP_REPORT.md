# ============================================================
# AMASCI — STARTUP HEALTH CHECK REPORT
# Generated: 2026-07-14
# ============================================================

## SYSTEM INVENTORY

| Check                  | Status       | Detail                                          |
|------------------------|--------------|-------------------------------------------------|
| Project Structure      | ✅ PASS      | backend/, frontend/, data/ all present          |
| Dataset                | ✅ PASS      | DataCoSupplyChainDataset.csv — 91.5 MB, 180,519 rows |
| .env File              | ✅ CREATED   | backend/.env generated from template            |
| Python                 | ✅ PASS      | Python 3.13.3                                   |
| Node.js                | ✅ PASS      | v22.5.1                                         |
| Python Packages        | ✅ PASS      | All core + secondary packages installed         |
| Frontend Packages      | ✅ PASS      | node_modules present                            |
| Alembic Migrations     | ✅ PRESENT   | 001_initialization.py, 002_core_tables.py       |
| Docker                 | ⚠️  INSTALLED | Docker 29.4.3 — daemon NOT running              |
| PostgreSQL             | ❌ NOT RUNNING | Connection refused on localhost:5432           |
| Neo4j                  | ❌ NOT RUNNING | Connection refused on localhost:7687           |
| Initialization         | ⏳ PENDING   | .initialized marker not found                   |

---

## FOLDERS VERIFIED / CREATED

| Folder                     | Status      |
|----------------------------|-------------|
| backend/data/raw/          | ✅ EXISTS   |
| backend/data/uploads/      | ✅ EXISTS   |
| backend/data/models/       | ✅ EXISTS   |
| backend/data/logs/         | ✅ EXISTS   |
| backend/data/processed/    | ✅ CREATED  |
| backend/data/actuals/      | ✅ CREATED  |
| backend/data/forecasts/    | ✅ CREATED  |
| backend/reports/           | ✅ CREATED  |

---

## PACKAGES INSTALLED AUTOMATICALLY

| Package         | Action    |
|-----------------|-----------|
| structlog       | Installed |
| python-json-logger | Installed |

---

## ⚠️  ACTION REQUIRED — DATABASE SERVICES

PostgreSQL and Neo4j are **not running** on this machine.

You have **two options**:

---

### OPTION A — Docker Compose (Recommended)

1. **Start Docker Desktop**
   - Open Docker Desktop application
   - Wait until the engine is running (green icon in system tray)

2. **Start databases**
   ```bash
   cd backend
   docker-compose up -d postgres neo4j
   ```

3. **Wait for health checks** (~30 seconds)
   ```bash
   docker-compose ps
   ```
   Both should show "healthy"

4. **Credentials are already set** in docker-compose.yml:
   - PostgreSQL: `amasci_user` / `amasci_password` / `amasci_db`
   - Neo4j: `neo4j` / `neo4j_password`

5. **Update .env** to match docker-compose credentials:
   ```
   POSTGRES_USER=amasci_user
   POSTGRES_PASSWORD=amasci_password
   POSTGRES_DB=amasci_db
   DATABASE_URL=postgresql+asyncpg://amasci_user:amasci_password@localhost:5432/amasci_db

   NEO4J_USER=neo4j
   NEO4J_PASSWORD=neo4j_password
   ```

---

### OPTION B — Local Installation

1. **Install PostgreSQL 16** from https://www.postgresql.org/download/windows/
   - During install, set password for `postgres` user
   - Create database: `CREATE DATABASE amasci_db;`

2. **Install Neo4j Desktop** from https://neo4j.com/download/
   - Create a new project + database
   - Set password for `neo4j` user
   - Start the database

3. **Update .env** with your chosen credentials:
   ```
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=<your_postgres_password>
   POSTGRES_DB=amasci_db
   DATABASE_URL=postgresql+asyncpg://postgres:<your_postgres_password>@localhost:5432/amasci_db

   NEO4J_USER=neo4j
   NEO4J_PASSWORD=<your_neo4j_password>
   ```

---

## AFTER DATABASES ARE RUNNING

Execute these commands in order:

```bash
cd backend

# 1. Run migrations (creates all 13 domain tables)
alembic upgrade head

# 2. Start backend (triggers auto-initialization on first boot)
uvicorn app.main:app --reload --port 8000
```

**First boot will automatically:**
- Detect DataCoSupplyChainDataset.csv
- Run 7-step initialization pipeline
- Train ML models (LightGBM + RandomForest)
- Build Knowledge Graph in Neo4j
- Mark system as initialized

**Expected console output:**
```
INFO  AMASCI Platform starting up...
INFO  System not initialized. Checking for master dataset...
INFO  Master dataset found: DataCoSupplyChainDataset.csv
INFO  === SYSTEM INITIALIZATION STARTED ===
INFO  [1/7] Loading dataset...
INFO  [1/7] Loaded: 180519 rows, 53 columns
INFO  [2/7] Running data engineering pipeline...
INFO  [3/7] Feature engineering...
INFO  [4/7] Training ML models...
INFO  [5/7] Building Knowledge Graph...
INFO  [6/7] Verifying model registry...
INFO  [7/7] Saving processed dataset...
INFO  === SYSTEM INITIALIZATION COMPLETED in XXs ===
INFO  Startup complete.
```

Then in a new terminal:
```bash
cd frontend
npm run dev
```

Open: http://localhost:5173

---

## VERIFICATION ENDPOINTS

| Endpoint | Expected |
|----------|----------|
| GET http://localhost:8000/api/v1/health | `{"status": "healthy"}` |
| GET http://localhost:8000/api/v1/admin/initialization/status | `{"initialized": true}` |
| GET http://localhost:8000/api/v1/business/dashboard | Dashboard KPIs |

---

## OVERALL STATUS

```
╔══════════════════════════════════════════════╗
║  AMASCI STARTUP STATUS: BLOCKED             ║
║                                             ║
║  Reason: PostgreSQL + Neo4j not running     ║
║                                             ║
║  Fix: Start Docker Desktop, then run:       ║
║       docker-compose up -d postgres neo4j   ║
║                                             ║
║  Everything else is READY.                  ║
╚══════════════════════════════════════════════╝
```
