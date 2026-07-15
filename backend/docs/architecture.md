# AMASCI Backend Architecture

## Clean Architecture Layers

### Layer 1: Presentation (app/api/)
- HTTP endpoint definitions
- Request/response serialization
- Input validation via Pydantic
- Authentication middleware
- No business logic

### Layer 2: Application (app/pipelines/, app/services/)
- Orchestrates business operations
- Defines workflow sequences
- Manages transactions
- Coordinates between domain modules

### Layer 3: Business/Domain (app/feature_engineering/, app/ml/, app/graph/, app/tpke/, app/graphrag/, app/rca/)
- Core intelligence algorithms
- Feature computation
- ML training and prediction
- Knowledge Graph operations
- TPKE evolution logic
- GraphRAG reasoning
- Root cause analysis

### Layer 4: Infrastructure (app/database/, app/infrastructure/)
- Database connections
- File storage
- External service clients
- Caching

### Layer 5: Persistence (app/models/, app/repositories/)
- ORM model definitions
- CRUD operations
- Query building
- Data access abstraction

## Dependency Rule

Dependencies flow INWARD only:
- Presentation → Application → Business → Infrastructure → Persistence
- Inner layers NEVER depend on outer layers
- Business logic is independent of framework and database

## Service Communication

- Services communicate through well-defined interfaces
- No direct service-to-service database access
- All inter-service data passes through defined schemas
- Pipeline orchestrator coordinates multi-service workflows
