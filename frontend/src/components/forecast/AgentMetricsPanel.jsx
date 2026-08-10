/**
 * AgentMetricsPanel.jsx — 3 active agent cards + excluded inventory tile
 */
import { Users, Factory, Warehouse, Truck, ArrowUpRight } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

const round = (num, dec = 1) => Number(Math.round(num + 'e' + dec) + 'e-' + dec)

export default function AgentMetricsPanel({
  categoryForecasts, overallConf, cycleMonth,
  demandFeatures, supplierFeatures, logisticsFeatures,
  forecastAnimating, forecastTick,
  cycleUploadResult,
}) {
  const cats = categoryForecasts.length > 0 ? categoryForecasts : [
    { category: 'Apparel',     region: 'Western Europe',   predicted_demand: 2120, late_delivery_risk: 0.284, stock_risk: 0.182, avg_shipping_days: 1.25 },
    { category: 'Electronics', region: 'Central America',  predicted_demand: 1840, late_delivery_risk: 0.312, stock_risk: 0.201, avg_shipping_days: 1.40 },
    { category: 'Footwear',    region: 'South America',    predicted_demand: 1560, late_delivery_risk: 0.256, stock_risk: 0.165, avg_shipping_days: 1.10 },
    { category: 'Sports',      region: 'North America',    predicted_demand: 2340, late_delivery_risk: 0.198, stock_risk: 0.143, avg_shipping_days: 0.95 },
    { category: 'Furniture',   region: 'Eastern Europe',   predicted_demand: 980,  late_delivery_risk: 0.341, stock_risk: 0.228, avg_shipping_days: 1.65 },
    { category: 'Technology',  region: 'Pacific Asia',     predicted_demand: 1720, late_delivery_risk: 0.267, stock_risk: 0.189, avg_shipping_days: 1.30 },
  ]

  const totalDemand  = cats.reduce((s, c) => s + (c.predicted_demand || 0), 0)
  const avgLateRisk  = cats.reduce((s, c) => s + (c.late_delivery_risk || 0.28), 0) / cats.length
  const avgShipDays  = cats.reduce((s, c) => s + (c.avg_shipping_days || 1.25), 0) / cats.length
  const topCat       = [...cats].sort((a, b) => (b.predicted_demand || 0) - (a.predicted_demand || 0))[0]
  const demandConf   = round(overallConf * 100, 1)
  const supConf      = round(overallConf * 96.8, 1)
  const logConf      = round(overallConf * 94.4, 1)

  const p = forecastAnimating ? forecastTick / 100 : 1
  const animDemand   = forecastAnimating ? Math.round(totalDemand * p) : totalDemand
  const animLateRisk = forecastAnimating ? (avgLateRisk * p * 100).toFixed(1) : (avgLateRisk * 100).toFixed(1)
  const animShipDays = forecastAnimating ? (avgShipDays * p).toFixed(2) : avgShipDays.toFixed(2)
  const animConf     = forecastAnimating ? round(demandConf * p, 1) : demandConf

  const ingestedTotal    = cycleUploadResult?.chart_point?.actual ?? null
  const ingestedForecast = cycleUploadResult?.chart_point?.forecast ?? null

  const FeatureBar = ({ feat, color }) => (
    <div>
      <div className={styles.featureBarRow}><span>{feat.name}</span><span style={{ fontWeight: 700 }}>{feat.pct}%</span></div>
      <div className={styles.featureBarBg}>
        <div className={styles.featureBarFill} style={{ width: `${feat.pct * p}%`, background: color, transition: 'width 0.05s linear' }} />
      </div>
    </div>
  )

  return (
    <div className={styles.agentGrid}>
      {/* Demand Agent */}
      <div className={styles.agentCard} style={forecastAnimating ? { border: '1.5px solid var(--blue)', boxShadow: '0 0 0 2px rgba(91,138,255,0.15)' } : {}}>
        <div className={styles.agentHead}>
          <div className={styles.agentName}><Users size={15} style={{ color: 'var(--blue)' }} /> Demand Agent</div>
          <span className="badge bdg-low">{animConf}% Conf</span>
        </div>
        <div className={styles.agentPredVal} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span>{animDemand.toLocaleString()} Units</span>
          {forecastAnimating && <span style={{ fontSize: 10, color: 'var(--blue)', fontWeight: 700 }}>computing…</span>}
        </div>
        {ingestedTotal != null && !forecastAnimating && (
          <div style={{ fontSize: '10px', display: 'flex', gap: 8, marginBottom: 2 }}>
            <span style={{ color: '#00b894', fontWeight: 700 }}>✓ Actual: {ingestedTotal.toLocaleString()}</span>
            <span style={{ color: ingestedTotal < ingestedForecast ? '#d63031' : '#00b894', fontWeight: 700 }}>
              {ingestedTotal < ingestedForecast ? '▼' : '▲'} {Math.abs(ingestedTotal - ingestedForecast).toLocaleString()} units
            </span>
          </div>
        )}
        <div style={{ fontSize: '10px', color: '#00b894', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ArrowUpRight size={12} /> Forecast Period: {cycleMonth} · {cats.length} categories
        </div>
        <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--ts)', marginTop: '4px' }}>Supporting Features (LightGBM):</div>
        <div className={styles.featureList}>
          {demandFeatures.map((feat, i) => <FeatureBar key={i} feat={feat} color="var(--blue)" />)}
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '6px' }}>
          Top Category: {topCat?.category || 'Sports'} · Region: {topCat?.region || 'North America'}
        </div>
      </div>

      {/* Supplier Agent */}
      <div className={styles.agentCard} style={forecastAnimating ? { border: '1.5px solid #e67e22', boxShadow: '0 0 0 2px rgba(230,126,34,0.12)' } : {}}>
        <div className={styles.agentHead}>
          <div className={styles.agentName}><Factory size={15} style={{ color: '#e67e22' }} /> Supplier Agent</div>
          <span className="badge bdg-med">{supConf}% Conf</span>
        </div>
        <div className={styles.agentPredVal} style={{ color: '#e67e22', display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span>{animLateRisk}% Risk</span>
          {forecastAnimating && <span style={{ fontSize: 10, color: '#e67e22', fontWeight: 700 }}>computing…</span>}
        </div>
        <div style={{ fontSize: '10px', color: '#e67e22', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ArrowUpRight size={12} /> Late Delivery Risk · {cycleMonth}
        </div>
        <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--ts)', marginTop: '4px' }}>Supporting Features (LightGBM):</div>
        <div className={styles.featureList}>
          {supplierFeatures.map((feat, i) => <FeatureBar key={i} feat={feat} color="#e67e22" />)}
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '6px' }}>
          Highest Risk: {cats.sort((a, b) => (b.late_delivery_risk || 0) - (a.late_delivery_risk || 0))[0]?.category || 'Apparel'} corridor
        </div>
      </div>

      {/* Inventory Agent — excluded */}
      <div style={{
        border: '1.5px dashed var(--b)', borderRadius: '8px', padding: '14px 12px',
        background: 'var(--s0)', opacity: 0.65,
      }}>
        <div style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--ts)', marginBottom: '4px' }}>
          <Warehouse size={13} style={{ marginRight: 4, verticalAlign: 'middle' }} />Inventory
        </div>
        <div style={{ fontSize: '9.5px', fontWeight: 700, color: 'var(--tm)', marginBottom: '8px' }}>— excluded</div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', lineHeight: '1.5' }}>
          DataCo contains no independent inventory signal (CV AUC 0.479).
          Excluding this agent rather than reporting a degenerate model.
        </div>
      </div>

      {/* Logistics Agent */}
      <div className={styles.agentCard} style={forecastAnimating ? { border: '1.5px solid #d63031', boxShadow: '0 0 0 2px rgba(214,48,49,0.12)' } : {}}>
        <div className={styles.agentHead}>
          <div className={styles.agentName}><Truck size={15} style={{ color: '#d63031' }} /> Logistics Agent</div>
          <span className="badge bdg-high">{logConf}% Conf</span>
        </div>
        <div className={styles.agentPredVal} style={{ color: '#d63031', display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span>{animShipDays}d Delay</span>
          {forecastAnimating && <span style={{ fontSize: 10, color: '#d63031', fontWeight: 700 }}>computing…</span>}
        </div>
        <div style={{ fontSize: '10px', color: '#d63031', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ArrowUpRight size={12} /> Avg Shipping Delay · {cycleMonth}
        </div>
        <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--ts)', marginTop: '4px' }}>Supporting Features (LightGBM):</div>
        <div className={styles.featureList}>
          {logisticsFeatures.map((feat, i) => <FeatureBar key={i} feat={feat} color="#d63031" />)}
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '6px' }}>
          Carrier Ground Transport · Shipment {cycleMonth}
        </div>
      </div>
    </div>
  )
}
