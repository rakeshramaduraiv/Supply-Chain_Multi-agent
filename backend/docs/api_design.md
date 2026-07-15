# AMASCI API Design

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All endpoints (except /health, /live, /ready) require JWT Bearer token.

```
Authorization: Bearer <token>
```

## Standard Response Format

### Success
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Error
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "status_code": 422,
    "details": { ... }
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Endpoints

### Upload
- `POST /upload/train` — Upload historical training dataset
- `POST /upload/actuals` — Upload actual next-month data for comparison

### Training
- `POST /train` — Trigger ML model training pipeline

### Forecast
- `POST /forecast` — Generate next-month risk forecasts
- `GET /forecast/latest` — Get latest forecast results

### Knowledge Graph
- `POST /graph/build` — Build Knowledge Graph from data
- `POST /graph/update` — Update graph with new predictions
- `GET /graph` — Get graph statistics and summary

### TPKE
- `POST /tpke/run` — Execute TPKE evolution cycle
- `GET /tpke/history` — Get TPKE evolution history

### GraphRAG
- `POST /graphrag/query` — Submit reasoning query

### Root Cause
- `POST /rootcause` — Analyze root cause for entity

### Dashboard
- `GET /dashboard` — Get complete dashboard payload

### Analytics
- `GET /analytics` — Get analytics aggregations

### Models
- `GET /models` — List trained model versions

### Health
- `GET /health` — Full health check
- `GET /ready` — Readiness probe
- `GET /live` — Liveness probe
