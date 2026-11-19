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
  const cats = (Array.isArray(categoryForecasts) && categoryForecasts.length > 0) ? categoryForecasts : []

  const totalDemand  = cats.length > 0 ? cats.reduce((s, c) => s + (c.predicted_demand || 0), 0) : null
  const lateRiskCats = cats.filter(c => c.late_delivery_risk != null)
  const avgLateRisk  = lateRiskCats.length > 0 ? lateRiskCats.reduce((s, c) => s + c.late_delivery_risk, 0) / lateRiskCats.length : null
  const shipDaysCats = cats.filter(c => c.avg_shipping_days != null)
  const avgShipDays  = shipDaysCats.length > 0 ? shipDaysCats.reduce((s, c) => s + c.avg_shipping_days, 0) / shipDaysCats.length : null
  const topCat       = cats.length > 0 ? [...cats].sort((a, b) => (b.predicted_demand || 0) - (a.predicted_demand || 0))[0] : null
  const highestRiskCat = cats.length > 0 ? [...cats].sort((a, b) => (b.late_delivery_risk || 0) - (a.late_delivery_risk || 0))[0] : null

  const demandConf   = overallConf != null ? round(overallConf * 100, 1) : null
  const supConf      = overallConf != null ? round(overallConf * 100, 1) : null
  const logConf      = overallConf != null ? round(overallConf * 100, 1) : null

  const p = forecastAnimating ? forecastTick / 100 : 1
  const animDemand   = totalDemand != null ? (forecastAnimating ? Math.round(totalDemand * p) : totalDemand) : null
  const animLateRisk = avgLateRisk != null ? (forecastAnimating ? (avgLateRisk * p * 100).toFixed(1) : (avgLateRisk * 100).toFixed(1)) : null
  const animShipDays = avgShipDays != null ? (forecastAnimating ? (avgShipDays * p).toFixed(2) : avgShipDays.toFixed(2)) : null
  const animConf     = demandConf != null ? (forecastAnimating ? round(demandConf * p, 1) : demandConf) : null

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
          <span className="badge bdg-low">{animConf != null ? `${animConf}% Conf` : <span title="Confidence unknown">—</span>}</span>
        </div>
        <div className={styles.agentPredVal} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span>{animDemand != null ? `${animDemand.toLocaleString()} Units` : <span title="Demand value unknown">—</span>}</span>
          {forecastAnimating && <span style={{ fontSize: 10, color: 'var(--blue)', fontWeight: 700 }}>computing…</span>}
        </div>
        {ingestedTotal != null && !forecastAnimating && (
          <div style={{ fontSize: '10px', display: 'flex', gap: 8, marginBottom: 2 }}>
            <span style={{ color: '#00b894', fontWeight: 700 }}>✓ Actual: {ingestedTotal.toLocaleString()}</span>
            {ingestedForecast != null && (
              <span style={{ color: ingestedTotal < ingestedForecast ? '#d63031' : '#00b894', fontWeight: 700 }}>
                {ingestedTotal < ingestedForecast ? '▼' : '▲'} {Math.abs(ingestedTotal - ingestedForecast).toLocaleString()} units
              </span>
            )}
          </div>
        )}
        <div style={{ fontSize: '10px', color: '#00b894', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ArrowUpRight size={12} /> Forecast Period: {cycleMonth || '—'} · {cats.length} categories
        </div>
        <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--ts)', marginTop: '4px' }}>Supporting Features (LightGBM):</div>
        <div className={styles.featureList}>
          {demandFeatures.map((feat, i) => <FeatureBar key={i} feat={feat} color="var(--blue)" />)}
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '6px' }}>
          Top Category: {topCat?.category || <span title="Category unknown">—</span>} · Region: {topCat?.region || <span title="Region unknown">—</span>}
        </div>
      </div>

      {/* Supplier Agent */}
      <div className={styles.agentCard} style={forecastAnimating ? { border: '1.5px solid #e67e22', boxShadow: '0 0 0 2px rgba(230,126,34,0.12)' } : {}}>
        <div className={styles.agentHead}>
          <div className={styles.agentName}><Factory size={15} style={{ color: '#e67e22' }} /> Supplier Agent</div>
          <span className="badge bdg-med">{supConf != null ? `${supConf}% Conf` : <span title="Confidence unknown">—</span>}</span>
        </div>
        <div className={styles.agentPredVal} style={{ color: '#e67e22', display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span>{animLateRisk != null ? `${animLateRisk}% Risk` : <span title="Risk value unknown">—</span>}</span>
          {forecastAnimating && <span style={{ fontSize: 10, color: '#e67e22', fontWeight: 700 }}>computing…</span>}
        </div>
        <div style={{ fontSize: '10px', color: '#e67e22', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ArrowUpRight size={12} /> Late Delivery Risk · {cycleMonth || '—'}
        </div>
        <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--ts)', marginTop: '4px' }}>Supporting Features (LightGBM):</div>
        <div className={styles.featureList}>
          {supplierFeatures.map((feat, i) => <FeatureBar key={i} feat={feat} color="#e67e22" />)}
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '6px' }}>
          Highest Risk: {highestRiskCat?.category || <span title="Category unknown">—</span>} corridor
        </div>
      </div>

      {/* Logistics Agent */}
      <div className={styles.agentCard} style={forecastAnimating ? { border: '1.5px solid #d63031', boxShadow: '0 0 0 2px rgba(214,48,49,0.12)' } : {}}>
        <div className={styles.agentHead}>
          <div className={styles.agentName}><Truck size={15} style={{ color: '#d63031' }} /> Logistics Agent</div>
          <span className="badge bdg-high">{logConf != null ? `${logConf}% Conf` : <span title="Confidence unknown">—</span>}</span>
        </div>
        <div className={styles.agentPredVal} style={{ color: '#d63031', display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span>{animShipDays != null ? `${animShipDays}d Delay` : <span title="Delay value unknown">—</span>}</span>
          {forecastAnimating && <span style={{ fontSize: 10, color: '#d63031', fontWeight: 700 }}>computing…</span>}
        </div>
        <div style={{ fontSize: '10px', color: '#d63031', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ArrowUpRight size={12} /> Avg Shipping Delay · {cycleMonth || '—'}
        </div>
        <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--ts)', marginTop: '4px' }}>Supporting Features (LightGBM):</div>
        <div className={styles.featureList}>
          {logisticsFeatures.map((feat, i) => <FeatureBar key={i} feat={feat} color="#d63031" />)}
        </div>
        <div style={{ fontSize: '9.5px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '6px' }}>
          Shipping Route Analysis · Shipment {cycleMonth || '—'}
        </div>
      </div>
    </div>
  )
}
