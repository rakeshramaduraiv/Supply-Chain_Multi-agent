/**
 * ActualDataPage.jsx
 * Upload actual performance data month-by-month.
 * The four holdout months (Oct–Jan 2017-18) are pre-wired as one-click uploads.
 * Any CSV can also be dragged in manually.
 * After upload the live metrics panel refreshes automatically.
 */
import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  Upload, CheckCircle, AlertTriangle, Clock, BarChart2,
  FileText, Zap, RefreshCw, ChevronDown, ChevronUp,
} from 'lucide-react'

const HOLDOUT_MONTHS = [
  { period: '2017-10', label: 'October 2017',  file: 'UPLOAD_1_October_2017.csv',  rows: 2255 },
  { period: '2017-11', label: 'November 2017', file: 'UPLOAD_2_November_2017.csv', rows: 2055 },
  { period: '2017-12', label: 'December 2017', file: 'UPLOAD_3_December_2017.csv', rows: 2124 },
  { period: '2018-01', label: 'January 2018',  file: 'UPLOAD_4_January_2018.csv',  rows: 2123 },
]

const METRIC_LABELS = {
  demand_mae:       { label: 'Demand MAE',      color: '#7c6fcd', fmt: v => v?.toFixed(4) },
  demand_rmse:      { label: 'Demand RMSE',     color: '#7c6fcd', fmt: v => v?.toFixed(4) },
  demand_r2:        { label: 'Demand R²',       color: '#7c6fcd', fmt: v => v?.toFixed(4) },
  supplier_auc:     { label: 'Supplier AUC',    color: '#f59e0b', fmt: v => v?.toFixed(4) },
  supplier_f1:      { label: 'Supplier F1',     color: '#f59e0b', fmt: v => v?.toFixed(4) },
  supplier_brier:   { label: 'Supplier Brier',  color: '#f59e0b', fmt: v => v?.toFixed(4) },
  logistics_auc:    { label: 'Logistics AUC',   color: '#ec4899', fmt: v => v?.toFixed(4) },
  logistics_f1:     { label: 'Logistics F1',    color: '#ec4899', fmt: v => v?.toFixed(4) },
  logistics_brier:  { label: 'Logistics Brier', color: '#ec4899', fmt: v => v?.toFixed(4) },
}

function MetricPill({ metaKey, value }) {
  const meta = METRIC_LABELS[metaKey]
  if (!meta || value == null) return null
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '8px 12px', borderRadius: 6,
      background: `${meta.color}12`, border: `1px solid ${meta.color}30`,
      minWidth: 90,
    }}>
      <span style={{ fontSize: 9, color: 'var(--tm)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {meta.label}
      </span>
      <span style={{ fontSize: 16, fontWeight: 800, color: meta.color, marginTop: 2 }}>
        {meta.fmt(value)}
      </span>
    </div>
  )
}

function UploadResultCard({ result }) {
  const [expanded, setExpanded] = useState(false)
  if (!result) return null

  const metrics = result._metrics || {}
  const hasMetrics = Object.values(metrics).some(v => v != null)

  return (
    <div style={{
      border: '1px solid var(--b)', borderRadius: 8,
      background: 'var(--s1)', overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 16px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <CheckCircle size={18} style={{ color: '#00b894', flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--tp)' }}>
              {result.period} — {result.records_loaded?.toLocaleString()} rows uploaded
            </div>
            <div style={{ fontSize: 10, color: 'var(--tm)', marginTop: 1 }}>
              Matched: {result.records_matched?.toLocaleString()} · Accuracy: {result.overall_accuracy?.toFixed(1)}%
            </div>
          </div>
        </div>
        {hasMetrics && (
          <button
            onClick={() => setExpanded(e => !e)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ts)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}
          >
            ML Metrics {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        )}
      </div>

      {expanded && hasMetrics && (
        <div style={{ padding: '0 16px 14px', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {Object.entries(metrics).map(([k, v]) => (
            <MetricPill key={k} metaKey={k} value={v} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function ActualDataPage() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  const [manualFile, setManualFile] = useState(null)
  const [manualPeriod, setManualPeriod] = useState('')
  const [drag, setDrag] = useState(false)
  const [results, setResults] = useState([])

  // Load cycle history to show what's already been uploaded
  const cycleQuery = useQuery({
    queryKey: ['cycleHistory'],
    queryFn: () => api.getCycleHistory().then(r => r.data),
    refetchInterval: 10_000,
  })
  const cycles = cycleQuery.data?.cycles || []
  const uploadedPeriods = new Set(cycles.filter(c => c.rows_uploaded > 0).map(c => c.month))

  const uploadMut = useMutation({
    mutationFn: async ({ file, period }) => {
      const r = await api.uploadBusinessActual(file, period)
      return { ...r.data, period }
    },
    onSuccess: (data) => {
      // Fetch real ML metrics from cycle history after upload
      queryClient.invalidateQueries({ queryKey: ['cycleHistory'] })
      queryClient.invalidateQueries({ queryKey: ['supplyChain'] })
      setResults(prev => {
        const filtered = prev.filter(r => r.period !== data.period)
        return [data, ...filtered]
      })
    },
  })

  // One-click upload of a holdout month from the server-side file
  const handleHoldoutUpload = async (month) => {
    try {
      // Fetch the CSV from the backend's actuals_real directory via a helper endpoint
      const resp = await fetch(
        `http://localhost:8000/api/v1/business/holdout-file/${month.file}`
      )
      if (!resp.ok) throw new Error(`Could not fetch ${month.file}`)
      const blob = await resp.blob()
      const file = new File([blob], month.file, { type: 'text/csv' })
      uploadMut.mutate({ file, period: month.period })
    } catch {
      // Fallback: prompt user to pick the file manually
      fileInputRef.current?.click()
    }
  }

  const handleManualUpload = () => {
    if (!manualFile || !manualPeriod) return
    uploadMut.mutate({ file: manualFile, period: manualPeriod })
  }

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false)
    const f = e.dataTransfer.files[0]
    if (f?.name.endsWith('.csv')) setManualFile(f)
  }

  return (
    <div className="page active" style={{ padding: '20px 24px', maxWidth: 900, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <BarChart2 size={22} style={{ color: 'var(--blue)' }} />
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--tp)', margin: 0 }}>
            Actual Data Upload
          </h1>
        </div>
        <p style={{ fontSize: 12, color: 'var(--tm)', margin: 0 }}>
          Upload monthly actual performance data to evaluate model predictions against real outcomes.
          The four held-out months (Oct 2017 – Jan 2018) are pre-wired below.
        </p>
      </div>

      {/* ── SECTION 1: Holdout Quick-Upload ── */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <Zap size={15} style={{ color: '#f59e0b' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--tp)' }}>
            Held-Out Evaluation Months
          </span>
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: '#eff6ff', color: 'var(--blue)', border: '1px solid #bfdbfe', fontWeight: 600 }}>
            Real DataCo data · Never seen by models during training
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {HOLDOUT_MONTHS.map(month => {
            const done = uploadedPeriods.has(month.period)
            const loading = uploadMut.isPending && uploadMut.variables?.period === month.period

            return (
              <div key={month.period} style={{
                padding: '14px 16px', borderRadius: 8,
                border: `1px solid ${done ? '#00b89440' : 'var(--b)'}`,
                background: done ? '#00b89408' : 'var(--s0)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--tp)' }}>
                    {month.label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--tm)', marginTop: 2 }}>
                    {month.rows.toLocaleString()} rows · {month.file}
                  </div>
                </div>

                {done ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#00b894', fontWeight: 700 }}>
                    <CheckCircle size={14} /> Uploaded
                  </div>
                ) : (
                  <button
                    onClick={() => handleHoldoutUpload(month)}
                    disabled={loading || uploadMut.isPending}
                    className="btn btn-primary btn-sm"
                    style={{ display: 'flex', alignItems: 'center', gap: 5 }}
                  >
                    {loading
                      ? <><RefreshCw size={12} className="spin" /> Uploading…</>
                      : <><Upload size={12} /> Upload</>
                    }
                  </button>
                )}
              </div>
            )
          })}
        </div>

        <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, background: 'rgba(9,132,227,0.06)', border: '1px solid rgba(9,132,227,0.2)', fontSize: 10.5, color: 'var(--ts)', lineHeight: 1.6 }}>
          <strong>📁 Where are these files?</strong> They are in your project at:
          <code style={{ display: 'block', marginTop: 4, padding: '4px 8px', background: 'var(--s0)', borderRadius: 4, fontSize: 10, fontFamily: 'monospace' }}>
            backend/data/user_uploads/
          </code>
          These are the last 4 months cut from the original DataCo dataset. The models were trained on everything before October 2017.
          Upload in order (1 → 2 → 3 → 4). Cycle 1 (Oct) skips metrics — measurement begins at Cycle 2 (Nov).
        </div>
      </div>

      {/* ── SECTION 2: Manual Upload ── */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <FileText size={15} style={{ color: 'var(--blue)' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--tp)' }}>
            Upload Any CSV
          </span>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          {/* Drop zone */}
          <div
            onDrop={onDrop}
            onDragOver={e => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onClick={() => fileInputRef.current?.click()}
            style={{
              flex: 1, minHeight: 80, border: `2px dashed ${drag ? 'var(--blue)' : 'var(--b)'}`,
              borderRadius: 8, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 6,
              cursor: 'pointer', background: drag ? 'rgba(9,132,227,0.04)' : 'var(--s0)',
              transition: 'all 0.15s',
            }}
          >
            <Upload size={20} style={{ color: 'var(--tm)' }} />
            <span style={{ fontSize: 11, color: 'var(--tm)' }}>
              {manualFile ? manualFile.name : 'Drop CSV or click to browse'}
            </span>
            <input
              ref={fileInputRef} type="file" accept=".csv" hidden
              onChange={e => { setManualFile(e.target.files[0]); e.target.value = '' }}
            />
          </div>

          {/* Period + submit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 160 }}>
            <label style={{ fontSize: 10.5, color: 'var(--ts)', fontWeight: 600 }}>Period (YYYY-MM)</label>
            <input
              type="month"
              value={manualPeriod}
              onChange={e => setManualPeriod(e.target.value)}
              style={{
                padding: '6px 10px', border: '1px solid var(--b)', borderRadius: 6,
                background: 'var(--s0)', color: 'var(--tp)', fontSize: 12, outline: 'none',
              }}
            />
            <button
              onClick={handleManualUpload}
              disabled={!manualFile || !manualPeriod || uploadMut.isPending}
              className="btn btn-primary"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              {uploadMut.isPending && !HOLDOUT_MONTHS.some(m => m.period === uploadMut.variables?.period)
                ? <><RefreshCw size={13} className="spin" /> Uploading…</>
                : <><Upload size={13} /> Upload</>
              }
            </button>
          </div>
        </div>

        {uploadMut.isError && (
          <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, background: 'rgba(214,48,49,0.08)', border: '1px solid rgba(214,48,49,0.2)', fontSize: 11, color: '#d63031', display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={13} /> {uploadMut.error?.message || 'Upload failed'}
          </div>
        )}
      </div>

      {/* ── SECTION 3: Upload Results ── */}
      {results.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ts)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Upload Results
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {results.map((r, i) => <UploadResultCard key={i} result={r} />)}
          </div>
        </div>
      )}

      {/* ── SECTION 4: Cycle History ── */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={15} style={{ color: 'var(--blue)' }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--tp)' }}>Cycle History</span>
          </div>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['cycleHistory'] })}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tm)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 10.5 }}
          >
            <RefreshCw size={11} /> Refresh
          </button>
        </div>

        {cycleQuery.isLoading ? (
          <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--tm)' }}>Loading…</div>
        ) : cycles.length === 0 ? (
          <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--tm)' }}>
            No cycles yet — upload a month above to begin.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--b)', color: 'var(--tm)', textAlign: 'left' }}>
                  {['Month', 'Rows', 'Stage 2', 'Stage 3', 'Sup AUC', 'Log AUC', 'Dem MAE', 'Dem R²', 'Duration'].map(h => (
                    <th key={h} style={{ padding: '6px 10px', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cycles.map((c, i) => {
                  const skipped = c.stage3_status === 'SKIPPED' || c.stage3_status === 'ABSENT'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--b)', color: 'var(--tp)' }}>
                      <td style={{ padding: '8px 10px', fontWeight: 700 }}>{c.month}</td>
                      <td style={{ padding: '8px 10px' }}>{c.rows_uploaded?.toLocaleString() ?? '—'}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, fontWeight: 700,
                          background: c.stage2_status === 'OK' ? '#00b89415' : '#e5534b15',
                          color: c.stage2_status === 'OK' ? '#00b894' : '#e5534b',
                          border: `1px solid ${c.stage2_status === 'OK' ? '#00b89430' : '#e5534b30'}`,
                        }}>
                          {c.stage2_status || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, fontWeight: 700,
                          background: skipped ? 'rgba(150,150,150,0.1)' : '#00b89415',
                          color: skipped ? 'var(--tm)' : '#00b894',
                          border: `1px solid ${skipped ? 'var(--b)' : '#00b89430'}`,
                        }}>
                          {c.stage3_status || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', color: '#f59e0b', fontWeight: 600 }}>
                        {c.supplier_auc != null ? c.supplier_auc.toFixed(4) : <span style={{ color: 'var(--tm)' }}>—</span>}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#ec4899', fontWeight: 600 }}>
                        {c.logistics_auc != null ? c.logistics_auc.toFixed(4) : <span style={{ color: 'var(--tm)' }}>—</span>}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#7c6fcd', fontWeight: 600 }}>
                        {c.demand_mae != null ? c.demand_mae.toFixed(4) : <span style={{ color: 'var(--tm)' }}>—</span>}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#7c6fcd', fontWeight: 600 }}>
                        {c.demand_r2 != null ? c.demand_r2.toFixed(4) : <span style={{ color: 'var(--tm)' }}>—</span>}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--ts)' }}>
                        {c.cycle_duration_s != null ? `${c.cycle_duration_s}s` : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
