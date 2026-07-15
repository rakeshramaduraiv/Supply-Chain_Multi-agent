# AMASCI — Adaptive Supply Chain Intelligence Platform

## Enterprise AI-Powered Supply Chain Risk Intelligence

Using **Temporal Knowledge Graph Evolution (TPKE)** and **GraphRAG-Guided Risk Reasoning**

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Docker Deployment](#docker-deployment)
- [API Documentation](#api-documentation)
- [Development Guide](#development-guide)
- [Testing](#testing)

---

## Overview

AMASCI is an enterprise-grade supply chain intelligence platform that transforms raw operational data into actionable business intelligence through:

- **ML-driven risk prediction** (LightGBM with Walk-Forward Validation)
- **Dynamic Knowledge Graph** construction and evolution
- **TPKE** — Novel temporal pattern-triggered graph evolution
- **GraphRAG** — Graph-based retrieval-augmented reasoning
- **Root Cause Analysis** — Combined ML + Graph evidence

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                     │
│              FastAPI REST + WebSocket APIs                │
├─────────────────────────────────────────────────────────┤
│                   APPLICATION LAYER                       │
│         Pipelines, Orchestration, Coordination           │
├─────────────────────────────────────────────────────────┤
│                    BUSINESS LAYER                         │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────┐ │
│  │Feature │ │   ML   │ │ Graph  │ │  TPKE  │ │GraphR│ │
│  │Engineer│ │ Engine │ │ Engine │ │ Engine │ │  AG  │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └──────┘ │
├─────────────────────────────────────────────────────────┤
│                 INFRASTRUCTURE LAYER                      │
│          Repositories, Caching, File Storage             │
├─────────────────────────────────────────────────────────┤
│                  PERSISTENCE LAYER                        │
│         ┌──────────────┐    ┌──────────────┐            │
│         │  PostgreSQL  │    │    Neo4j     │            │
│         └──────────────┘    └──────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Runtime | Python | 3.11 |
| Web Framework | FastAPI | 0.104.1 |
| Validation | Pydantic | 2.5.2 |
| ORM | SQLAlchemy | 2.0.23 |
| Migrations | Alembic | 1.13.0 |
| Relational DB | PostgreSQL | 16 |
| Graph DB | Neo4j | 5.15 |
| ML | LightGBM | 4.2.0 |
| Explainability | SHAP | 0.44.0 |
| Data Processing | Pandas/NumPy | Latest |
| Containerization | Docker | Latest |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                    # Application entry point
│   ├── api/                       # Presentation layer (endpoints)
│   ├── core/                      # Config, security, constants, enums
│   ├── models/                    # SQLAlchemy ORM models
│   ├── schemas/                   # Pydantic request/response models
│   ├── repositories/              # Data access layer
│   ├── services/                  # Business logic orchestration
│   ├── pipelines/                 # Multi-step workflow orchestration
│   ├── feature_engineering/       # Business feature computation
│   ├── ml/                        # LightGBM training & prediction
│   ├── forecast/                  # Risk forecasting engine
│   ├── graph/                     # Knowledge Graph construction
│   ├── tpke/                      # Temporal Pattern KG Evolution
│   ├── graphrag/                  # Graph RAG reasoning
│   ├── rca/                       # Root Cause Analysis
│   ├── analytics/                 # KPI & trend computation
│   ├── dashboard/                 # Dashboard payload assembly
│   ├── database/                  # DB connection management
│   ├── exceptions/                # Custom exception hierarchy
│   ├── logging/                   # Structured logging
│   └── utils/                     # Shared utilities
├── tests/                         # Test suite
├── scripts/                       # Utility scripts
├── alembic/                       # Database migrations
├── data/                          # Runtime data (uploads, models, logs)
├── docker-compose.yml             # Service orchestration
├── Dockerfile                     # Container definition
├── requirements.txt               # Dependencies
└── Makefile                       # Development commands
```

---

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Neo4j 5.15+
- Docker & Docker Compose (for containerized deployment)

### Local Development Setup

```bash
# 1. Clone and navigate
cd backend

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your database credentials

# 5. Initialize databases
python -m scripts.init_db

# 6. Run migrations
alembic upgrade head
```

---

## Running the Application

### Development Mode (with hot reload)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Makefile

```bash
make dev        # Development with reload
make run        # Production
make test       # Run tests
make lint       # Run linters
make format     # Format code
```

---

## Docker Deployment

### Start All Services

```bash
docker-compose up -d --build
```

### View Logs

```bash
docker-compose logs -f api
```

### Stop Services

```bash
docker-compose down
```

### Services

| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | localhost:5432 |
| Neo4j Browser | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | bolt://localhost:7687 |

---

## API Documentation

Once running, access:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

### Key Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/v1/health | System health check |
| POST | /api/v1/upload/train | Upload training dataset |
| POST | /api/v1/upload/actuals | Upload actual data |
| POST | /api/v1/train | Trigger model training |
| POST | /api/v1/forecast | Generate forecasts |
| POST | /api/v1/graph/build | Build Knowledge Graph |
| POST | /api/v1/tpke/run | Execute TPKE evolution |
| POST | /api/v1/graphrag/query | GraphRAG reasoning query |
| POST | /api/v1/rootcause | Root cause analysis |
| GET | /api/v1/dashboard | Dashboard data |
| GET | /api/v1/analytics | Analytics data |

---

## Development Guide

### Code Style

- **Formatter:** Black (line-length: 100)
- **Import Sorting:** isort (black profile)
- **Linter:** Ruff
- **Type Checking:** mypy (strict mode)

### Adding a New Module

1. Create package under `app/` with `__init__.py`
2. Define service in `app/services/`
3. Define schemas in `app/schemas/`
4. Create endpoint in `app/api/v1/endpoints/`
5. Register router in `app/api/v1/router.py`
6. Add tests in `tests/unit/`

### Environment Variables

All configuration is managed via environment variables. See `.env.example` for the complete list.

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_health.py

# Run with verbose output
pytest -v
```

---

## License

Proprietary — AMASCI Platform
