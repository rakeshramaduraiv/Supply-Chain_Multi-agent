import DataTable from '../ui/DataTable'
import ScoreBar from '../ui/ScoreBar'
import RiskBadge from '../ui/RiskBadge'

export default function ForecastTable({ data = [], onViewContext }) {
  const columns = [
    { key: 'category', label: 'Category', sortable: true },
    { key: 'region', label: 'Region', sortable: true },
    { key: 'demand_7d', label: 'Demand 7d', sortable: true, render: (v) => v?.toFixed(0) || '—' },
    { key: 'stockout_risk', label: 'Stockout', sortable: true, render: (v) => <ScoreBar value={v || 0} /> },
    { key: 'supplier_risk', label: 'Supplier', sortable: true, render: (v) => <ScoreBar value={v || 0} /> },
    { key: 'logistics_risk', label: 'Logistics', sortable: true, render: (v) => <ScoreBar value={v || 0} /> },
    { key: 'combined_risk', label: 'Combined', sortable: true, render: (v) => {
      const level = v >= 0.65 ? 'high' : v >= 0.35 ? 'med' : 'low'
      return <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><ScoreBar value={v || 0} /><RiskBadge level={level} /></div>
    }},
    { key: '_ctx', label: '', render: (_, row) => (
      <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onViewContext?.(row) }}>View</button>
    )},
  ]
  return <DataTable columns={columns} data={data} />
}
