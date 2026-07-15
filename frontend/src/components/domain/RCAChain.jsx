export default function RCAChain({ chain = [], rootCause, disruption, confidence }) {
  const nodes = chain.length ? chain : buildChain(disruption, rootCause)
  if (!nodes.length) return null

  return (
    <div className="rca-chain">
      {nodes.map((step, i) => {
        const isFirst = i === 0
        const isLast = i === nodes.length - 1
        const dotClass = isLast ? 'root' : isFirst ? 'disruption' : 'causal'
        const badgeLabel = isLast ? 'ROOT CAUSE' : isFirst ? 'DISRUPTION' : 'CAUSAL'
        const badgeCls = isLast ? 'bdg-high' : isFirst ? 'bdg-med' : 'bdg-low'
        const borderColor = isLast ? 'var(--rh)' : isFirst ? 'var(--tpke)' : undefined

        return (
          <div key={i} className="rca-step">
            <div className="rca-gutter">
              <div className={`rca-dot ${dotClass}`} />
              {!isLast && <div className="rca-line" />}
            </div>
            <div className="rca-card" style={borderColor ? { borderLeftColor: borderColor } : undefined}>
              {i > 0 && step.relationship && (
                <div style={{ fontSize: '10px', fontStyle: 'italic', color: 'var(--tm)', marginBottom: '3px' }}>↑ caused by</div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span className={`badge ${badgeCls}`} style={{ fontSize: '9px', marginRight: '6px' }}>{badgeLabel}</span>
                  <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--tp)' }}>{step.entity || step.name}</span>
                  {step.type && <span style={{ fontSize: '11px', color: 'var(--tm)', marginLeft: '6px' }}>{step.type}</span>}
                </div>
                {!isLast && step.score != null && <span style={{ fontSize: '11px', color: 'var(--ts)' }}>{step.score.toFixed(2)}</span>}
              </div>
              {isLast && step.pattern && (
                <div style={{ fontSize: '11px', color: 'var(--tpke)', marginTop: '4px' }}>Pattern: {step.pattern}</div>
              )}
              {isLast && step.intervention_days && (
                <div style={{ fontSize: '11px', color: 'var(--tpke)', marginTop: '2px' }}>Intervention window: Day −{step.intervention_days}</div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function buildChain(disruption, rootCause) {
  const nodes = []
  if (disruption) nodes.push({ ...disruption })
  if (rootCause && rootCause !== disruption) nodes.push({ ...rootCause })
  return nodes
}
