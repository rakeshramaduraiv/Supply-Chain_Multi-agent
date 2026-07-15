# AMASCI - System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  React 18 + TypeScript + Vite + Recharts + React Query    │  │
│  │  CSS Modules | 10 Page Modules | 409 Source Files         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Nginx Reverse Proxy                         │
│  Rate Limiting | Gzip | Security Headers | Static Cache         │
│  TLS Termination | Load Balancing | Access Logging              │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP (internal)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  FastAPI + Uvicorn (4 workers)                            │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐   │  │
│  │  │  Auth   │ │  Data   │ │   ML    │ │  Dashboard   │   │  │
│  │  │  JWT    │ │  Eng.   │ │ Pipeline│ │  Analytics   │   │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────────┘   │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐   │  │
│  │  │  Graph  │ │  TPKE   │ │GraphRAG │ │     RCA      │   │  │
│  │  │  Build  │ │  Evolve │ │ Retrieve│ │   Analyze    │   │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │              │
              ┌──────────┘              └──────────┐
              ▼                                    ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│     PostgreSQL 16        │    │        Neo4j 5.15             │
│  ┌────────────────────┐  │    │  ┌────────────────────────┐  │
│  │ Users, Models,      │  │    │  │ Suppliers, Products,   │  │
│  │ Predictions, Audit  │  │    │  │ Warehouses, Orders,    │  │
│  │ Configs, Sessions   │  │    │  │ Shipments, Customers   │  │
│  └────────────────────┘  │    │  │ TPKE Edges, Patterns   │  │
│  Source of Truth         │    │  └────────────────────────┘  │
│  ACID Transactions       │    │  Graph Traversal             │
│  Full-text Search        │    │  PageRank, GDS Algorithms    │
└──────────────────────────┘    └──────────────────────────────┘
```

## Data Flow

```
CSV Upload → Validation → Cleaning → Feature Engineering
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            ML Training              Graph Build              Dashboard
            (LightGBM)              (Neo4j)                  (KPIs)
                    │                       │
                    ▼                       ▼
            Predictions              TPKE Evolution
                    │                       │
                    └───────────┬───────────┘
                                ▼
                          GraphRAG Query
                                │
                                ▼
                     Root Cause Analysis
                                │
                                ▼
                      Executive Reports
```

## Module Architecture (Backend)

```
app/
├── api/                    # Presentation Layer
│   ├── routes/             # FastAPI route handlers
│   ├── schemas/            # Pydantic request/response models
│   └── dependencies/       # Dependency injection
├── core/                   # Cross-cutting Concerns
│   ├── config.py           # Pydantic Settings
│   ├── security.py         # JWT, RBAC
│   ├── middleware.py       # Correlation ID, Timing
│   ├── exceptions.py       # Custom exception hierarchy
│   └── logging.py          # Structured JSON logging
├── services/               # Business Logic Layer
│   ├── data/               # Upload, Validate, Clean, Transform
│   ├── ml/                 # Train, Predict, Evaluate
│   ├── graph/              # Build, Query, TPKE
│   ├── graphrag/           # Retrieve, Context, Query
│   ├── rca/                # Analyze, Traverse, Report
│   └── dashboard/          # KPIs, Trends, Export
├── repositories/           # Data Access Layer
│   ├── postgres/           # SQLAlchemy repositories
│   └── neo4j/              # Neo4j driver repositories
├── models/                 # Domain Models
│   ├── database.py         # SQLAlchemy models
│   └── graph.py            # Neo4j node/relationship models
└── main.py                 # Application entry point
```

## Frontend Module Architecture

```
src/
├── api/                    # HTTP client layer
├── components/             # 15 reusable UI components
├── contexts/               # Auth, Theme, Notification, Toast
├── pages/                  # Feature modules
│   ├── Dashboard/          # Executive dashboard (28 files)
│   ├── TrainingCenter/     # ML training (29 files)
│   ├── ForecastCenter/     # Forecast generation (27 files)
│   ├── KnowledgeGraph/     # Graph explorer (44 files)
│   ├── TPKEEvolution/      # TPKE dashboard (44 files)
│   ├── GraphRAG/           # GraphRAG interface (41 files)
│   ├── RootCauseAnalysis/  # RCA center (41 files)
│   ├── Analytics/          # Analytics reporting (33 files)
│   └── Administration/     # Admin settings (29 files)
├── hooks/                  # Custom React hooks
├── utils/                  # Helpers, formatters
└── styles/                 # Global CSS variables
```

## Security Architecture

```
┌─────────────────────────────────────────┐
│              Security Layers            │
├─────────────────────────────────────────┤
│ L1: Network (Docker bridge isolation)   │
│ L2: TLS (Nginx SSL termination)        │
│ L3: Rate Limiting (30r/s API, 5r/s auth)│
│ L4: Authentication (JWT HS256)          │
│ L5: Authorization (RBAC 5 roles)        │
│ L6: Input Validation (Pydantic)         │
│ L7: SQL Injection (SQLAlchemy ORM)      │
│ L8: XSS (CSP headers, React escaping)  │
│ L9: CSRF (SameSite cookies)             │
│ L10: Secrets (env injection, no commit) │
└─────────────────────────────────────────┘
```

## Deployment Environments

| Environment | Purpose | Compose File | Port |
|-------------|---------|-------------|------|
| Development | Local dev with hot-reload | `docker-compose.dev.yml` | 8000 |
| Testing | CI/CD automated tests | Service containers | 8000 |
| Staging | Pre-production validation | `docker-compose.staging.yml` | 8080 |
| Production | Live deployment | `docker-compose.prod.yml` | 80/443 |

## Novel Contributions

### TPKE (Temporal Pattern Knowledge Evolution)
- Sliding window analysis over supply chain events
- Conditional probability calculation for edge weights
- Edge decay for stale relationships
- Pattern detection with frequency thresholds

### GraphRAG (Graph-Augmented Retrieval)
- Subgraph extraction based on query relevance
- Entity embedding for semantic similarity
- Context building from graph neighborhoods
- Evidence chain construction for reasoning

### Risk-Aware Knowledge Graphs
- Multi-dimensional risk scoring per entity
- Causal chain identification via graph traversal
- Dependency ranking with centrality metrics
- Temporal risk propagation modeling
