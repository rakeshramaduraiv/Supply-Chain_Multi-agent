export default function StepIndicator({ steps, current }) {
  return (
    <div className="steps">
      {steps.map((s, i) => {
        const done = i < current
        const active = i === current
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
            <div className={`step${active ? ' active' : ''}${done ? ' done' : ''}`}>
              <div className="step-num">{done ? '✓' : i + 1}</div>
              <span className="step-label">{s}</span>
            </div>
            {i < steps.length - 1 && <div className={`step-line${done ? ' done' : ''}`} />}
          </div>
        )
      })}
    </div>
  )
}
