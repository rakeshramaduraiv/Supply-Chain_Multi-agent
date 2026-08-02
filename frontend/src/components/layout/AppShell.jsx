import { useEffect, useMemo, useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { api } from '../../api/client'
import Overview from '../../pages/Overview'
import ForecastPage from '../../pages/ForecastPage'
import GraphPage from '../../pages/GraphPage'
import IntelligencePage from '../../pages/IntelligencePage'
import RiskPage from '../../pages/RiskPage'
import EntityPage from '../../pages/EntityPage'
import ReportsPage from '../../pages/ReportsPage'
import { useSharedParams } from '../../hooks/useSharedParams'
import { useRealtimeSync } from '../../hooks/useRealtimeSync'
import { ChevronRight, Home, Bell, X, Trash2, AlertTriangle, AlertCircle, CheckCircle, Info, Brain } from 'lucide-react'
import { useBusinessAlerts, SUPPLY_CHAIN_QUERY_KEYS } from '../../hooks/useSupplyChainData'

import Logo from '../ui/Logo'
import EnterpriseCopilot from '../domain/EnterpriseCopilot'

const PAGES = [
  { id: 'overview',     path: '/',             label: 'Live Operations' },
  { id: 'forecast',     path: '/forecast',     label: 'Forecast Center' },
  { id: 'risk',         path: '/risk',         label: 'Root Cause Center' },
  { id: 'graph',        path: '/graph',        label: 'Knowledge Intelligence' },
  { id: 'reports',      path: '/reports',      label: 'System & Reports' },
]

export default function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { entityId, issueId, navigateToPage } = useSharedParams()
  const { isConnected } = useRealtimeSync()
  const alertsQuery = useBusinessAlerts()
  const alertsList = alertsQuery.data?.alerts || []
  const alertCount = alertsList.length
  const [bellOpen, setBellOpen] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const bellRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    if (!bellOpen) return
    const handler = (e) => { if (bellRef.current && !bellRef.current.contains(e.target)) setBellOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [bellOpen])

  const dismissMut = useMutation({
    mutationFn: (id) => api.dismissBusinessAlert(id).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.alerts }),
  })

  const SEV_ICON = { Critical: AlertTriangle, High: AlertCircle, Medium: Info, Low: CheckCircle }
  const SEV_COLOR = { Critical: '#d63031', High: '#e67e22', Medium: '#0984e3', Low: '#00b894' }

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
    navigate({ pathname: path, search: location.search })
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
        <Logo size="sm" onClick={() => handleNavClick('/')} style={{ cursor: 'pointer' }} />
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
          <div ref={bellRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setBellOpen(o => !o)}
              style={{
                position: 'relative', background: bellOpen ? 'var(--s2)' : 'none',
                border: 'none', cursor: 'pointer', padding: '4px 6px',
                display: 'flex', alignItems: 'center',
                color: 'var(--ts)', borderRadius: 5,
              }}
              title="Notifications"
            >
              <Bell size={16} />
              {alertCount > 0 && (
                <span style={{
                  position: 'absolute', top: 1, right: 1,
                  background: '#d63031', color: '#fff', borderRadius: '50%',
                  width: 13, height: 13, fontSize: 7, fontWeight: 800,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>{alertCount > 99 ? '99+' : alertCount}</span>
              )}
            </button>

            {/* Dropdown panel — outside the button to avoid nesting */}
            {bellOpen && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 8px)', right: 0,
                width: 340, maxHeight: 420, overflowY: 'auto',
                background: 'var(--s0)', border: '1px solid var(--b)',
                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                zIndex: 9999, color: 'var(--tp)',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', borderBottom: '1px solid var(--b)',
                  background: 'var(--s1)',
                }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)' }}>Notifications</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {alertCount > 0 && (
                      <span style={{ fontSize: 9, padding: '1px 7px', borderRadius: 10, background: 'rgba(214,48,49,0.1)', color: '#d63031', fontWeight: 700, border: '1px solid rgba(214,48,49,0.2)' }}>
                        {alertCount} active
                      </span>
                    )}
                    <button onClick={() => setBellOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tm)', display: 'flex' }}>
                      <X size={13} />
                    </button>
                  </div>
                </div>

                {alertsQuery.isLoading ? (
                  <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--tm)' }}>Loading…</div>
                ) : alertsList.length === 0 ? (
                  <div style={{ padding: 24, textAlign: 'center', fontSize: 11, color: 'var(--tm)' }}>
                    <CheckCircle size={20} style={{ color: 'var(--rl)', marginBottom: 6, display: 'block', margin: '0 auto 6px' }} />
                    All systems clear
                  </div>
                ) : (
                  alertsList.slice(0, 12).map(alert => {
                    const SevIcon = SEV_ICON[alert.severity] || Info
                    const color = SEV_COLOR[alert.severity] || '#868e96'
                    return (
                      <div key={alert.id} style={{
                        padding: '10px 14px', borderBottom: '1px solid var(--b)',
                        cursor: 'pointer', transition: 'background 0.1s',
                      }}
                        onMouseEnter={e => e.currentTarget.style.background = 'var(--s1)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                        onClick={() => {
                          setBellOpen(false)
                          navigateToPage('/risk', { issueId: alert.issue_id, entityId: alert.entity_id })
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9 }}>
                          <SevIcon size={13} style={{ color, flexShrink: 0, marginTop: 1 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--tp)', marginBottom: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {alert.name}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--ts)', lineHeight: 1.4 }}>{alert.business_impact}</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                              <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: `${color}14`, color, fontWeight: 700, border: `1px solid ${color}30` }}>
                                {alert.severity}
                              </span>
                              <span style={{ fontSize: 9, color: 'var(--tm)' }}>{alert.type}</span>
                            </div>
                          </div>
                          <button
                            onClick={e => { e.stopPropagation(); dismissMut.mutate(alert.id) }}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tm)', flexShrink: 0, padding: 2 }}
                            title="Dismiss"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => setCopilotOpen(o => !o)}
            className="btn btn-secondary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '5px', marginRight: '6px', cursor: 'pointer' }}
          >
            <Brain size={13} /> AI Copilot
          </button>
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
            <Route path="/forecast"     element={<ForecastPage />} />
            <Route path="/graph"        element={<IntelligencePage />} />
            <Route path="/risk"         element={<RiskPage />} />
            <Route path="/entities"     element={<EntityPage />} />
            <Route path="/reports"      element={<ReportsPage />} />
            {/* Fallback */}
            <Route path="*"             element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>

      {/* Enterprise AI Investigation Copilot Drawer */}
      <EnterpriseCopilot
        isOpen={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        entityId={entityId}
      />
    </div>
  )
}
