# AMASCI - API Documentation

## Base URL

```
Development: http://localhost:8000/api/v1
Staging:     http://staging.amasci.local/api/v1
Production:  https://api.amasci.io/api/v1
```

## Authentication

All endpoints (except `/auth/login` and `/health`) require a Bearer token:

```
Authorization: Bearer <jwt_token>
```

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}

Response 200:
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

## Endpoints

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |

### Data Engineering

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/data/upload` | Upload CSV dataset |
| POST | `/data/validate` | Validate uploaded data |
| POST | `/data/clean` | Clean and preprocess data |
| POST | `/data/transform` | Feature engineering |
| GET | `/data/profile` | Data profiling report |
| POST | `/data/pipeline` | Run full pipeline |

### Machine Learning

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ml/train` | Train ML models |
| POST | `/ml/predict` | Generate predictions |
| GET | `/ml/models` | List trained models |
| GET | `/ml/evaluate` | Model evaluation metrics |
| GET | `/ml/feature-importance` | Feature importance scores |

### Forecasting

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ml/forecast/generate` | Generate demand forecast |
| GET | `/ml/forecast/results` | Get forecast results |
| POST | `/ml/forecast/validate` | Validate against actuals |

### Knowledge Graph

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graph/build` | Build knowledge graph |
| POST | `/graph/query` | Query graph (Cypher) |
| GET | `/graph/analytics` | Graph analytics metrics |
| GET | `/graph/entities` | List graph entities |
| GET | `/graph/relationships` | List relationships |
| GET | `/graph/health` | Neo4j health status |

### TPKE (Temporal Pattern Knowledge Evolution)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graph/tpke/evolve` | Trigger TPKE evolution |
| GET | `/graph/tpke/snapshots` | List graph snapshots |
| GET | `/graph/tpke/compare` | Compare graph versions |
| GET | `/graph/tpke/metrics` | TPKE performance metrics |

### GraphRAG

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graphrag/query` | Natural language query |
| GET | `/graphrag/context` | Get retrieval context |
| POST | `/graphrag/retrieve` | Retrieve subgraph |
| GET | `/graphrag/dependencies` | Dependency analysis |

### Root Cause Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rca/analyze` | Run RCA on incident |
| POST | `/rca/traverse` | Graph traversal |
| GET | `/rca/report` | Get RCA report |
| GET | `/rca/history` | RCA history |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/kpi` | KPI metrics |
| GET | `/dashboard/executive-summary` | Executive summary |
| GET | `/dashboard/forecast` | Forecast overview |
| GET | `/dashboard/risk` | Risk overview |
| GET | `/dashboard/graph` | Graph summary |
| GET | `/dashboard/tpke` | TPKE summary |
| GET | `/dashboard/rca` | RCA summary |
| GET | `/dashboard/trends` | Trend analysis |
| GET | `/dashboard/comparison` | Historical comparison |
| GET | `/dashboard/export` | Export data |

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "Description of the error",
    "field": "optional_field_name"
  }
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Internal Server Error |

## Rate Limits

| Endpoint Group | Limit |
|---------------|-------|
| General API | 30 requests/second |
| Authentication | 5 requests/second |
| File Upload | 5 requests/minute |

## Pagination

List endpoints support pagination:

```
GET /api/v1/endpoint?page=1&size=25
```

Response includes:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "size": 25,
  "pages": 4
}
```
