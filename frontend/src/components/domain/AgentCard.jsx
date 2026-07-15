import RiskGauge from '../ui/RiskGauge'
import RiskBadge from '../ui/RiskBadge'

const AGENTS = {
  demand:    { label: 'Demand Forecasting', color: 'var(--dem)', model: 'LightGBM Regressor' },
  inventory: { label: 'Inventory Health',   color: 'var(--inv)', model: 'LightGBM Classifier' },
  supplier:  { label: 'Supplier Risk',      color: 'var(--sup)', model: 'Random Forest + LightGBM' },
  logistics: { label: 'Logistics Risk',     color: 'var(--log)', model: 'LightGBM Classifier' },
}

export default function AgentCard({ type, score = 0, metrics = [], period }) {
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
        <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
          <RiskGauge score={score} size={100} color={cfg.color} label="Risk" />
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
