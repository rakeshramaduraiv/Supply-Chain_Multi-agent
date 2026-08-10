// src/components/figures/Fig4ROC.jsx
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip,
} from 'recharts'
import { api } from '../../api/client'
import FigureShell from './FigureShell'
import { PALETTE, FONT, NO_ANIMATION, AXIS_STYLE } from './figureTheme'

const DIAGONAL = Array.from({ length: 11 }, (_, i) => ({ fpr: i / 10, tpr: i / 10 }))

const AGENT_STYLE = {
  Logistics: { color: PALETTE.green,   dash: undefined, width: 2.4 },
  Supplier:  { color: PALETTE.primary, dash: undefined, width: 2.4 },
  Inventory: { color: PALETTE.grey,    dash: '6 4',     width: 1.8 },
}

const Tip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1e293b', borderRadius: 8, padding: '8px 12px', fontSize: 12, color: '#f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,.3)' }}>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: TPR=<b>{Number(p.value).toFixed(3)}</b>
        </div>
      ))}
    </div>
  )
}

// Rotated "Random chance" text near diagonal midpoint
const DiagonalLabel = () => (
  <text
    x={310} y={290}
    transform="rotate(-45, 310, 290)"
    textAnchor="middle"
    fontSize={11}
    fill="#888"
  >
    Random chance
  </text>
)

export default function Fig4ROC() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['figures', 'roc-curves'],
    queryFn: () => api.getRocCurves().then(r => r.data),
    staleTime: 120_000, retry: 2,
  })

  const curves = Array.isArray(data) ? data : []

  return (
    <FigureShell
      figureNumber={4}
      title="ROC Curves for Deployed Classifiers"
      emptyMessage={!isLoading && !isError && curves.length === 0
        ? 'No stored predictions found — persist walk-forward test predictions.' : undefined}
      loading={isLoading}
      error={isError ? 'Failed to load ROC curves' : undefined}
      caption="Both deployed classifiers exceed random chance on held-out walk-forward folds. The Inventory agent did not and was excluded from deployment."
    >
      <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', justifyContent: 'center' }}>
        {/* Square chart */}
        <div style={{ position: 'relative' }}>
          <LineChart width={620} height={620} margin={{ top: 20, right: 20, left: 20, bottom: 50 }}>
              <CartesianGrid strokeDasharray="" stroke={PALETTE.gridline} />
              <XAxis
                type="number" dataKey="fpr" domain={[0, 1]} name="FPR"
                tick={{ fontSize: FONT.tick, fill: '#333' }}
                axisLine={false} tickLine={false}
                label={{ value: 'False positive rate', position: 'insideBottom', offset: -24, style: AXIS_STYLE.label }}
              />
              <YAxis
                type="number" dataKey="tpr" domain={[0, 1]} name="TPR"
                tick={{ fontSize: FONT.tick, fill: '#333' }}
                axisLine={false} tickLine={false}
                label={{ value: 'True positive rate', angle: -90, position: 'insideLeft', offset: 16, style: AXIS_STYLE.label }}
              />
              <Tooltip content={<Tip />} />

              {/* Diagonal */}
              <Line
                data={DIAGONAL} dataKey="tpr" name="Random chance"
                stroke="#999999" strokeDasharray="5 4" strokeWidth={1.5}
                dot={false} {...NO_ANIMATION}
              />

              {/* Agent curves */}
              {curves.map(c => {
                const s = AGENT_STYLE[c.agent] || { color: PALETTE.grey, width: 2 }
                return (
                  <Line
                    key={c.agent}
                    data={c.points} dataKey="tpr"
                    name={`${c.agent}${c.excluded ? ' (excluded)' : ''}  —  AUC = ${Number(c.auc).toFixed(2)}`}
                    stroke={s.color}
                    strokeWidth={s.width}
                    strokeDasharray={s.dash}
                    dot={false}
                    {...NO_ANIMATION}
                  />
                )
              })}
          </LineChart>
          {/* Rotated diagonal label overlay */}
          <svg style={{ position: 'absolute', top: 0, left: 0, width: 620, height: 620, pointerEvents: 'none' }}>
            <DiagonalLabel />
          </svg>
        </div>

        {/* Legend bottom-right, no frame */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 480, fontSize: FONT.legend }}>
          {curves.map(c => {
            const s = AGENT_STYLE[c.agent] || { color: PALETTE.grey }
            return (
              <div key={c.agent} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 24, height: 3, background: s.color, display: 'inline-block', borderRadius: 2 }} />
                <span style={{ color: '#333' }}>
                  {c.agent}{c.excluded ? ' (excluded)' : ''}  —  AUC = {Number(c.auc).toFixed(2)}
                </span>
              </div>
            )
          })}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 24, height: 2, background: '#999', display: 'inline-block', borderStyle: 'dashed', borderWidth: 1, borderColor: '#999' }} />
            <span style={{ color: '#888' }}>Random chance</span>
          </div>
        </div>
      </div>
    </FigureShell>
  )
}
