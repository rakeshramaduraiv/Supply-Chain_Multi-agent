// src/pages/Neo4jPage.jsx
import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const LABEL_COLORS = {
  Supplier:      '#0072B2', Product:       '#009E73', Warehouse:     '#D55E00',
  Order:         '#CC79A7', Customer:      '#E69F00', Route:         '#56B4E9',
  SupplierRoute: '#F0E442', Inventory:     '#999999', Shipment:      '#000000',
  CalendarEvent: '#0072B2', TemporalPeriod:'#009E73',
}
const labelColor = (l) => LABEL_COLORS[l] || '#64748b'

const S = {
  page:    { minHeight: '100vh', background: '#f1f5f9', fontFamily: 'system-ui,-apple-system,sans-serif' },
  header:  { background: 'linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%)', padding: '20px 28px', boxShadow: '0 2px 12px rgba(0,0,0,.2)' },
  body:    { padding: '20px 28px', display: 'flex', gap: 18, flexWrap: 'wrap' },
  card:    { background: '#fff', borderRadius: 10, border: '1px solid #e2e8f0', boxShadow: '0 1px 4px rgba(0,0,0,.05)', overflow: 'hidden' },
  cardHdr: { padding: '11px 16px', borderBottom: '1px solid #f1f5f9', background: '#fafafa', fontSize: 12, fontWeight: 700, color: '#334155' },
  badge:   (color) => ({ display: 'inline-block', padding: '2px 8px', borderRadius: 12, fontSize: 10, fontWeight: 700, background: `${color}18`, color, border: `1px solid ${color}30` }),
  propRow: { display: 'flex', gap: 6, padding: '4px 0', borderBottom: '1px solid #f8fafc', fontSize: 11, flexWrap: 'wrap' },
  propKey: { color: '#94a3b8', minWidth: 120, flexShrink: 0 },
  propVal: { color: '#1e293b', fontFamily: 'monospace', wordBreak: 'break-all' },
  input:   { width: '100%', padding: '8px 12px', fontSize: 12, border: '1px solid #e2e8f0', borderRadius: 7, outline: 'none', background: '#fff', color: '#1e293b', boxSizing: 'border-box' },
  btn:     (active) => ({ padding: '6px 14px', fontSize: 11, fontWeight: 600, border: 'none', borderRadius: 6, cursor: 'pointer', background: active ? '#0072B2' : '#f1f5f9', color: active ? '#fff' : '#475569', transition: 'all .15s' }),
}

function PropTable({ props }) {
  const skip = new Set(['created_at','updated_at','computed_from_window'])
  const entries = Object.entries(props || {}).filter(([k]) => !skip.has(k))
  if (!entries.length) return <div style={{ fontSize: 11, color: '#94a3b8', padding: 8 }}>No properties</div>
  return (
    <div style={{ padding: '4px 0' }}>
      {entries.map(([k, v]) => (
        <div key={k} style={S.propRow}>
          <span style={S.propKey}>{k}</span>
          <span style={{ ...S.propVal, color: typeof v === 'number' ? '#0072B2' : typeof v === 'boolean' ? '#009E73' : '#1e293b' }}>
            {typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v)}
          </span>
        </div>
      ))}
    </div>
  )
}

function OverviewPanel({ data }) {
  if (!data) return null
  const labels = data.label_counts || {}
  const rels   = data.rel_counts   || {}
  return (
    <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
      {/* Node types */}
      <div style={{ ...S.card, flex: '1 1 300px' }}>
        <div style={S.cardHdr}>Node Types — {data.total_nodes?.toLocaleString()} total</div>
        <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {Object.entries(labels).sort((a,b) => b[1]-a[1]).map(([lbl, cnt]) => (
            <div key={lbl} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={S.badge(labelColor(lbl))}>{lbl}</span>
              <div style={{ flex: 1, height: 6, background: '#f1f5f9', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${(cnt / data.total_nodes * 100).toFixed(1)}%`, background: labelColor(lbl), borderRadius: 3 }} />
              </div>
              <span style={{ fontSize: 11, color: '#64748b', minWidth: 50, textAlign: 'right' }}>{cnt.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
      {/* Rel types */}
      <div style={{ ...S.card, flex: '1 1 300px' }}>
        <div style={S.cardHdr}>Relationship Types — {data.total_edges?.toLocaleString()} total</div>
        <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {Object.entries(rels).sort((a,b) => b[1]-a[1]).map(([rt, cnt]) => (
            <div key={rt} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#475569', minWidth: 130 }}>{rt}</span>
              <div style={{ flex: 1, height: 6, background: '#f1f5f9', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${(cnt / data.total_edges * 100).toFixed(1)}%`, background: '#0072B2', borderRadius: 3, opacity: 0.6 }} />
              </div>
              <span style={{ fontSize: 11, color: '#64748b', minWidth: 50, textAlign: 'right' }}>{cnt.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function NodeBrowser({ overview }) {
  const labels = Object.keys(overview?.label_counts || {})
  const [activeLabel, setActiveLabel] = useState(labels[0] || 'Supplier')
  const [skip, setSkip]               = useState(0)
  const [selected, setSelected]       = useState(null)
  const LIMIT = 20

  const { data, isLoading } = useQuery({
    queryKey: ['neo4j-nodes', activeLabel, skip],
    queryFn: () => api.getNeo4jNodes(activeLabel, { limit: LIMIT, skip }).then(r => r.data),
    enabled: !!activeLabel,
    staleTime: 60_000,
  })

  const { data: relData, isLoading: relLoading } = useQuery({
    queryKey: ['neo4j-rels', selected?.id],
    queryFn: () => api.getNeo4jRelationships(selected.id).then(r => r.data),
    enabled: !!selected?.id,
    staleTime: 60_000,
  })

  const nodes = data?.nodes || []
  const total = data?.total || 0
  const pages = Math.ceil(total / LIMIT)
  const page  = Math.floor(skip / LIMIT)

  return (
    <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
      {/* Label selector + node list */}
      <div style={{ ...S.card, flex: '1 1 340px', minWidth: 300 }}>
        <div style={S.cardHdr}>Browse Nodes</div>
        {/* Label tabs */}
        <div style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {labels.map(l => (
            <button key={l} style={S.btn(activeLabel === l)}
              onClick={() => { setActiveLabel(l); setSkip(0); setSelected(null) }}>
              {l} <span style={{ opacity: .6 }}>({(overview.label_counts[l] || 0).toLocaleString()})</span>
            </button>
          ))}
        </div>
        {/* Node rows */}
        <div style={{ maxHeight: 420, overflowY: 'auto' }}>
          {isLoading ? (
            <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: '#94a3b8' }}>Loading…</div>
          ) : nodes.map(n => {
            const p = n.properties
            const name = p.supplier_name || p.category || p.city || p.shipping_mode || p.order_id || p.customer_id || p.node_id?.slice(0,10) || n.id?.slice(0,10)
            const sub  = p.region || p.order_country || p.segment || p.order_date?.slice(0,10) || ''
            const isActive = selected?.id === n.id
            return (
              <div key={n.id} onClick={() => setSelected(n)}
                style={{ padding: '9px 14px', borderBottom: '1px solid #f8fafc', cursor: 'pointer', background: isActive ? '#eff6ff' : 'transparent', transition: 'background .1s' }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#f8fafc' }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: labelColor(n.label), flexShrink: 0 }} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{name}</span>
                  {p.risk_score != null && (
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: p.risk_score > 0.7 ? '#dc2626' : p.risk_score > 0.4 ? '#d97706' : '#16a34a', fontWeight: 600 }}>
                      risk {p.risk_score.toFixed(2)}
                    </span>
                  )}
                </div>
                {sub && <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2, marginLeft: 15 }}>{sub}</div>}
              </div>
            )
          })}
        </div>
        {/* Pagination */}
        {pages > 1 && (
          <div style={{ padding: '8px 14px', borderTop: '1px solid #f1f5f9', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#64748b' }}>
            <button style={S.btn(false)} disabled={page === 0} onClick={() => setSkip(Math.max(0, skip - LIMIT))}>← Prev</button>
            <span>Page {page+1} / {pages} ({total.toLocaleString()} nodes)</span>
            <button style={S.btn(false)} disabled={page >= pages-1} onClick={() => setSkip(skip + LIMIT)}>Next →</button>
          </div>
        )}
      </div>

      {/* Node detail + relationships */}
      <div style={{ flex: '1 1 380px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {selected ? (
          <>
            <div style={S.card}>
              <div style={{ ...S.cardHdr, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={S.badge(labelColor(selected.label))}>{selected.label}</span>
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>{selected.id}</span>
              </div>
              <div style={{ padding: '8px 14px', maxHeight: 260, overflowY: 'auto' }}>
                <PropTable props={selected.properties} />
              </div>
            </div>

            <div style={S.card}>
              <div style={S.cardHdr}>Relationships ({relData?.relationships?.length || 0})</div>
              <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                {relLoading ? (
                  <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: '#94a3b8' }}>Loading…</div>
                ) : (relData?.relationships || []).length === 0 ? (
                  <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: '#94a3b8' }}>No relationships</div>
                ) : (relData?.relationships || []).map((r, i) => (
                  <div key={i} style={{ padding: '8px 14px', borderBottom: '1px solid #f8fafc', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>{r.is_outgoing ? '→' : '←'}</span>
                      <span style={{ fontSize: 10, fontFamily: 'monospace', fontWeight: 700, color: '#475569', background: '#f1f5f9', padding: '2px 6px', borderRadius: 4 }}>{r.rel_type}</span>
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={S.badge(labelColor(r.target_label))}>{r.target_label}</span>
                        <span style={{ fontSize: 11, color: '#1e293b', fontFamily: 'monospace' }}>
                          {r.target_props?.supplier_name || r.target_props?.category || r.target_props?.city || r.target_props?.shipping_mode || r.target_id?.slice(0,12)}
                        </span>
                      </div>
                      {Object.keys(r.rel_props || {}).length > 0 && (
                        <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>
                          {Object.entries(r.rel_props).slice(0,3).map(([k,v]) => `${k}: ${typeof v === 'number' ? v.toFixed(3) : v}`).join(' · ')}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div style={{ ...S.card, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, color: '#94a3b8', fontSize: 13 }}>
            ← Select a node to inspect
          </div>
        )}
      </div>
    </div>
  )
}

function SearchPanel() {
  const [q, setQ]           = useState('')
  const [submitted, setSub] = useState('')
  const [selLabel, setSel]  = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['neo4j-search', submitted],
    queryFn: () => api.searchNeo4j(submitted).then(r => r.data),
    enabled: submitted.length >= 2,
    staleTime: 30_000,
  })

  const results = data?.results || []

  return (
    <div style={{ ...S.card, width: '100%' }}>
      <div style={S.cardHdr}>Search Graph</div>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f1f5f9', display: 'flex', gap: 8 }}>
        <input style={{ ...S.input, flex: 1 }} placeholder="Search by name, category, region, order ID, city…"
          value={q} onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && setSub(q)} />
        <button style={{ ...S.btn(true), padding: '8px 18px' }} onClick={() => setSub(q)}>Search</button>
      </div>
      {isLoading && <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: '#94a3b8' }}>Searching…</div>}
      {!isLoading && submitted && results.length === 0 && (
        <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: '#94a3b8' }}>No results for "{submitted}"</div>
      )}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {results.map((r, i) => {
          const p = r.props || {}
          const name = p.supplier_name || p.category || p.city || p.shipping_mode || p.order_id || p.customer_id || r.id?.slice(0,12)
          return (
            <div key={i} style={{ padding: '10px 14px', borderBottom: '1px solid #f8fafc', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span style={S.badge(labelColor(r.label))}>{r.label}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{name}</div>
                <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2, fontFamily: 'monospace' }}>
                  {Object.entries(p).filter(([k]) => !['created_at','updated_at','label','node_id','entity_id'].includes(k)).slice(0,4).map(([k,v]) => `${k}: ${typeof v === 'number' ? v.toFixed(3) : String(v).slice(0,30)}`).join(' · ')}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const TABS = [
  { id: 'overview', label: '📊 Overview'    },
  { id: 'browse',   label: '🗂 Browse Nodes' },
  { id: 'search',   label: '🔍 Search'       },
]

export default function Neo4jPage({ embedded = false }) {
  const [tab, setTab] = useState('overview')

  const { data: overview, isLoading, isError } = useQuery({
    queryKey: ['neo4j-overview'],
    queryFn: () => api.getNeo4jOverview().then(r => r.data),
    staleTime: 120_000,
  })

  const tabBar = (
    <div style={{ display: 'flex', gap: 2 }}>
      {TABS.map(t => {
        const on = tab === t.id
        return (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ padding: '8px 16px', fontSize: 12, fontWeight: on ? 600 : 400, color: on ? '#fff' : 'rgba(255,255,255,.45)', background: on ? 'rgba(255,255,255,.1)' : 'transparent', border: 'none', borderBottom: on ? '2px solid #60a5fa' : '2px solid transparent', cursor: 'pointer', borderRadius: '5px 5px 0 0' }}>
            {t.label}
          </button>
        )
      })}
    </div>
  )

  return (
    <div style={{ ...S.page, minHeight: embedded ? 'unset' : '100vh' }}>
      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}`}</style>

      {embedded ? (
        <div style={{ background: 'linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%)', padding: '10px 20px' }}>
          {tabBar}
        </div>
      ) : (
        <div style={S.header}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#fff' }}>Neo4j Graph Explorer</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,.4)', marginTop: 2 }}>
                {overview ? `${overview.total_nodes?.toLocaleString()} nodes · ${overview.total_edges?.toLocaleString()} edges · ${Object.keys(overview.label_counts||{}).length} node types` : 'Connecting…'}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(74,222,128,.1)', border: '1px solid rgba(74,222,128,.2)', borderRadius: 20, padding: '4px 12px', fontSize: 11, color: '#4ade80' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80', animation: 'pulse 2s infinite', display: 'inline-block' }} />
              {isError ? 'Offline' : 'Connected'}
            </div>
          </div>
          {tabBar}
        </div>
      )}

      <div style={S.body}>
        {isLoading && <div style={{ fontSize: 13, color: '#94a3b8', padding: 20 }}>Connecting to Neo4j…</div>}
        {isError   && <div style={{ fontSize: 13, color: '#ef4444', padding: 20 }}>⚠ Failed to connect to Neo4j</div>}
        {!isLoading && !isError && (
          <>
            {tab === 'overview' && <div style={{ width: '100%' }}><OverviewPanel data={overview} /></div>}
            {tab === 'browse'   && <div style={{ width: '100%' }}><NodeBrowser overview={overview} /></div>}
            {tab === 'search'   && <div style={{ width: '100%' }}><SearchPanel /></div>}
          </>
        )}
      </div>
    </div>
  )
}
