import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { api } from '../../api/client'
import Overview from '../../pages/Overview'
import DatasetOverview from '../../pages/DatasetOverview'
import ForecastPage from '../../pages/ForecastPage'
import GraphPage from '../../pages/GraphPage'
import RiskPage from '../../pages/RiskPage'
import EntityPage from '../../pages/EntityPage'
import IntelligencePage from '../../pages/IntelligencePage'
import ReportsPage from '../../pages/ReportsPage'
import AlertsPage from '../../pages/AlertsPage'
import { useSharedParams } from '../../hooks/useSharedParams'
import { useRealtimeSync } from '../../hooks/useRealtimeSync'
import { ArrowRight, ChevronRight, Home, ShieldAlert } from 'lucide-react'

const PAGES = [
  { id: 'overview',     path: '/',             label: 'Overview' },
  { id: 'dataset',      path: '/dataset',      label: 'Dataset' },
  { id: 'forecast',     path: '/forecast',     label: 'Forecast' },
  { id: 'graph',        path: '/graph',        label: 'Supply Chain Network' },
  { id: 'intelligence', path: '/intelligence', label: 'Supply Chain Intelligence' },
  { id: 'risk',         path: '/risk',         label: 'Risk & Root Cause' },
  { id: 'entities',     path: '/entities',     label: 'Entities' },
  { id: 'reports',      path: '/reports',      label: 'Executive Reports' },
  { id: 'alerts',       path: '/alerts',       label: 'Alerts' },
]

export default function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const { entityId, issueId } = useSharedParams()
  const { isConnected } = useRealtimeSync()

  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health().then(r => r.data),
    refetchInterval: 30_000,
  })

  const apiStatus = healthData ? 'ok' : 'error'

  // Determine current active section id from path
  const currentPath = location.pathname
  const activePage = PAGES.find(p => p.path === currentPath) || PAGES[0]

  const handleNavClick = (path) => {
    // Navigate carrying over the active search parameters (deep linking)
    navigate({
      pathname: path,
      search: location.search
    })
  }

  // Dynamic Breadcrumbs
  const breadcrumbs = useMemo(() => {
    const list = [{ label: 'Home', path: '/' }]
    if (activePage.path !== '/') {
      list.push({ label: activePage.label, path: activePage.path })
    }
    if (entityId) {
      // Decode and add entity chip
      const name = entityId.replace(/^(supplier|product|warehouse|shipment|customer|order|event)[_-]/i, '').replace(/[_-]main$/i, '').replace(/[_-]/g, ' ')
      const entityLabel = name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')
      list.push({ label: entityLabel, path: `/entities` })
    }
    if (issueId && activePage.path === '/risk') {
      const issueLabel = issueId.replace(/[_-]/g, ' ').toUpperCase()
      list.push({ label: issueLabel, path: `/risk` })
    }
    return list
  }, [activePage, entityId, issueId])

  return (
    <div className="shell">
      <div className="topbar">
        <div className="logo" onClick={() => handleNavClick('/')} style={{ cursor: 'pointer' }}>
          AMASCI <em>Phase 1</em>
        </div>
        <nav className="nav">
          {PAGES.map(p => (
            <button
              key={p.id}
              className={`nav-btn${currentPath === p.path ? ' active' : ''}`}
              onClick={() => handleNavClick(p.path)}
            >
              {p.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <div className="topbar-status" style={{ marginRight: '8px' }}>
            <span className={`status-dot ${isConnected ? 'ok' : 'warn'} pulse`} style={{ background: isConnected ? '#00b894' : '#e67e22' }} />
            {isConnected ? 'Sync: Real-time' : 'Sync: Polling'}
          </div>
          <div className="topbar-status">
            <span className={`status-dot ${apiStatus} pulse`} />
            {apiStatus === 'ok' ? 'System ready' : 'API offline'}
          </div>
          <div className="user-circle">SC</div>
        </div>
      </div>

      {/* Breadcrumbs Row */}
      <div style={{
        background: 'var(--s1)',
        borderBottom: '1px solid var(--b)',
        padding: '6px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '10.5px',
        color: 'var(--tm)',
        zIndex: 5,
        minHeight: '26px'
      }}>
        {breadcrumbs.map((b, idx) => (
          <span key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              onClick={() => handleNavClick(b.path)}
              style={{
                cursor: 'pointer',
                fontWeight: idx === breadcrumbs.length - 1 ? 600 : 400,
                color: idx === breadcrumbs.length - 1 ? 'var(--tp)' : 'var(--ts)',
              }}
            >
              {idx === 0 ? <Home size={10} style={{ verticalAlign: '-1px' }} /> : b.label}
            </span>
            {idx < breadcrumbs.length - 1 && <ChevronRight size={10} style={{ color: 'var(--bs)' }} />}
          </span>
        ))}
      </div>

      <div className="shell-body">
        <div className="main">
          <Routes>
            <Route path="/"             element={<Overview />} />
            <Route path="/dataset"      element={<DatasetOverview />} />
            <Route path="/forecast"     element={<ForecastPage />} />
            <Route path="/graph"        element={<GraphPage />} />
            <Route path="/intelligence" element={<IntelligencePage />} />
            <Route path="/risk"         element={<RiskPage />} />
            <Route path="/entities"     element={<EntityPage />} />
            <Route path="/reports"      element={<ReportsPage />} />
            <Route path="/alerts"       element={<AlertsPage />} />
            {/* Fallback */}
            <Route path="*"             element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
