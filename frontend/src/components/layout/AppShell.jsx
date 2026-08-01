import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { api } from '../../api/client'
import Overview from '../../pages/Overview'
import DatasetOverview from '../../pages/DatasetOverview'
import ForecastPage from '../../pages/ForecastPage'
import GraphPage from '../../pages/GraphPage'
import RiskPage from '../../pages/RiskPage'
import LearningPage from '../../pages/LearningPage'
import EntityPage from '../../pages/EntityPage'
import ReportsPage from '../../pages/ReportsPage'
import AlertsPage from '../../pages/AlertsPage'
import { useSharedParams } from '../../hooks/useSharedParams'
import { useRealtimeSync } from '../../hooks/useRealtimeSync'
import { Bell, Database, Layers, Server, ShieldCheck, Home, ChevronRight } from 'lucide-react'

const PAGES = [
  {
    id: 'overview',
    path: '/',
    label: 'Dashboard',
    stage: 'Decision Support',
    source: 'Dashboard APIs',
    description: 'Executive view of forecast readiness, business risk and system health from backend APIs.',
  },
  {
    id: 'dataset',
    path: '/dataset',
    label: 'Dataset Management',
    stage: 'Feature Engineering',
    source: 'Processed Dataset',
    description: 'Explain how the historical supply chain dataset becomes AI-ready through cleaning, transformation and feature engineering.',
  },
  {
    id: 'forecast',
    path: '/forecast',
    label: 'Forecast & Multi-Agent Intelligence',
    stage: 'Multi-Agent AI',
    source: 'Forecast APIs',
    description: 'Review predicted demand, inventory, supplier and logistics outcomes from backend agents.',
  },
  {
    id: 'graph',
    path: '/graph',
    label: 'Knowledge Graph',
    stage: 'Knowledge Graph',
    source: 'Neo4j',
    description: 'Visualize the enterprise knowledge graph that stores business relationships and predictions.',
  },
  {
    id: 'risk',
    path: '/risk',
    label: 'Root Cause Analysis',
    stage: 'Root Cause',
    source: 'GraphRAG',
    description: 'Probe root causes and risk paths using graph reasoning and backend RCA services.',
  },
  {
    id: 'learning',
    path: '/learning',
    label: 'Learning Cycle',
    stage: 'Learning',
    source: 'Forecast + Actual Upload + TPKE',
    description: 'Close the loop with actual performance, TPKE graph evolution and knowledge learning.',
  },
]

const WORKFLOW_STEPS = [
  { id: 'dataset', label: 'Historical Dataset' },
  { id: 'feature', label: 'Feature Engineering' },
  { id: 'multiAgent', label: 'Multi-Agent AI' },
  { id: 'knowledgeGraph', label: 'Knowledge Graph' },
  { id: 'graphRAG', label: 'GraphRAG' },
  { id: 'rootCause', label: 'Root Cause' },
  { id: 'decision', label: 'Decision Support' },
  { id: 'learning', label: 'Learning' },
]

const PAGE_STAGE_MAP = {
  overview: 'decision',
  dataset: 'feature',
  forecast: 'multiAgent',
  graph: 'knowledgeGraph',
  risk: 'rootCause',
  learning: 'learning',
}

function WorkflowRibbon({ stage }) {
  const activeIndex = WORKFLOW_STEPS.findIndex(step => step.id === stage)
  return (
    <div className="workflow-ribbon">
      {WORKFLOW_STEPS.map((step, index) => (
        <div
          key={step.id}
          className={`workflow-step${index === activeIndex ? ' active' : index < activeIndex ? ' completed' : ''}`}
        >
          {step.label}
        </div>
      ))}
    </div>
  )
}

export default function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const { entityId, issueId } = useSharedParams()
  const { isConnected } = useRealtimeSync()

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health().then(r => r.data),
    refetchInterval: 30_000,
  })

  const forecastPeriodQuery = useQuery({
    queryKey: ['nextForecastPeriod'],
    queryFn: () => api.getNextForecastPeriod().then(r => r.data),
    refetchInterval: 60_000,
    retry: false,
  })

  const graphStatusQuery = useQuery({
    queryKey: ['graphStatus'],
    queryFn: () => api.getGraphStats().then(r => r.data),
    refetchInterval: 60_000,
    retry: false,
  })

  const modelsQuery = useQuery({
    queryKey: ['latestModels'],
    queryFn: () => api.getLatestModels().then(r => r.data),
    refetchInterval: 60_000,
    retry: false,
  })

  const alertsQuery = useQuery({
    queryKey: ['alertsSummary'],
    queryFn: () => api.getBusinessAlerts().then(r => r.data),
    refetchInterval: 60_000,
    retry: false,
  })

  const tpkeStatusQuery = useQuery({
    queryKey: ['tpkeStatus'],
    queryFn: () => api.getTpkeStatus().then(r => r.data),
    refetchInterval: 60_000,
    retry: false,
  })

  const currentPath = location.pathname
  const activePage = PAGES.find(p => p.path === currentPath) || PAGES[0]
  const activeStage = PAGE_STAGE_MAP[activePage.id] || 'decision'

  const healthStatus = healthQuery.data?.status || 'degraded'
  const graphStatus = graphStatusQuery.data?.total_nodes ? 'Online' : 'Initializing'
  const modelCount = Array.isArray(modelsQuery.data) ? modelsQuery.data.length : modelsQuery.data?.models?.length || 0
  const notificationCount = Array.isArray(alertsQuery.data) ? alertsQuery.data.length : alertsQuery.data?.alerts?.length || 0

  const handleNavClick = (path) => {
    navigate({ pathname: path, search: location.search })
  }

  const breadcrumbs = useMemo(() => {
    const list = [{ label: 'Home', path: '/' }]
    if (activePage.path !== '/') list.push({ label: activePage.label, path: activePage.path })
    if (entityId) {
      const name = entityId.replace(/^(supplier|product|warehouse|shipment|customer|order|event)[_-]/i, '').replace(/[_-]main$/i, '').replace(/[_-]/g, ' ')
      const entityLabel = name.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ')
      list.push({ label: entityLabel, path: '/entities' })
    }
    if (issueId && activePage.path === '/risk') {
      const issueLabel = issueId.replace(/[_-]/g, ' ').toUpperCase()
      list.push({ label: issueLabel, path: '/risk' })
    }
    return list
  }, [activePage, entityId, issueId])

  return (
    <div className="shell">
      <header className="header-bar">
        <div className="header-main">
          <div className="brand-section">
            <div className="brand-title">AMASCI Enterprise AI</div>
            <div className="brand-sub">Adaptive multi-agent supply chain decision support</div>
          </div>
          <div className="header-pill-group">
            <span className="status-pill"><Bell size={14} /> Forecast: {forecastPeriodQuery.data?.forecast_period || 'Pending'}</span>
            <span className="status-pill"><Database size={14} /> Graph: {graphStatus}</span>
            <span className="status-pill"><Layers size={14} /> Model: {modelCount > 0 ? `${modelCount} active` : 'Idle'}</span>
          </div>
        </div>
        <div className="header-actions">
          <span className="status-pill"><Server size={14} /> Health: {healthStatus}</span>
          <span className="status-pill"><ShieldCheck size={14} /> {notificationCount} notifications</span>
          <div className="user-circle">SC</div>
        </div>
      </header>

      <div className="content">
        <aside className="app-sidebar">
          <div className="sidebar-brand">AMASCI</div>
          <div className="sidebar-desc">Follow the enterprise AI pipeline from dataset to learning cycle.</div>
          <nav className="sidebar-nav">
            {PAGES.map(page => (
              <button
                key={page.id}
                className={`sidebar-link${currentPath === page.path ? ' active' : ''}`}
                onClick={() => handleNavClick(page.path)}
              >
                {page.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div className="footer-pill"><span>System health</span><strong>{healthStatus}</strong></div>
            <div className="footer-pill"><span>Forecast period</span><strong>{forecastPeriodQuery.data?.forecast_period || 'N/A'}</strong></div>
          </div>
        </aside>

        <main className="app-main">
          <div className="page-banner">
            <div>
              <div className="page-banner-title">{activePage.label}</div>
              <div className="page-banner-sub">{activePage.description}</div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
              <span className="page-banner-chip">Data Source: {activePage.source}</span>
              <span className="page-banner-chip">Pipeline Stage: {activePage.stage}</span>
            </div>
          </div>

          <div className="page-toolbar">
            <div className="breadcrumbs-row">
              {breadcrumbs.map((item, idx) => (
                <span key={idx} className="breadcrumb-item" onClick={() => handleNavClick(item.path)}>
                  {idx > 0 && <ChevronRight size={12} />} {item.label}
                </span>
              ))}
            </div>
          </div>

          <div className="page-content">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/dataset" element={<DatasetOverview />} />
              <Route path="/forecast" element={<ForecastPage />} />
              <Route path="/graph" element={<GraphPage />} />
              <Route path="/learning" element={<LearningPage />} />
              <Route path="/risk" element={<RiskPage />} />
              <Route path="/entities" element={<EntityPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>

          <WorkflowRibbon stage={activeStage} />
        </main>
      </div>

      <footer className="footer-bar">
        <div className="footer-status">
          <span>Backend Status</span>
          <span>FastAPI {healthStatus === 'healthy' ? '✓' : '⚠'}</span>
          <span>Neo4j {healthQuery.data?.services?.neo4j === 'healthy' ? '✓' : '⚠'}</span>
          <span>PostgreSQL {healthQuery.data?.services?.postgresql === 'healthy' ? '✓' : '⚠'}</span>
        </div>
        <div className="footer-status">
          <span>LightGBM {modelCount > 0 ? 'Active' : 'Offline'}</span>
          <span>GraphRAG {graphStatusQuery.data ? 'Ready' : 'Pending'}</span>
          <span>TPKE {tpkeStatusQuery.data?.status ? tpkeStatusQuery.data.status : 'Pending'}</span>
        </div>
      </footer>
    </div>
  )
}
