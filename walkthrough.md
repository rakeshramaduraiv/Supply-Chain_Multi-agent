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
