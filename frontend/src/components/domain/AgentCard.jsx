import RiskGauge from '../ui/RiskGauge'
import RiskBadge from '../ui/RiskBadge'

const AGENTS = {
  demand:    { label: 'Demand Forecasting', color: 'var(--dem)', model: 'LightGBM Regressor',    primaryMetric: 'R²',  secondaryMetric: 'MAPE' },
  supplier:  { label: 'Supplier Risk',      color: 'var(--sup)', model: 'Random Forest',          primaryMetric: 'AUC', secondaryMetric: 'F1', fusionWeight: 0.45 },
  logistics: { label: 'Logistics Risk',     color: 'var(--log)', model: 'LightGBM Classifier',    primaryMetric: 'AUC', secondaryMetric: 'F1', fusionWeight: 0.55 },
}

// Two-agent prediction fusion weights (supplier + logistics only)
// Demand is a regressor — it does not participate in the binary risk fusion.
const FUSION_WEIGHTS = { supplier: 0.45, logistics: 0.55 }

function KGBadge({ graphEnriched, coverage }) {
  if (graphEnriched && coverage >= 0.5) {
    return (
      <span style={{
        fontSize: '9px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px',
        background: 'rgba(0,184,148,0.12)', color: '#00b894', border: '1px solid rgba(0,184,148,0.3)',
        display: 'inline-block', marginBottom: '6px',
      }}>
        KG-enriched ({Math.round(coverage * 100)}%)
      </span>
    )
  }
  return (
    <span style={{
      fontSize: '9px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px',
      background: 'rgba(230,126,34,0.12)', color: '#e67e22', border: '1px solid rgba(230,126,34,0.3)',
      display: 'inline-block', marginBottom: '6px',
    }}>
      Tier-1 only
    </span>
  )
}

export function AgentMetricsPanel({ agents = {} }) {
  // agents: { demand: { score, metrics, graphEnriched, coverage }, supplier: {...}, logistics: {...} }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', alignItems: 'start' }}>
      {['demand', 'supplier', 'logistics'].map(type => {
        const cfg = AGENTS[type]
        const data = agents[type] || {}
        const score = data.score ?? 0
        const level = score >= 0.65 ? 'high' : score >= 0.35 ? 'med' : 'low'
        const metrics = data.metrics || []

        // Ensure accuracy is never shown alone — require companion metrics
        const hasCompanion = metrics.some(m =>
          ['precision', 'recall', 'auc', 'f1', 'mape', 'r2', 'rmse'].some(k =>
            m.label?.toLowerCase().includes(k)
          )
        )
        const safeMetrics = hasCompanion ? metrics : metrics.filter(m =>
          !m.label?.toLowerCase().includes('accuracy')
        )

        return (
          <div key={type} className="agent-card">
            <div className="agent-accent" style={{ background: cfg.color }} />
            <div className="agent-body">
              <div className="agent-head">
                <div>
                  <div className="agent-name">{cfg.label}</div>
                  <div className="agent-model">{cfg.model}</div>
                </div>
                <RiskBadge level={level} />
              </div>
              <KGBadge graphEnriched={data.graphEnriched} coverage={data.coverage ?? 0} />
              <div style={{ display: 'flex', justifyContent: 'center', margin: '4px 0 8px' }}>
                <RiskGauge score={score} size={90} color={cfg.color} label="Risk" />
              </div>
              <div className="agent-metrics">
                {safeMetrics.slice(0, 4).map((m, i) => (
                  <div key={i}>
                    <div className="agent-metric-lbl">{m.label}</div>
                    <div className="agent-metric-val">{m.value ?? '\u2014'}</div>
                  </div>
                ))}
                {FUSION_WEIGHTS[type] != null && (
                  <div style={{ gridColumn: '1 / -1', marginTop: 4, fontSize: '9px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: 4 }}>
                    Fusion weight: <strong>{FUSION_WEIGHTS[type]}</strong>
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}

      {/* Inventory agent tile — commented out, no UI display for now */}
      {/* <div style={{
        border: '1.5px dashed var(--b)', borderRadius: '8px', padding: '14px 12px',
        background: 'var(--s0)', opacity: 0.7,
      }}>
        <div style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--ts)', marginBottom: '4px' }}>
          Inventory
        </div>
        <div style={{ fontSize: '9.5px', fontWeight: 700, color: 'var(--tm)', marginBottom: '8px' }}>
          — excluded
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', lineHeight: '1.5' }}>
          DataCo contains no independent inventory signal (CV AUC 0.479).
          Excluding this agent rather than reporting a degenerate model.
        </div>
      </div> */}
    </div>
  )
}

// Legacy single-card export kept for backward compat
export default function AgentCard({ type, score = 0, metrics = [], period, graphEnriched, coverage }) {
  const cfg = AGENTS[type] || AGENTS.demand
  const level = score >= 0.65 ? 'high' : score >= 0.35 ? 'med' : 'low'

  return (
    <div className="agent-card">
      <div className="agent-accent" style={{ background: cfg.color }} />
      <div className="agent-body">
        <div className="agent-head">
          <div>
            <div className="agent-name">{cfg.label}</div>
            <div className="agent-model">{cfg.model}</div>
          </div>
          <RiskBadge level={level} />
        </div>
        <KGBadge graphEnriched={graphEnriched} coverage={coverage ?? 0} />
        <div style={{ display: 'flex', justifyContent: 'center', margin: '4px 0 8px' }}>
          <RiskGauge score={score} size={90} color={cfg.color} label="Risk" />
        </div>
        <div className="agent-metrics">
          {metrics.slice(0, 4).map((m, i) => (
            <div key={i}>
              <div className="agent-metric-lbl">{m.label}</div>
              <div className="agent-metric-val">{m.value}</div>
            </div>
          ))}
        </div>
        {period && <div style={{ fontSize: '10px', color: 'var(--tm)', marginTop: '8px' }}>Based on {period}</div>}
      </div>
    </div>
  )
}
