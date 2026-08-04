# Supply Chain Dashboard Redesigns — Complete Walkthrough

This document records the redesigns of the **Supply Chain Network**, **Risk & Root Cause**, and **Entity Intelligence** pages, and the integration of the **Intelligent Navigation Platform**, **Real-time Synchronization** engine, **Executive Reporting Center**, and **Business Alert Center**.

---

## 1. Supply Chain Network — Interactive Force-Directed Graph

A complete rewrite of [GraphPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/GraphPage.jsx) and [GraphPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/GraphPage.module.css).

```text
GraphPage
├── Header          (Neo4j status · node count · rel count · TPKE count · refresh)
│
├── LEFT (240px)    EntityExplorer
│   ├── Live entity counts from /graph/statistics
│   ├── Search + active-only filter
│   └── Per-type expand/collapse with schema relationships
│
├── CENTER          ForceGraphCanvas  (canvas 2D + requestAnimationFrame)
│   ├── Physics: spring + repulsion + center gravity + collision
│   ├── Nodes: colored circles, risk ring arc, TPKE dashed border, type label
│   ├── Edges: directional arrows, weight-scaled width, TPKE animated dashes
│   ├── Zoom/Pan: scroll wheel + drag canvas
│   └── Drag nodes: pin temporarily, release to unpin
│
├── RIGHT (300px)   EntityDetailPanel  (slides in on click)
│   ├── Tab 1 Overview: 4 KPIs · node properties · risk gauge + bar
│   ├── Tab 2 Relationships: live connections + schema connections with strength bars
│   └── Tab 3 Forecast: summary table · historical trend AreaChart
│
├── Resize divider  (drag to resize bottom panel)
│
└── BOTTOM          AnalyticsCharts
    ├── Tab: Analytics (7 charts in grid)
    └── Tab: Relationships (sortable/searchable/filterable table)
```

---

## 2. Risk & Root Cause — Incident Investigation Center

A complete rewrite of [RiskPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/RiskPage.jsx) and [RiskPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/RiskPage.module.css).

```text
RiskPage
├── Header          (Sync button · Active Incidents count · Exposure value · Audits count)
│
├── LEFT (300px)    Issue Queue
│   ├── Filter dropdowns (Severity, Status)
│   ├── Search input (Incident title, Region, Entity)
│   ├── Multi-field sorting (Risk Score, Date, Loss Exposure Value)
│   └── High-density list (Loss value, priority tag, status, severity, risk)
│
├── CENTER          Relationship Traversal Path
│   ├── Traversal visualization traversing: Supplier → Warehouse → Shipment → Product → Customer
│   ├── Active connections highlighted using dynamic active states and line color gradients
│   ├── Target/Critical indicators showing disruption propagation
│   └── Detailed Business Impact Indicators & Demand Forecast Impact KPIs
│
├── RIGHT (340px)   AI Root Cause Report
│   ├── Causal Timeline (Disruption initialized → risk limits crossed → AI Graph Audit → root cause mapped)
│   ├── RCA Confidence Level (high/medium status bar and mitigation success rate)
│   ├── Primary Root Cause description text
│   ├── Contributing Factors listing with percentage bars
│   ├── Recommendations checklist & milestones timeline
│   └── Graph Traversal audit trigger button
│
├── Resize divider  (drag to resize bottom panel)
│
└── BOTTOM          BI-Style Charts (7 charts in Tab bar)
    ├── Issue Contribution Chart (Exposure loss by issue type)
    ├── Root Cause Distribution (Incident count per category)
    ├── Risk Trend (Overall risk index timeline)
    ├── Affected Entity Distribution (Product, Supplier, Warehouse, Customer exposed)
    ├── Monthly Issue Trend (Line chart of active issues)
    ├── Forecast vs Actual (Actual accuracy vs target forecast)
    └── Business Impact (Radar chart showing exposed metrics)
```

---

## 3. Entity Intelligence — Power BI Executive Report

A complete rewrite of [EntityPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/EntityPage.jsx) and [EntityPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/EntityPage.module.css).

```text
EntityPage
│
├── LEFT (260px)    Entity Selector
│   ├── Entity Class Tabs: Supplier 🏭 | Warehouse 🏪 | Product 📦 | Shipment 🚚 | Customer 👤
│   ├── Instant search input
│   └── Scrollable lists populated from /graph/nodes (dynamic)
│
└── CENTER          Power BI Executive Report Canvas
    ├── Super Header (Active entity name, gauges for risk score & forecast accuracy)
    ├── KPI Blocks (Exposure val, lead delay days, graph connections count, SLA rating)
    ├── AI Recommendation Alert (Dynamic optimizing plans based on risk score)
    └── 8 BI-Style Charts (Grid Layout):
        ├── Performance Trend (Line chart of delay days)
        ├── Risk Trend (Area chart of risk components)
        ├── Forecast Trend (Actual demand vs predicted forecast)
        ├── Historical Trend (Historical order counts)
        ├── Relationship Distribution (Donut chart of supplier vs carrier vs retail links)
        ├── Connected Entities (Bar chart count per class type)
        ├── Business Impact (Radar chart of SLA risk, holding cost, volatility)
        └── Monthly Comparison (Bar chart of Current month vs Last month comparison)
```

---

## 4. Intelligent Navigation — Connected Investigation Platform

All pages are integrated into a **connected investigation platform** using React Router hash routing, keeping shared states synchronized in URL query parameters.

```text
[Overview]
  └── Click High Risk Alert
        └── [Entity Intelligence]
              └── Click "View Relationships"
                    └── [Supply Chain Network]
                          └── Click "Investigate Issue"
                                └── [Risk & Root Cause]
                                      └── Click "Explain Disruption"
                                            └── [Supply Chain Intelligence] (Auto Ask GraphRAG)
```

---

## 5. Real-time Synchronization Engine

Implemented a robust event-driven real-time synchronization architecture:

```text
[Backend: FastAPI Endpoints]
  ├── ws.py WebSocket broadcast router (/api/v1/ws)
  ├── data_engineering.py ──> Broadcasts: "Actual Uploaded" & "Forecast Validated" & "Knowledge Graph Updated"
  ├── ml/router.py ─────────> Broadcasts: "Forecast Generated"
  └── tpke/routes ──────────> Broadcasts: "TPKE Completed"
       │
       ▼ (Event Notification Broadcast)
[Frontend: React Hook (useRealtimeSync)]
  ├── Listens to active WS connection
  ├── On Event ──> Invalidate react-query cache keys (SUPPLY_CHAIN_QUERY_KEYS.all)
  └── UI Feedback ──> Toast message: "Database Sync: [Event]. Refreshing views..."
       │
       ▼ (Fallback Polling)
[React Query QueryClient Config]
  └── In App.jsx, configured refetchInterval: 15_000 (15 seconds poll fallback) & retry: 3
```

---

## 6. Executive Reporting Center

A new component page [ReportsPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/ReportsPage.jsx) and [ReportsPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/ReportsPage.module.css) dedicated to report composition, printing, and exporting:

```text
ReportsPage
├── LEFT (280px)    Sidebar
│   ├── Report selector (7 options: Business Summary, Forecast, Risk, Supplier, Warehouse, Entity, Incident)
│   └── Global Export Panel (Export PDF, Export Data Excel CSV)
│
└── CENTER          Report Document Canvas
    ├── Super Header (Report Title, Meta stats, Print/Export quick trigger buttons)
    └── Dynamic report area displaying KPIs, Recharts graphs (Pie, Line, Area, Radar, Bar), and tables
```

---

## 7. Business Alert Center

A dedicated monitoring and warning control board [AlertsPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/AlertsPage.jsx) and [AlertsPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/AlertsPage.module.css) with instant response controls:

```text
AlertsPage
├── Header          (Alert count badge · Refresh status trigger)
├── Toolbar         (Search bar · Category filter · Severity filter · Sorting parameters)
└── Alerts Grid     (High-density cards displaying alert details)
```

---

## 8. Safari Compatibility & Build Optimizations

- **Safari CSS Prefixes**: Implemented browser vendor prefixes (`-webkit-backdrop-filter` and `-webkit-user-select`) inside `GraphPage.module.css` to support visual transparency and selection handling in Safari and iOS web views.
- **JS-Driven compilation Config**: Configured `allowJs: true` and expanded the input matching path to `src/**/*` in `tsconfig.app.json` to properly compile purely JavaScript and JSX code bases using the TypeScript typechecker.

---

## 9. Forecast Center Redesign: Enterprise Planning Workspace

A complete redesign of [ForecastPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/ForecastPage.jsx) and [ForecastPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/ForecastPage.module.css) from a basic file upload panel into an **Enterprise Planning Workspace** modeled after Oracle Demand Planning Cloud and SAP IBP.

* **Automated Lifecycle Processing**: Ingesting actual sales data (via the top toolbar) automatically triggers the entire forecasting lifecycle pipeline: Ingestion ➔ Error Validation ➔ Recalculation ➔ Graph Mutation ➔ TPKE Inference Retraining. Operators see a real-time visual progress bar detailing active steps.
* **Planning scorecards**: Interactive KPIs displaying Forecast Accuracy, MAPE (Mean Error), RMSE/MAE, Forecast Bias, Operational Health Index, and Model Grounding Confidence.
* **Planning Grid**: Incorporates high-fidelity composed actuals vs forecast line charts, rolling 90-day trajectory lines, prediction error heatmaps, and regional accuracy profile selectors.
* **SKU Accuracy & Ingestion History**: Searchable sidebar panels displaying SKU level accuracy rankings and persistent ingestion logs tracking historic actual files.

---

## 10. Knowledge Graph Intelligence Workspace Redesign

A complete redesign of [IntelligencePage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/IntelligencePage.jsx) and [IntelligencePage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/IntelligencePage.module.css) into an **Enterprise Digital Twin Workspace** mapping the complete structural topology of the organization.

* **Historical month-by-month Replay**: Added a bottom player bar displaying months (Jul 2017 to Jan 2018). Scraping the timeline or pressing "Play" triggers dynamic risk and weight variations, animating relationship links and node color codes dynamically.
* **Power BI-style Entity Details**: Clicking any card opens a business intelligence panel showing:
  * Business Impact, Business Owner, Region, Grounded Confidence, Revenue Dependency.
  * Closeness, Betweenness, PageRank centralities.
  * Forecast Influence, Root Cause History, Recent TPKE Learning, and Historical Changes.
  * **GraphRAG Explainer**: LLM-grounded explanation box detailing topological significance.
* **Causal Traversal Engine**: Selecting any node traverses the graph topology using BFS to highlight Upstream Dependencies, Downstream Impacts, and Shortest Paths to Customers.

```text
IntelligencePage
├── Header          (Neo4j Status · Node/Rel Count · TPKE Version · confidence · health score)
│
├── LEFT (310px)    Searchable Entity Explorer
│   ├── Interactive search bar
│   ├── Node Type filters (Supplier, Warehouse, Product, etc.)
│   └── Risk level filters (High, Medium, Low)
│
├── CENTER          Power BI Model View Canvas (custom DOM + SVG overlay)
│   ├── Entities: DOM table cards styled by Type with risk/confidence/impact indicators
## 11. Root Cause Center Redesign: Executive AI Investigation Workspace

A complete redesign of [RiskPage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/RiskPage.jsx) and [RiskPage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/RiskPage.module.css) from a tabbed report page into a professional, guided 8-step Enterprise AI Investigation Workspace inspired by Oracle Fusion SCM, SAP IBP, Microsoft Fabric, and Palantir Foundry.

### Guided Main Workflow (8 Steps)

The page layout is structured as a step-by-step guided wizard driving the center pane, ensuring executives and analysts focus only on relevant context:
1. **STEP 1: Executive Summary** — Grounded AI Incident Briefing memo describing what happened, why, financial impact, affected entities, and prediction confidence.
2. **STEP 2: Business Impact** — High-fidelity 9-KPI dashboard showcasing Revenue Exposure, Delayed Orders, Affected SKUs, Regions, Delay Days, and Forecast drop.
3. **STEP 3: Evidence Ranking** — Interactive evidence cards outlining source type, description, confidence, and criticality level, with hovering/clicking highlights connected to the graph.
4. **STEP 5: Knowledge Graph** — SVG relationship visualization showing Supplier, Product, Warehouse, Shipment, and Customer cards. Features path tracing toggles: Upstream Path, Downstream Path, Shortest Path to Customer, and Critical Causal Line.
5. **STEP 5: Propagation Timeline** — Vertical disruption timeline tracking time offsets (T+0h to T+48h), severity dots, and localized financial impact shifts.
6. **STEP 6: Counterfactual Sim** — 6 sliders allowing perturbations on Supplier Delay, Warehouse Capacity, Inventory buffers, Demand, Transport delays, and Carrier capacity. Updates risk, forecast drop, delay, and recommended actions instantly.
7. **STEP 7: AI Copilot Briefing** — Detailed guide highlighting the right-docked LLM's GraphRAG capabilities and listing quick prompt options.
8. **STEP 8: Decision Center** — Recommendation cards showing expected savings, implementation cost, difficulty, time, risk, with operational approval toggles and PDF/PPT/JSON download options.

### Incident Overview Header

* Renders a large, multi-column dashboard card displaying Incident Name, Severity, Status, Started Time, Region, Affected Supplier/Warehouse, Exposure, Forecast Accuracy impact, and Prediction Source.

### Left Sidebar: Investigation Queue

* Replaces simple lists with high-fidelity status cards displaying left severity indicators (rose, orange, amber, green), current Risk Index, total Exposure, affected orders, grounded confidence, status tags, and time since detection. Clicking dynamically updates the entire workspace.

### Right Sidebar: Always-Docked AI Copilot

* The GraphRAG chatbot stays docked on the right margin, providing quick prompt chips, real-time query responses, and suggestions grounded strictly in Neo4j databases and temporal learning history.
Confidence/Consequences
3. **Impact Assessment** — 8 KPI dashboard: Revenue, Orders, Customers, Warehouses, Products, Supplier Risk, Forecast Degradation, Financial Exposure + Recovery Timeline bar
4. **Evidence Ranking** — Clickable matrix with synchronized graph highlighting
5. **Knowledge Graph** — SVG relationship map with reasoning accordion
6. **Propagation Timeline** — Animated vertical timeline (T+0h → T+48h) with severity dots
7. **Counterfactual Simulation** — 5 interactive sliders (Supplier Delay, Warehouse Capacity, Transport Delay, Inventory Buffer, Demand Level) + live recalculated outcomes
9. **Recommendations** — Optimal action card + executive approval directive
10. **Decision Export** — TPKE learned edges + JSON download

The 12-stage AI pipeline is now available inside a **collapsible "Investigation Progress" drawer** via the header button.

---

## 12. Knowledge Intelligence Redesign: Enterprise Digital Twin Workspace (Light Theme)

A complete redesign of [IntelligencePage.jsx](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/IntelligencePage.jsx) and [IntelligencePage.module.css](file:///c:/Users/balan/OneDrive/Desktop/supply-chain/frontend/src/pages/IntelligencePage.module.css) from a graph viewer into a high-fidelity Light Theme Enterprise Digital Twin platform.

**Design inspirations**: Microsoft Power BI Model View, Neo4j Bloom, Oracle Fusion SCM Digital Twin, Microsoft Fabric Lineage View, Palantir Foundry.

### Light Relationship Canvas

* **Soft Grey Dot-Matrix Pattern Canvas** (`#f8fafc` background with `#e2e8f0` grid dots) providing a highly clean, commercial look.
* **White Entity Cards** with clear border outlines (`#cbd5e1`) and soft drop shadows (`0 4px 12px rgba(0,0,0,0.05)`).
* **Causal Traversal Engine**: Selecting any node automatically traverses the topology (using BFS queues) to highlight:
  * **Upstream Dependencies** (highlighted in Yellow: `#eab308`)
  * **Downstream Impacts** (highlighted in Orange: `#f97316`)
  * **Shortest Path to Customer** (highlighted in Emerald Green: `#10b981`)
* **Animated Directed Edges** displaying weight flow speed based on confidence, relationship type, and traversal role (Upstream/Downstream/Shortest Path).
* **Tooltip Overlays** showing type, direction, confidence, weight, risk level, and business impact.
* Interactivity including pan, zoom, drag, node click focusing, and neighbor expansion/collapsing.

### Entity Cards (Power BI–style)

* **Status indicator bar** — 3px top bar colored by risk level (rose/amber/emerald)
* **Operational status badge** — "At Risk", "Warning", "Operational"
* **Core metrics row** — Risk %, Prediction %, Impact % displayed inline
* **Expandable properties** — Double-click to expand/collapse additional attributes
* **Primary key footer** — Node ID with expand chevron
* 10 entity types: Supplier, Warehouse, Product, Shipment, Customer, Carrier, Region, Order, Department, Store


### left Sidebar (Entity Explorer Slicers)

* Search bar for filtering by IDs or properties.
* **Entity Type pills**: Slicers for all 10 types.
* **Risk Level pills**: High, Medium, Low.
* **Prediction selector**: High/Low confidence filter.
* **Criticality selector**: Critical, High, Medium, Low.

### Entity Intelligence Dashboard (Right Panel)

* **Profile header** with risk chip and entity icon
* **Quick KPI strip** — Risk, Prediction, Centrality, Links (4 metrics)
* **Risk progress bar** with color-coded fill
* 5 tabs: **Overview** (attributes), **Links** (connected entities, Critical dependency flow), **Centrality** (betweenness, closeness, PageRank, recent changes), **TPKE History** (Line and Bar charts showing confidence evolution), **Trend & Forecast** (Area chart for Risk Index history, Forecast influence meter)

### Digital Twin Simulation Panel (Right Panel Tab)

* **5 adjustable parameters**: Supplier Delay, Warehouse Capacity, Inventory Buffer, Transport Delay, Demand Level
* **Live client-side topology recalculation** — Node Risk, Prediction Confidence, Affected Nodes, Risk Delta
* **Server simulation** — Sends perturbations to `/api/v1/rca/counterfactual`
* **Reset button** to restore baseline

### Knowledge Analytics (Bottom Panel Tab)

* **Relationship Distribution** — Bar chart of relationship types.
* **Node Degree Distribution** — Bar chart by entity type.
* **Edge Confidence Distribution** — Area chart mapping count vs confidence groups.
* **Centrality Ranking** — Top 5 nodes by betweenness/closeness.
* **Community Detection** — Pie chart of node communities.
* **Knowledge Growth** — Line chart showing node and edge counts over quarters.
* **Risk Heatmap** — Heatmap grid displaying nodes by risk color.
* **Knowledge Coverage** — Pie chart showing Grounded vs TPKE Inferred data.
* **Business Impact Distribution** — Radar chart displaying structural metrics (Density, Health, Connectivity).
* **Structural Metrics** — Clustering coefficient, components, average degree.

### Graph Replay Timeline (Bottom Panel Tab)

* 9 stages: Forecast Generated → Prediction → Actual Upload → Validation → Root Cause → TPKE Learning → Graph Mutation → Retraining → Next Forecast
* **Playback animation** at 1.5s intervals with Play/Pause controls
* **Click-to-seek** to any stage

### Relationship Explorer (Bottom Panel Tab)

* 9 columns: Source Entity, Relationship Type, Target Entity, Weight, Confidence, TPKE Status, Risk Level, Supporting Evidence, Temporal Evolution.
* **Color-coded badges** for relationship types.

### Offline Fallback

* **16 nodes** (incorporating Store, Carrier, Department, Region)
* **17 edges** with detailed weights and confidence

```text
Digital Twin Workspace (Light Theme)
├── Header (Enterprise Digital Twin · Neo4j status · KG version · Health score · Live Sync)
└── Body (Flex: 3-column)
    ├── LEFT (280px): Entity Explorer (Search + 10 Type Slicers + Risk + Pred + Crit Selectors)
    │
    ├── CENTER (flex): Digital Twin Canvas (Light Canvas with dot-grid pattern)
    │   ├── Toolbar (8 layer pills · Trace · Zoom · Reset · Legend · Bottom toggle)
    │   ├── Viewport (pan/zoom/drag canvas)
    │   │   ├── SVG Edge Layer (curved, animated, labeled)
    │   │   ├── HTML Card Layer (Power BI cards with status bars)
    │   │   ├── Legend Overlay (entities + relationships)
    │   │   ├── Minimap Overlay
    │   │   └── Relationship Tooltip (direction, weight, confidence, TPKE, impact)
    │   └── Bottom Panel (220px, collapsible)
    │       ├── Tab: Graph Replay Timeline (9 stages + Play/Pause)
    │       ├── Tab: Relationship Explorer (9-column table)
    │       └── Tab: Knowledge Analytics (10 chart cards)
    │
    └── RIGHT (320px): Intelligence Panels
        ├── Tab: Entity Intelligence Dashboard
        │   ├── Profile header + Quick KPI strip + Risk bar
        │   └── 5 sub-tabs: Overview / Links / Centrality / TPKE / Trend & Forecast
        └── Tab: Digital Twin Simulation
            ├── 5 parameter sliders
            ├── Live topology recalculation grid (4 KPIs)
            ├── Server simulation button
            └── Server result display
```

---

## 8. Enterprise Architecture Audit & Continuous Learning Pipeline

### Verified Enterprise Workflow (12 Core Components)

```text
Historical DataCo Dataset
       ↓
Feature Engineering (22 Features + Lags + Rolling Stats + Trend + Seasonality + Momentum)
       ↓
Knowledge Graph Construction (Neo4j Multi-Layer Nodes & Relationships)
       ↓
TPKE Initialization (Temporal Pattern Knowledge Engine)
       ↓
GraphRAG Index Creation (Context Embeddings & Retrieval Cache)
       ↓
Multi-Agent Memory Initialization (Demand, Supplier, Inventory, Logistics Agents)
       ↓
LightGBM Training (DemandTrainer, SupplierTrainer, InventoryTrainer, LogisticsTrainer)
       ↓
Enterprise Forecast Generation (Collaborative Consensus Forecast)
       ↓
Waiting for Monthly Actual Dataset
       ↓
Actual Dataset Arrival (January 2019 CSV Ingestion)
       ↓
Automatic Continuous Learning Pipeline (12-Stage Automated ECLE Engine)
       ↓
Predict Next Month (February 2019 Forecast Auto-Generation)
```

### Component Audit Summary

1. **Historical Dataset Expansion**: `processed_master.parquet` is expanded cumulatively (`df_old + df_new`), preserving historical memory while expanding timeline (`2015-2018_v1` → `2015-2019-01_v2`).
2. **Feature Engineering**: Recalculates 22 engineered features plus explicit time-series lag features (`demand_lag_1m`, `demand_lag_3m`, `supplier_delay_lag_1m`), rolling statistics (`demand_rolling_mean_3m`, `demand_rolling_std_3m`, `delay_rolling_mean_3m`), trend, seasonality index, and momentum.
3. **Machine Learning Retraining**: `TrainingOrchestrator` retrains LightGBM models on the expanded ground truth dataset, updating `ModelRegistry` versions and confidence metrics.
4. **Knowledge Graph Mutation**: `ActualIntegrationLayer` mutates node properties (`actual_demand`, `actual_delay_days`, `actual_late_delivery`), updates relationship weights, inserts newly discovered entities, and recalculates PageRank/Degree centrality, dependency scores, and business impact scores on Neo4j without rebuilding the graph.
5. **TPKE Evolution**: `TPKEEngine` detects temporal patterns (sliding window W, frequency K, confidence θ), creates/strengthens `:TPKE_CAUSES` edges, and decays inactive relationships.
6. **GraphRAG Re-Indexing**: `ContextBuilderService` and `EnterpriseGraphRAGPipeline` refresh graph embeddings, clear retrieval caches, and preserve historical context.
7. **Multi-Agent Intelligence**: 4 Enterprise BI Decision Agents (`Demand Planning Agent`, `Supplier Intelligence Agent`, `Inventory & Warehouse Agent`, `Logistics & Transportation Agent`) retrieve context from GraphRAG & Knowledge Graph metrics and log execution history in agent memory (`app.ml.agent_memory`).
8. **RWDAA Adaptive Allocation**: Recurrent Weight Dynamic Adaptive Allocation computes dynamic agent weights based on historical accuracy/MAPE/RMSE metrics.
9. **Forecast Center**: `ForecastPage.jsx` auto-refreshes forecast cards, prediction charts, actual vs predicted dashboards, KPI metrics, disruption drivers, confidence intervals, and immediate next-month predictions (`February 2019`).
10. **Root Cause Center**: `RiskPage.jsx` & `rca_investigation.py` automatically register completed months as historical incidents, map relationship traversal paths, and compute counterfactual recommendations.
11. **Knowledge Intelligence**: `IntelligencePage.jsx` & `GraphPage.jsx` update Digital Twin topology, relationship strengths, PageRank centrality, dependency maps, and risk heatmaps.
12. **System Synchronization**: `useRealtimeSync.js` subscribes to WebSockets (`/ws`). Any `Continuous Learning Completed` or `Actual Uploaded` broadcast invalidates React Query caches, automatically updating all 10 frontend pages simultaneously from the single enterprise data source.


