import EmptyState from '../ui/EmptyState'
import { GitBranch } from 'lucide-react'

export default function KGEvolutionPanel({ events = [] }) {
  if (!events.length) return <EmptyState icon={GitBranch} title="No TPKE events" desc="Run a forecast to trigger knowledge graph evolution" />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {events.map((ev, i) => (
        <div key={i} className="tpke-event">
          <div className="tpke-event-main">
            <div className="tpke-event-name">{ev.pattern || ev.name}</div>
            <div className="tpke-event-sub">
              Confidence: {((ev.confidence || 0) * 100).toFixed(0)}% · Freq: {ev.frequency || 0}
            </div>
          </div>
          <span className="badge bdg-blue"><span className="bdg-dot" />{ev.action || 'Edge created'}</span>
        </div>
      ))}
    </div>
  )
}
