# AMASCI - Adaptive Supply Chain Intelligence Platform

> Temporal Knowledge Graph Evolution (TPKE) and GraphRAG-Guided Risk Reasoning

[![CI/CD](https://github.com/your-org/amasci/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-org/amasci/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

AMASCI is an enterprise supply chain intelligence platform that combines Machine Learning, Knowledge Graphs, and novel algorithms (TPKE, GraphRAG) to provide predictive analytics, risk assessment, and root cause analysis for supply chain operations.

## Key Features

- **Demand Forecasting** — LightGBM with Walk-Forward Validation (91%+ accuracy)
- **Knowledge Graph** — Neo4j-powered entity relationship modeling
- **TPKE Algorithm** — Temporal Pattern Knowledge Evolution for dynamic graph updates
- **GraphRAG** — Graph-augmented retrieval for contextual risk reasoning
- **Root Cause Analysis** — Graph traversal-based causal chain identification
- **Enterprise Dashboard** — Real-time KPIs, analytics, and reporting

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Frontend | React 18, TypeScript 5.5, Vite 5, Recharts |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 |
| Database | PostgreSQL 16, Neo4j 5.15 |
| ML | LightGBM, scikit-learn, LangChain |
| Infrastructure | Docker, Nginx, GitHub Actions |

## Quick Start

```bash
# Development
make dev
cd frontend && npm run dev

# Production
make prod-build
make prod
```

## Documentation

- [Deployment Guide](deployment/docs/DEPLOYMENT.md)
- [Developer Guide](deployment/docs/DEVELOPER.md)

## Project Stats

- **Backend**: 234 tests passing
- **Frontend**: 409 source files, 0 TypeScript errors
- **Build**: ~9.4s production build
- **Dataset**: DataCo Smart Supply Chain (180,519 rows, 53 columns)

## License

MIT License - See [LICENSE](LICENSE) for details.
