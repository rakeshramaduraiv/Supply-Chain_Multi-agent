/**
 * ValidationPanel.jsx — Validation tab: upload zone, error diagnostics, charts, history
 */
import { FileUp, Activity, AlertTriangle, ShieldCheck, Cpu, Loader } from 'lucide-react'
import {
  ComposedChart, LineChart, BarChart, PieChart, Pie, Cell,
  Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import UploadZone from '../ui/UploadZone'
import CycleStageTracker from '../domain/CycleStageTracker'
import EmptyState from '../ui/EmptyState'
import styles from '../../pages/ForecastPage.module.css'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 8, padding: '8px 12px', fontSize: 11 }}>
      <div style={{ fontWeight: 600, color: 'var(--tp)', marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '2px 0' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color || p.stroke, flexShrink: 0 }} />
          <span style={{ color: 'var(--ts)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600, color: 'var(--tp)' }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function ValidationPanel({
  cycleMonth, cycleStep, cycleActualsUploaded,
  actualsFile, setActualsFile,
  isIngestingActuals, cycleUploadResult,
  handleIngestSyntheticMonth, setValidationResult, setCycleUploadResult,
  errorDiagnostics,
  historicalForecastSeries, confidenceTimeline, deviationData,
  uploadHistory,
  // CycleStageTracker props
  activeCycleId, cycleStages, cycleComplete, wsConnected,
}) {
  const agentAccuracyData = [
    { name: 'Demand Agent',   accuracy: null, color: 'var(--blue)' },
    { name: 'Supplier Agent', accuracy: null, color: '#e67e22' },
    { name: 'Logistics Agent',accuracy: null, color: '#d63031' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Upload Zone */}
      <div id="upload-zone-anchor" className="card" style={{
        padding: '16px 20px',
        border: cycleStep === 2 && !cycleActualsUploaded ? '2px solid var(--blue)' : '1px solid var(--b)',
        borderRadius: 10,
      }}>
        <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--tp)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FileUp size={15} style={{ color: 'var(--blue)' }} /> Ingest Monthly Actual Performance CSV
          {cycleStep === 2 && !cycleActualsUploaded && (
            <span style={{ marginLeft: 'auto', fontSize: '10px', background: '#dbeafe', color: '#1d4ed8', padding: '2px 8px', borderRadius: 8, fontWeight: 700 }}>
              ← Step 2 Active · Upload actuals for {cycleMonth}
            </span>
          )}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--tm)', marginBottom: '10px' }}>
          Upload the actual CSV for <strong>{cycleMonth}</strong> to validate model predictions and compute deviation metrics:
        </div>
        <div style={{ maxWidth: '500px' }}>
          <UploadZone
            accept=".csv"
            hint={`Drag & drop ${cycleMonth} actuals CSV here, or click to browse`}
            hasFile={!!actualsFile}
            fileName={actualsFile?.name}
            onFile={(file) => {
              setActualsFile(file)
              handleIngestSyntheticMonth(cycleMonth, file)
            }}
            onClear={() => {
              setActualsFile(null)
              setValidationResult(null)
              setCycleUploadResult(null)
            }}
            disabled={isIngestingActuals || cycleActualsUploaded}
          />
        </div>
        {isIngestingActuals && (
          <div style={{ marginTop: 8, fontSize: '10px', color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Loader size={12} className={styles.spin} /> Running 6-stage upload cycle pipeline…
          </div>
        )}
        {cycleActualsUploaded && cycleUploadResult && (
          <div style={{ marginTop: 8, fontSize: '10px', color: '#00b894', fontWeight: 700 }}>
            ✅ {cycleUploadResult.records_loaded?.toLocaleString()} records ingested · MAPE: {cycleUploadResult.mape_val?.toFixed(2)}%
          </div>
        )}
      </div>

      {/* Live Cycle Stage Tracker */}
      <CycleStageTracker
        cycleId={activeCycleId}
        stages={cycleStages}
        complete={cycleComplete}
        connected={wsConnected}
        period={cycleMonth}
      />

      {/* Error Diagnostics */}
      <div id="error-diagnostics-anchor" style={{ fontSize: '14px', fontWeight: 800, color: 'var(--tp)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span>Error Breakdown &amp; Responsible Agent Diagnostics</span>
        <span style={{ fontSize: '10px', fontWeight: 600, color: cycleUploadResult?.comparison_records?.length ? '#00b894' : '#f59e0b' }}>
          {cycleUploadResult?.comparison_records?.length
            ? `✅ ${cycleUploadResult.period} — Predicted vs Actual (${cycleUploadResult.comparison_records.length} categories)`
            : `⚠️ Upload actuals above to see predicted vs actual deviation for ${cycleMonth}`}
        </span>
      </div>

      <div className={styles.validationErrorGrid}>
        {errorDiagnostics.map((err, idx) => {
          const hasActual = err.actual !== '—'
          return (
            <div key={idx} className={styles.errorDiagnosticCard}>
              <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--tp)' }}>{err.category}</div>
              {hasActual ? (
                <>
                  <div style={{ fontSize: '10.5px', color: 'var(--ts)' }}>Predicted: <strong>{err.predicted}</strong></div>
                  <div style={{ fontSize: '10.5px', color: 'var(--ts)' }}>Actual: <strong style={{ color: '#00b894' }}>{err.actual}</strong></div>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: err.diff.startsWith('+') ? '#d63031' : '#00b894' }}>Variance: {err.diff}</div>
                </>
              ) : (
                <div style={{ fontSize: '10.5px', color: 'var(--ts)' }}>
                  Forecast Prediction: <strong style={{ color: 'var(--blue)' }}>{err.predicted}</strong>
                </div>
              )}
              <div style={{ fontSize: '10px', color: 'var(--tm)', marginTop: 4 }}>
                <strong>Reason:</strong> {err.reason}<br />
                <strong>Agent:</strong> <span className="badge bdg-blue">{err.responsible_agent}</span><br />
                <strong>Root Cause:</strong> {err.root_cause}
              </div>
            </div>
          )
        })}
      </div>

      {/* Validation Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '16px' }}>
        <div className="card" style={{ padding: '16px' }}>
          <div className="card-head" style={{ marginBottom: '10px' }}>
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Activity size={15} style={{ color: 'var(--blue)' }} />
              Actual vs Predicted Order Volume Trend
              {cycleUploadResult && <span className="badge bdg-low" style={{ marginLeft: 6 }}>Live — {cycleUploadResult.period}</span>}
            </span>
          </div>
          <div style={{ height: '220px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={historicalForecastSeries} margin={{ left: -15, right: 10, top: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 9 }} />
                <Bar dataKey="historical" name="Historical Orders" fill="var(--blue)" barSize={16} radius={[3,3,0,0]} />
                <Line type="monotone" dataKey="forecast" name="Predicted Forecast" stroke="#00b894" strokeWidth={2.5} dot={{ r: 3 }} />
                {cycleUploadResult && (
                  <Line type="monotone" dataKey="actual" name="Ingested Actuals" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4 }} connectNulls={false} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card" style={{ padding: '16px' }}>
          <div className="card-head" style={{ marginBottom: '10px' }}>
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={15} style={{ color: '#e67e22' }} />
              Model Deviation Distribution (Matched Records)
            </span>
          </div>
          {!cycleUploadResult ? (
            <EmptyState icon={AlertTriangle} title="No deviation data" description="Upload actuals to see deviation breakdown." />
          ) : (
            <div style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: '50%', height: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={deviationData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                      {deviationData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                    </Pie>
                    <Tooltip formatter={(value) => `${value} records`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ width: '50%', display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '10px' }}>
                {deviationData.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: d.color, flexShrink: 0 }} />
                    <span style={{ fontSize: '10.5px', color: 'var(--tp)', fontWeight: 600 }}>{d.name}:</span>
                    <span style={{ fontSize: '10.5px', color: 'var(--ts)' }}>{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="card" style={{ padding: '16px' }}>
          <div className="card-head" style={{ marginBottom: '10px' }}>
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={15} style={{ color: '#00b894' }} />
              Model Confidence &amp; Accuracy Cycles (%)
            </span>
          </div>
          <div style={{ height: '220px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={confidenceTimeline} margin={{ left: -15, right: 10, top: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} domain={[70, 100]} unit="%" />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 9 }} />
                <Line type="monotone" dataKey="prediction_confidence" name="Prediction Confidence %" stroke="var(--blue)" strokeWidth={2} />
                <Line type="monotone" dataKey="validation_confidence" name="Validation Accuracy %" stroke="#00b894" strokeWidth={2} strokeDasharray="3 3" />
                <Line type="monotone" dataKey="rolling_average" name="Rolling Avg Confidence" stroke="#7c6fcd" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card" style={{ padding: '16px' }}>
          <div className="card-head" style={{ marginBottom: '10px' }}>
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Cpu size={15} style={{ color: '#7c6fcd' }} />
              Multi-Agent Decision Accuracy Comparison
            </span>
          </div>
          <EmptyState
            icon={Cpu}
            title="No ablation run yet"
            description="Run the ablation experiment to compare per-agent accuracy (precision, recall, AUC)."
          />
        </div>
      </div>

      {/* Upload History */}
      <div className="card" style={{ padding: '16px' }}>
        <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--tp)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FileUp size={15} style={{ color: 'var(--blue)' }} />
          Upload History — Actual Performance Records
        </div>
        {uploadHistory.length === 0 ? (
          <EmptyState icon={FileUp} title="No uploads yet" description="Use the upload section above to ingest monthly actuals." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--b)', color: 'var(--tm)', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px' }}>Uploaded Month</th>
                <th style={{ padding: '6px 8px' }}>Records</th>
                <th style={{ padding: '6px 8px' }}>Validation Status</th>
                <th style={{ padding: '6px 8px' }}>MAPE</th>
                <th style={{ padding: '6px 8px' }}>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {uploadHistory.map((h, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid var(--b)', color: 'var(--tp)' }}>
                  <td style={{ padding: '6px 8px', fontWeight: 700, color: 'var(--blue)' }}>{h.period}</td>
                  <td style={{ padding: '6px 8px' }}>{(h.records || 0).toLocaleString()}</td>
                  <td style={{ padding: '6px 8px' }}><span className="badge bdg-low">{h.status}</span></td>
                  <td style={{ padding: '6px 8px', color: '#e67e22' }}>{h.mape}</td>
                  <td style={{ padding: '6px 8px', color: 'var(--ts)', fontSize: '10px' }}>{h.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
