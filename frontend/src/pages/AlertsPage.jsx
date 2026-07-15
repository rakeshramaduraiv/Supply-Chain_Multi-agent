import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useBusinessAlerts, SUPPLY_CHAIN_QUERY_KEYS } from '../hooks/useSupplyChainData'
import { useSharedParams } from '../hooks/useSharedParams'
import {
  Bell, Search, Filter, ArrowUpDown, Trash2, ShieldAlert,
  GitBranch, Layers, Eye, RefreshCw, AlertTriangle, AlertCircle, Info, CheckCircle
} from 'lucide-react'
import styles from './AlertsPage.module.css'

export default function AlertsPage() {
  const queryClient = useQueryClient()
  const { navigateToPage } = useSharedParams()
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('')
  const [sortBy, setSortBy] = useState('severity') // 'severity', 'type', 'name'

  // Fetch live alerts
  const alertsQuery = useBusinessAlerts()
  const alertsData = alertsQuery.data || {}
  const alertsList = alertsData.alerts || []

  // Dismiss mutation
  const dismissMut = useMutation({
    mutationFn: (id) => api.dismissBusinessAlert(id).then(r => r.data),
    onSuccess: () => {
      // Invalidate query to trigger refresh
      queryClient.invalidateQueries({ queryKey: SUPPLY_CHAIN_QUERY_KEYS.alerts })
    }
  })

  // Filter & Sort
  const processedAlerts = useMemo(() => {
    let result = [...alertsList]

    // Search
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(a =>
        a.name.toLowerCase().includes(q) ||
        a.business_impact.toLowerCase().includes(q) ||
        a.affected_entities.toLowerCase().includes(q)
      )
    }

    // Filter Type
    if (filterType) {
      result = result.filter(a => a.type === filterType)
    }

    // Filter Severity
    if (filterSeverity) {
      result = result.filter(a => a.severity === filterSeverity)
    }

    // Sort
    const severityWeight = { Critical: 4, High: 3, Medium: 2, Low: 1 }
    result.sort((a, b) => {
      if (sortBy === 'severity') {
        return (severityWeight[b.severity] || 0) - (severityWeight[a.severity] || 0)
      } else if (sortBy === 'type') {
        return a.type.localeCompare(b.type)
      } else {
        return a.name.localeCompare(b.name)
      }
    })

    return result
  }, [alertsList, search, filterType, filterSeverity, sortBy])

  // Handlers
  const handleDismiss = (id, e) => {
    e.stopPropagation()
    dismissMut.mutate(id)
  }

  const handleInvestigate = (alert) => {
    navigateToPage('/risk', { issueId: alert.issue_id, entityId: alert.entity_id })
  }

  const handleViewRelationships = (alert, e) => {
    e.stopPropagation()
    navigateToPage('/graph', { entityId: alert.entity_id })
  }

  const handleOpenEntity = (alert, e) => {
    e.stopPropagation()
    navigateToPage('/entities', { type: alert.entity_type, entityId: alert.entity_id })
  }

  return (
    <div className="page active" style={{ height: 'calc(100vh - 44px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      
      {/* Header */}
      <div className={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className={styles.bellWrap}>
            <Bell size={16} className={styles.bellIcon} />
            {alertsList.length > 0 && <span className={styles.badgeCount}>{alertsList.length}</span>}
          </div>
          <div>
            <h2 className={styles.title}>Business Alert Center</h2>
            <div className={styles.subtitle}>Real-time monitoring of supply chain exceptions, risks, and anomalies</div>
          </div>
        </div>

        <button className="btn btn-secondary btn-sm" onClick={() => alertsQuery.refetch()}>
          <RefreshCw size={11} className={alertsQuery.isFetching ? styles.spinning : ''} />
          Refresh
        </button>
      </div>

      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <Search size={12} className={styles.searchIcon} />
          <input
            className={styles.searchBar}
            placeholder="Search alerts by name, entities or impact…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <div className={styles.filters}>
          <div className={styles.filterGroup}>
            <Filter size={11} style={{ color: 'var(--tm)' }} />
            <select className={styles.select} value={filterType} onChange={e => setFilterType(e.target.value)}>
              <option value="">All Categories</option>
              <option value="Logistics">Logistics</option>
              <option value="Supplier">Supplier</option>
              <option value="Inventory">Inventory</option>
              <option value="Demand">Demand</option>
            </select>
          </div>

          <div className={styles.filterGroup}>
            <select className={styles.select} value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}>
              <option value="">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>

          <div className={styles.filterGroup}>
            <ArrowUpDown size={11} style={{ color: 'var(--tm)' }} />
            <select className={styles.select} value={sortBy} onChange={e => setSortBy(e.target.value)}>
              <option value="severity">Sort by Severity</option>
              <option value="type">Sort by Category</option>
              <option value="name">Sort by Name</option>
            </select>
          </div>
        </div>
      </div>

      {/* Content Canvas */}
      <div className={styles.content}>
        {alertsQuery.isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 20 }}>
            {[...Array(3)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 120, borderRadius: 8 }} />
            ))}
          </div>
        ) : processedAlerts.length === 0 ? (
          <div className={styles.emptyState}>
            <CheckCircle size={32} style={{ color: 'var(--rl)', marginBottom: 12 }} />
            <h4>All Systems Clear</h4>
            <p>No active operational risk alerts detected in your supply chain network.</p>
          </div>
        ) : (
          <div className={styles.alertsGrid}>
            {processedAlerts.map(alert => {
              const sevClass = alert.severity === 'Critical' ? styles.sevCritical
                             : alert.severity === 'High' ? styles.sevHigh
                             : alert.severity === 'Medium' ? styles.sevMed
                             : styles.sevLow

              return (
                <div key={alert.id} className={`${styles.alertCard} ${sevClass}`} onClick={() => handleInvestigate(alert)}>
                  {/* Left tag & Header */}
                  <div className={styles.cardHeader}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className={`badge ${alert.severity === 'Critical' || alert.severity === 'High' ? 'bdg-high' : 'bdg-med'}`}>
                        {alert.severity}
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--tm)', fontWeight: 600, textTransform: 'uppercase' }}>
                        {alert.type} Alert
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className={styles.iconBtn} onClick={(e) => handleOpenEntity(alert, e)} title="Open Entity Report">
                        <Layers size={11} />
                      </button>
                      <button className={styles.iconBtn} onClick={(e) => handleViewRelationships(alert, e)} title="View Relationships">
                        <Eye size={11} />
                      </button>
                      <button className={styles.iconBtn} onClick={(e) => handleDismiss(alert.id, e)} title="Dismiss Alert">
                        <Trash2 size={11} style={{ color: 'var(--rh)' }} />
                      </button>
                    </div>
                  </div>

                  <h3 className={styles.alertName}>{alert.name}</h3>

                  {/* Impact detail columns */}
                  <div className={styles.detailRow}>
                    <div className={styles.detailCol}>
                      <span className={styles.colLabel}>Business Impact</span>
                      <span className={styles.colText}>{alert.business_impact}</span>
                    </div>
                    <div className={styles.detailCol}>
                      <span className={styles.colLabel}>Affected Entities</span>
                      <span className={styles.colText} style={{ fontWeight: 600, color: 'var(--tp)' }}>{alert.affected_entities}</span>
                    </div>
                  </div>

                  <div className={styles.detailRow} style={{ borderTop: '1px solid var(--b)', paddingTop: 8, marginTop: 8 }}>
                    <div className={styles.detailCol}>
                      <span className={styles.colLabel}>Recommendation</span>
                      <span className={styles.colText}>{alert.recommendation}</span>
                    </div>
                    <div className={styles.detailCol}>
                      <span className={styles.colLabel}>Forecast Impact</span>
                      <span className={styles.colText} style={{ color: 'var(--rh)', fontWeight: 500 }}>{alert.forecast_impact}</span>
                    </div>
                  </div>

                  {/* Action Link Footer */}
                  <div className={styles.cardFooter}>
                    <span className={styles.footerLink}>
                      <GitBranch size={10} />
                      Click card to run AI Root Cause traversal
                    </span>
                    <span style={{ fontSize: 9, color: 'var(--tm)' }}>
                      Detected {alert.created_at?.slice(11, 16)} UTC
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
