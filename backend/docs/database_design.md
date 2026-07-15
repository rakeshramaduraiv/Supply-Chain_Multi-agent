# AMASCI Database Design

## Dual Database Strategy

### PostgreSQL — Relational/Transactional Data
- Uploaded datasets (raw, cleaned, features)
- ML model metadata and predictions
- Forecast results and comparisons
- Pipeline execution logs
- TPKE evolution audit trail
- User accounts and sessions
- System configuration

### Neo4j — Graph/Relationship Data
- Supply chain entity nodes (Supplier, Product, Warehouse, etc.)
- Operational relationships (SUPPLIES, SHIPS_VIA, etc.)
- Risk scores as node properties
- TPKE-inferred edges with confidence scores
- Graph analytics results (centrality, communities)

## Synchronization Strategy

PostgreSQL is the **source of truth** for all computed data.
Neo4j is **derived** from PostgreSQL data.

Flow:
1. Data enters via PostgreSQL (upload → clean → features → predictions)
2. Graph Builder reads from PostgreSQL and writes to Neo4j
3. TPKE reads temporal patterns from PostgreSQL, writes new edges to Neo4j
4. Graph analytics computed in Neo4j, results stored back in PostgreSQL
5. Dashboard reads aggregated data from PostgreSQL

## PostgreSQL Tables

| Table | Purpose |
|-------|---------|
| users | User accounts and roles |
| datasets | Dataset metadata and versions |
| raw_data | Uploaded raw records |
| cleaned_data | Cleaned records |
| feature_store | Engineered features (versioned) |
| predictions | ML prediction results |
| forecasts | Generated forecasts |
| comparisons | Forecast vs actual results |
| model_registry | Trained model metadata |
| pipeline_runs | Pipeline execution tracking |
| tpke_logs | TPKE evolution audit trail |
| graph_stats | KG statistics snapshots |
| audit_logs | System audit trail |

## Neo4j Node Types

| Node | Key Properties |
|------|---------------|
| Supplier | supplier_id, name, risk_score, fulfillment_rate |
| Product | product_id, name, category, risk_score, demand_variability |
| Warehouse | warehouse_id, region, risk_score, load_factor |
| Customer | customer_id, segment, risk_score, payment_risk |
| Order | order_id, date, risk_score, delay_ratio |
| Market | market_id, name, volatility_index, growth_momentum |
| Region | region_id, name, geographic_risk |
| Shipment | shipment_id, mode, velocity, cost_anomaly |

## Neo4j Relationship Types

| Relationship | From → To | Key Properties |
|-------------|-----------|---------------|
| SUPPLIES | Supplier → Product | volume, reliability, lead_time |
| STORED_IN | Product → Warehouse | quantity, turnover_rate |
| SHIPS_VIA | Order → Shipment | cost, delay_ratio |
| DELIVERED_TO | Order → Customer | satisfaction, on_time |
| PLACED | Customer → Order | frequency, value |
| CONTAINS | Order → Product | quantity, discount |
| LOCATED_IN | Warehouse → Region | — |
| BELONGS_TO | Region → Market | — |
| INFLUENCES | (TPKE-inferred) | confidence, frequency, temporal_score |
