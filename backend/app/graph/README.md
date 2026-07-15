# Knowledge Graph Intelligence Layer - Developer Documentation

## Architecture Overview

The Knowledge Graph module constructs and manages a Neo4j-backed supply chain knowledge graph from engineered DataCo datasets.

```
app/graph/
├── connection/     # Neo4j connection manager (pooling, retry, health)
├── builder/        # Bulk graph construction (MERGE, batch, transactions)
├── extractor/      # Entity extraction from DataFrames
├── nodes/          # Node type definitions (7 entity types)
├── relationships/  # Relationship definitions (7 types)
├── analytics/      # Graph analytics (centrality, PageRank, components)
├── validator/      # Graph integrity validation
├── repository/     # CRUD operations against Neo4j
├── services/       # Business logic orchestration
├── schemas/        # Pydantic API contracts
├── routes/         # FastAPI endpoints
└── utils/          # Shared helpers
```

## Node Types

| Node | Key Properties | Source |
|------|---------------|--------|
| Supplier | reliability_score, delay_rate, risk_score | Department Name aggregation |
| Product | rolling_7d_demand, demand_volatility, forecast_risk | Category Name aggregation |
| Warehouse | stock_coverage_ratio, inventory_stress_index | Order City aggregation |
| Shipment | shipping_delay, efficiency_score, late_delivery_rate | Shipping Mode aggregation |
| Customer | segment, avg_order_value, profit_margin | Customer Id aggregation |
| Order | order_value, order_quantity, risk_score | Individual orders (sampled) |
| CalendarEvent | event_name, event_type, is_holiday | Temporal features |

## Relationship Types

| Relationship | Source → Target | Properties |
|-------------|----------------|------------|
| SUPPLIES | Supplier → Product | strength, frequency, avg_delay |
| STORED_IN | Product → Warehouse | strength, frequency |
| SHIPS_VIA | Order → Shipment | strength |
| DELIVERED_TO | Shipment → Customer | strength, frequency, avg_delay |
| PLACED | Customer → Order | strength |
| CONTAINS | Order → Product | strength |
| INFLUENCES | CalendarEvent → Order | strength, confidence |

## Usage

### Build Graph

```python
from app.graph.connection import get_connection_manager
from app.graph.services import GraphService

conn = get_connection_manager()
await conn.connect()

service = GraphService(conn)
result = await service.build_graph(df, dataset_version="v1.0", clear_existing=True)
print(f"Built: {result.nodes_created} nodes, {result.relationships_created} rels")
```

### Query Entities

```python
# Get entity with connections
entity = await service.get_entity("node_id_here")

# Get subgraph
subgraph = await service.get_subgraph("node_id_here", max_hops=2)

# Get nodes by label
suppliers = await service.get_nodes("Supplier", limit=50)
```

### Analytics

```python
# Statistics
stats = await service.get_statistics()

# Degree centrality
top_suppliers = await service.degree_centrality("Supplier", top_n=10)

# Shortest path
path = await service.shortest_path("source_id", "target_id")
```

### Validation

```python
result = await service.validate_graph()
if not result.is_valid:
    for issue in result.issues:
        print(f"[{issue.severity}] {issue.message}")
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/graph/build` | Build graph from processed dataset |
| POST | `/api/v1/graph/update` | Incremental update |
| POST | `/api/v1/graph/rebuild` | Full rebuild (clear + build) |
| POST | `/api/v1/graph/import` | Import from JSON |
| POST | `/api/v1/graph/export` | Export to JSON |
| GET | `/api/v1/graph/statistics` | Graph statistics |
| GET | `/api/v1/graph/validate` | Validate integrity |
| GET | `/api/v1/graph/nodes?label=Supplier` | Get nodes by label |
| GET | `/api/v1/graph/relationships?label=Supplier&node_id=x` | Get relationships |
| GET | `/api/v1/graph/entity/{node_id}` | Get entity with connections |
| GET | `/api/v1/graph/subgraph?node_id=x&max_hops=2` | Get ego network |
| GET | `/api/v1/graph/centrality/{label}?algorithm=degree` | Centrality analysis |
| GET | `/api/v1/graph/shortest-path?source_id=x&target_id=y` | Shortest path |

## Graph Build Pipeline

```
DataFrame → EntityExtractor → [Nodes + Relationships] → GraphBuilder → Neo4j
                                                              ↓
                                                    MERGE (upsert) queries
                                                    Batch processing (500/batch)
                                                    Transaction management
```

## Testing

```bash
# Unit tests (61 tests, no Neo4j required)
pytest tests/unit/graph/ -v --override-ini="addopts="

# Integration tests (require running Neo4j)
# Set pytestmark skip to False in test file first
pytest tests/integration/graph/ -v --override-ini="addopts="
```

## Extension Points

This module connects with:
- **TPKE Module**: Graph edges evolve based on temporal patterns
- **GraphRAG Module**: Graph context feeds into LLM reasoning
- **ML Module**: Model predictions update node risk scores
- **Dashboard Module**: Graph visualization data
