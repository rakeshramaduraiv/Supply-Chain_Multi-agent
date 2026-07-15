import DataTable from '../ui/DataTable'
import RiskBadge from '../ui/RiskBadge'
import ForecastVsActual from '../charts/ForecastVsActual'
import EmptyState from '../ui/EmptyState'

function gradeLevel(score, metric) {
  if (metric === 'MAPE') return score < 15 ? 'low' : score < 30 ? 'med' : 'high'
  return score >= 0.8 ? 'low' : score >= 0.6 ? 'med' : 'high'
}

function gradeLetter(score, metric) {
  if (metric === 'MAPE') return score < 10 ? 'A' : score < 15 ? 'B' : score < 25 ? 'C' : score < 35 ? 'D' : 'F'
  return score >= 0.9 ? 'A' : score >= 0.8 ? 'B' : score >= 0.7 ? 'C' : score >= 0.6 ? 'D' : 'F'
}

export default function AccuracyPanel({ accuracy, chartData }) {
  if (!accuracy) return <EmptyState title="Upload actuals to see accuracy" />

  const rows = [
    { agent: 'Demand', metric: 'MAPE', score: accuracy.demand_mape, _metric: 'MAPE' },
    { agent: 'Inventory', metric: 'F1', score: accuracy.inventory_f1, _metric: 'F1' },
    { agent: 'Supplier', metric: 'F1 + AUC', score: accuracy.supplier_f1, _metric: 'F1' },
    { agent: 'Logistics', metric: 'F1', score: accuracy.logistics_f1, _metric: 'F1' },
  ]

  const columns = [
    { key: 'agent', label: 'Agent' },
    { key: 'metric', label: 'Metric' },
    { key: 'score', label: 'Score', render: (v) => v != null ? v.toFixed(2) : '—' },
    { key: '_grade', label: 'Grade', render: (_, row) => {
      const letter = gradeLetter(row.score, row._metric)
      const level = gradeLevel(row.score, row._metric)
      return <RiskBadge level={level} label={letter} />
    }},
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div className="section-lbl">Agent Accuracy</div>
      <DataTable columns={columns} data={rows} />
      {chartData && <ForecastVsActual data={chartData} />}
    </div>
  )
}
