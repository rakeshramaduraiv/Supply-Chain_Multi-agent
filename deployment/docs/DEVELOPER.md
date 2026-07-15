# AMASCI - Developer Guide

## Project Structure

```
supply-chain/
├── backend/                    # FastAPI backend (Python 3.11)
│   ├── app/                    # Application source
│   │   ├── api/                # API routes
│   │   ├── core/               # Config, security, middleware
│   │   ├── models/             # SQLAlchemy models
│   │   ├── services/           # Business logic
│   │   ├── repositories/       # Data access layer
│   │   └── main.py             # FastAPI app entry
│   ├── tests/                  # pytest test suite
│   ├── alembic/                # Database migrations
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Backend container
├── frontend/                   # React 18 frontend (TypeScript)
│   ├── src/
│   │   ├── api/                # Axios client + endpoints
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Page modules (10 pages)
│   │   ├── contexts/           # React contexts
│   │   ├── hooks/              # Custom hooks
│   │   ├── utils/              # Helpers
│   │   └── styles/             # Global CSS
│   ├── package.json
│   └── vite.config.ts
├── deployment/                 # DevOps infrastructure
│   ├── docker/                 # Dockerfiles
│   ├── nginx/                  # Nginx configuration
│   ├── monitoring/             # Health checks, logging
│   ├── backup/                 # Backup/restore scripts
│   ├── scripts/                # Deployment scripts
│   └── docs/                   # Documentation
├── .github/workflows/          # CI/CD pipeline
├── docker-compose.dev.yml      # Development compose
├── docker-compose.prod.yml     # Production compose
├── .env.development            # Dev environment
├── .env.testing                # Test environment
└── .env.production             # Prod environment template
```

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 22+
- Docker & Docker Compose
- Git

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start databases
docker compose up -d postgres neo4j

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Type check
npx tsc --noEmit

# Production build
npm run build
```

### Running Tests

```bash
# Backend (from backend/)
pytest tests/ --override-ini="addopts=" -v --tb=short -x

# Frontend type check (from frontend/)
npx tsc --noEmit
```

## Architecture Patterns

### Backend - Clean Architecture

```
Presentation (API Routes)
    ↓
Application (Services)
    ↓
Business (Domain Logic)
    ↓
Infrastructure (Repositories)
    ↓
Persistence (PostgreSQL + Neo4j)
```

### Frontend - Feature-Based Modules

Each page is a self-contained module:
```
pages/ModuleName/
├── components/     # UI components
├── hooks/          # React Query hooks
├── services/       # API service layer
├── types/          # TypeScript interfaces
├── styles/         # CSS Modules
└── index.tsx       # Page orchestrator
```

## Key Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TypeScript | UI framework |
| State | React Query (TanStack) | Server state management |
| Charts | Recharts | Data visualization |
| Styling | CSS Modules | Scoped styles |
| Backend | FastAPI | REST API framework |
| ORM | SQLAlchemy 2.0 | Database abstraction |
| ML | LightGBM + scikit-learn | Predictions |
| Graph | Neo4j 5.x | Knowledge graph |
| Auth | JWT (python-jose) | Authentication |

## API Conventions

- Base URL: `/api/v1`
- Auth: Bearer token in Authorization header
- Responses: JSON with consistent error format
- Pagination: `?page=1&size=25`
- Filtering: Query parameters

## Git Workflow

1. Create feature branch from `develop`
2. Implement changes with tests
3. Push and create PR to `develop`
4. CI pipeline runs automatically
5. Merge to `develop` after review
6. Release: merge `develop` → `main`
