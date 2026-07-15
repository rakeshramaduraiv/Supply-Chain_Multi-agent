import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import KpiCard from '../components/ui/KpiCard'
import RiskBarChart from '../components/charts/RiskBarChart'
import DeliveryDonut from '../components/charts/DeliveryDonut'
import DataTable from '../components/ui/DataTable'
import ScoreBar from '../components/ui/ScoreBar'
import RiskBadge from '../components/ui/RiskBadge'
import Spinner from '../components/ui/Spinner'
import InfoBox from '../components/ui/InfoBox'

const FEATURE_GROUPS = [
  { group: 'Shipping', color: 'var(--blue)', tags: ['shipping_delay', 'delay_ratio', 'mode_risk_score'] },
  { group: 'Supplier', color: 'var(--inv)', tags: ['supplier_reliability', 'supplier_delay_rate'] },
  { group: 'Demand', color: 'var(--dem)', tags: ['demand_7d', 'demand_trend', 'demand_volatility', 'demand_momentum', 'spike_flag', 'seasonal_index', 'event_boost'] },
  { group: 'Inventory', color: 'var(--log)', tags: ['stockout_risk', 'days_to_reorder', 'inventory_health'] },
  { group: 'Order Value', color: 'var(--ts)', tags: ['order_value_norm', 'profit_ratio'] },
  { group: 'Calendar', color: 'var(--tpke)', tags: ['is_holiday', 'day_of_week', 'month', 'quarter', 'is_month_end'] },
]

export default function DatasetOverview() {
  const summary = useQuery({ queryKey: ['datasetSummary'], queryFn: () => api.getDatasetSummary().then(r => r.data) })
  const analytics = useQuery({ queryKey: ['datasetAnalytics'], queryFn: () => api.getDatasetAnalytics().then(r => r.data) })

  if (summary.isLoading || analytics.isLoading) return <Spinner large text="Computing analytics from DataCo dataset..." />
  if (summary.isError) return <InfoBox type="error">{summary.error?.message || 'Failed to load dataset'}</InfoBox>

  const s = summary.data || {}
  const a = analytics.data || {}

  if (!s.ready) return <InfoBox type="warn">Dataset not processed yet. Run initialization first.</InfoBox>

  const volColumns = [
    { key: 'category', label: 'Category', sortable: true },
    { key: 'score', label: 'Volatility', sortable: true, render: (v) => <ScoreBar value={v} /> },
    { key: 'order_count', label: 'Orders', sortable: true, render: (v) => v?.toLocaleString() },
    { key: '_badge', label: 'Risk', render: (_, row) => <RiskBadge level={row.score >= 0.65 ? 'high' : row.score >= 0.35 ? 'med' : 'low'} /> },
  ]

  const wf = a.walk_forward_split || {}

  return (
    <div className="page active">
      <div className="page-head">
        <div>
          <div className="page-title">Dataset Overview</div>
          <div className="page-sub">DataCo Smart Supply Chain — {s.date_range_start} to {s.date_range_end}</div>
        </div>
        <span className="badge bdg-blue"><span className="bdg-dot" />{s.total_orders?.toLocaleString()} orders · {s.total_categories} categories · {s.total_regions} regions</span>
      </div>

      <div className="g4">
        <KpiCard label="Total Orders" value={s.total_orders?.toLocaleString()} color="var(--blue)" foot="DataCo dataset" />
        <KpiCard label="Late Delivery Rate" value={s.late_delivery_pct} unit="%" color="var(--rh)"
          delta={`${(s.late_delivery_pct - 50).toFixed(1)}% vs 50%`} deltaDir="down" />
        <KpiCard label="Avg Shipping Delay" value={s.avg_shipping_delay} unit="days" color="var(--rm)" foot="Actual − scheduled" />
        <KpiCard label="Supplier Reliability" value={(s.avg_supplier_reliability * 100).toFixed(1)} unit="%" color="var(--inv)" foot="On-time delivery rate" />
      </div>

      <div className="g2">
        <div className="card">
          <div className="card-head"><span className="card-title">Late delivery risk by shipping mode</span></div>
          <div className="card-body">
            {a.shipping_risk?.length > 0
              ? <RiskBarChart data={a.shipping_risk} referenceLine={50} />
              : <Spinner text="Loading..." />
            }
          </div>
        </div>
        <div className="card">
          <div className="card-head"><span className="card-title">Demand volatility by category</span></div>
          <div className="card-body">
            <DataTable columns={volColumns} data={a.category_volatility || []} />
          </div>
        </div>
      </div>

      <div className="g2">
        <div className="card">
          <div className="card-head"><span className="card-title">Order value distribution</span></div>
          <div className="card-body">
            {a.order_value_distribution?.length > 0
              ? <DeliveryDonut data={a.order_value_distribution} />
              : <Spinner text="Loading..." />
            }
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <div><span className="card-title">22 Engineered Features</span><div className="card-meta">All computed from DataCo — no raw identifiers</div></div>
          </div>
          <div className="card-body">
            {FEATURE_GROUPS.map(g => (
              <div key={g.group} style={{ marginBottom: '12px' }}>
                <div className="section-lbl">{g.group}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                  {g.tags.map(t => (
                    <span key={t} style={{
                      display: 'inline-flex', alignItems: 'center', gap: '4px',
                      padding: '3px 8px', borderRadius: '4px',
                      border: '0.5px solid var(--b)', background: 'var(--s2)',
                      fontSize: '11px', color: 'var(--ts)'
                    }}>
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: g.color }} />
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {wf.train_start && (
        <div className="card">
          <div className="card-head"><span className="card-title">Walk-Forward Validation Split</span></div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: '2px', height: '28px', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ flex: wf.train_rows, background: 'var(--s2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', color: 'var(--ts)' }}>
                Training · {wf.train_start} — {wf.train_end}
              </div>
              <div style={{ flex: wf.val_rows, background: 'rgba(91,138,255,.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', color: 'var(--blue)' }}>
                Val · {wf.val_start} — {wf.val_end}
              </div>
              <div style={{ flex: wf.test_rows, background: 'var(--rlb)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', color: 'var(--rl)' }}>
                Test · {wf.test_start} — {wf.test_end}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '2px', marginTop: '4px' }}>
              <div style={{ flex: wf.train_rows, textAlign: 'center', fontSize: '10px', color: 'var(--tm)' }}>~{(wf.train_rows / 1000).toFixed(0)}K rows</div>
              <div style={{ flex: wf.val_rows, textAlign: 'center', fontSize: '10px', color: 'var(--tm)' }}>~{(wf.val_rows / 1000).toFixed(0)}K rows</div>
              <div style={{ flex: wf.test_rows, textAlign: 'center', fontSize: '10px', color: 'var(--tm)' }}>~{(wf.test_rows / 1000).toFixed(0)}K rows</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
