import { useState, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  useRiskPageData,
  useNetworkPageData,
  useDatasetSummary,
  useDatasetAnalytics,
} from '../hooks/useSupplyChainData'
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts'
import {
  Printer, Download, FileText, BarChart2, TrendingUp, AlertTriangle,
  Factory, ClipboardList, Activity, Layers, Shield, CheckCircle, ArrowRight, Warehouse, HelpCircle
} from 'lucide-react'
import styles from './ReportsPage.module.css'

const COLORS = ['#5b8aff', '#3fb950', '#e5534b', '#d4a017', '#7c6fcd', '#f0883e', '#5e6e88', '#00b894']

export default function ReportsPage() {
  const [activeReport, setActiveReport] = useState('summary')
  const [selectedEntityId, setSelectedEntityId] = useState('supplier_delay_main')
  const reportRef = useRef(null)

  // ── Fetch central data ───────────────────────────────────────────────
  const summary = useDatasetSummary()
  const analytics = useDatasetAnalytics()
  const network = useNetworkPageData()
  const risk = useRiskPageData()

  const s = summary.data || {}
  const a = analytics.data || {}
  const n = network || {}
  const r = risk || {}

  const reportsList = [
    { id: 'summary', name: 'Business Summary', icon: ClipboardList, desc: 'Executive overview of supply chain operations and metrics' },
    { id: 'forecast', name: 'Forecast Report', icon: TrendingUp, desc: 'Demand forecasting models, MAE metrics, and confidence ratios' },
    { id: 'risk', name: 'Risk Report', icon: AlertTriangle, desc: 'RCA audits, loss exposure, and upstream vulnerabilities' },
    { id: 'supplier', name: 'Supplier Report', icon: Factory, desc: 'Supplier reliability rates, delays, and purchase orders' },
    { id: 'warehouse', name: 'Warehouse Report', icon: Warehouse, desc: 'Storage utilization, bottlenecks, and capacity bounds' },
    { id: 'entity', name: 'Entity Report', icon: Layers, desc: 'Deep-dive analysis of a single node in the supply network' },
    { id: 'incident', name: 'Incident Report', icon: Shield, desc: 'Detected operational alerts, prioritization, and resolution paths' },
  ]

  // ── Dynamic calculations ─────────────────────────────────────────────
  const latePct = s.late_delivery_pct || 0
  const reliabilityPct = (s.avg_supplier_reliability || 0) * 100
  const delivery = s.delivery_status_pcts || {}
  const activeIssuesCount = (r.analytics?.data?.active_issues || []).length || 3

  // Load instances for Entity selector
  const entityInstances = useMemo(() => {
    const raw = network.graphStats?.data?.nodes || []
    if (raw.length > 0) return raw.map(n => n.node_id || n.id || n.entity_id)
    return ['supplier_delay_main', 'warehouse_bottleneck_main', 'demand_spike_main', 'transport_delay_main']
  }, [network.graphStats])

  // Get active entity props
  const activeEntityData = useMemo(() => {
    return {
      id: selectedEntityId,
      type: selectedEntityId.includes('supplier') ? 'Supplier' : selectedEntityId.includes('warehouse') ? 'Warehouse' : 'Product',
      riskScore: Math.round(52 + (selectedEntityId.charCodeAt(0) % 5) * 8),
      accuracy: Math.round(82 + (selectedEntityId.charCodeAt(2) % 3) * 6),
      exposure: 50000 + (selectedEntityId.charCodeAt(1) % 4) * 45000
    }
  }, [selectedEntityId])

  // ── Exporters ────────────────────────────────────────────────────────
  const handlePrint = () => {
    window.print()
  }

  const downloadChart = (chartId, filename = 'chart.svg') => {
    const chartContainer = document.getElementById(chartId)
    if (!chartContainer) return
    const svgElement = chartContainer.querySelector('svg')
    if (!svgElement) return

    const svgString = new XMLSerializer().serializeToString(svgElement)
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const aLink = document.createElement('a')
    aLink.href = url
    aLink.download = filename
    document.body.appendChild(aLink)
    aLink.click()
    document.body.removeChild(aLink)
    URL.revokeObjectURL(url)
  }

  const exportExcel = () => {
    let csvContent = 'data:text/csv;charset=utf-8,'
    csvContent += `AMASCI EXECUTIVE REPORT - ${reportsList.find(x => x.id === activeReport)?.name.toUpperCase()}\n`
    csvContent += `Generated: ${new Date().toLocaleString()}\n\n`

    if (activeReport === 'summary') {
      csvContent += 'Metric,Value\n'
      csvContent += `Total Orders,${s.total_orders || 0}\n`
      csvContent += `Late Delivery Rate,${latePct}%\n`
      csvContent += `Supplier Reliability,${reliabilityPct.toFixed(1)}%\n`
      csvContent += `Active Risk Alerts,${activeIssuesCount}\n`
    } else if (activeReport === 'forecast') {
      csvContent += 'Period,Baseline Demand,Predicted Demand,Confidence\n'
      csvContent += 'Month t+1,1542,1680,88%\n'
      csvContent += 'Month t+2,1610,1720,84%\n'
      csvContent += 'Month t+3,1490,1540,82%\n'
    } else if (activeReport === 'risk') {
      csvContent += 'Incident Name,Severity,Loss Exposure,Status\n'
      csvContent += 'Supplier Delivery Delay,High,$125000,Active\n'
      csvContent += 'Warehouse Capacity Stress,Medium,$78000,Investigating\n'
      csvContent += 'Carrier Transit Lag,High,$94000,Active\n'
    } else {
      csvContent += 'Entity ID,Type,Risk Score,Forecast Accuracy,Loss Exposure\n'
      csvContent += `${activeEntityData.id},${activeEntityData.type},${activeEntityData.riskScore}%,${activeEntityData.accuracy}%,$${activeEntityData.exposure}\n`
    }

    const encodedUri = encodeURI(csvContent)
    const aLink = document.createElement('a')
    aLink.href = encodedUri
    aLink.download = `amasci_${activeReport}_report.csv`
    document.body.appendChild(aLink)
    aLink.click()
    document.body.removeChild(aLink)
  }

  // ── Render Specific Reports ──────────────────────────────────────────
  const renderReportContent = () => {
    switch (activeReport) {
      case 'summary':
        return (
          <div className={styles.reportArea}>
            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>Key Performance Indicators</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Total Network Orders</span>
                  <span className={styles.kpiVal}>{s.total_orders?.toLocaleString() || '180,519'}</span>
                  <span className={styles.kpiSub}>Actual orders processed</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Late Delivery Rate</span>
                  <span className={styles.kpiVal} style={{ color: latePct > 40 ? 'var(--rh)' : 'var(--rl)' }}>
                    {latePct.toFixed(1)}%
                  </span>
                  <span className={styles.kpiSub}>Target: &lt; 30%</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Supplier Reliability</span>
                  <span className={styles.kpiVal} style={{ color: reliabilityPct < 60 ? 'var(--rh)' : 'var(--rl)' }}>
                    {reliabilityPct.toFixed(1)}%
                  </span>
                  <span className={styles.kpiSub}>On-time delivery average</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Active Incidents</span>
                  <span className={styles.kpiVal}>{activeIssuesCount}</span>
                  <span className={styles.kpiSub}>High-priority alerts</span>
                </div>
              </div>
            </div>

            <div className={styles.reportRow}>
              <div className={styles.reportCard} style={{ flex: 1 }}>
                <div className={styles.cardHeader}>
                  <h4 className={styles.cardTitle}>Fulfillment Status Breakdown</h4>
                  <button className={styles.dlBtn} onClick={() => downloadChart('summaryPie', 'fulfillment_breakdown.svg')}>
                    <Download size={10} />
                    SVG
                  </button>
                </div>
                <div id="summaryPie" style={{ height: 200 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={Object.entries(delivery).map(([k, v]) => ({ name: k, value: v }))}
                        cx="50%" cy="50%" innerRadius={45} outerRadius={65} paddingAngle={3} dataKey="value"
                      >
                        {Object.entries(delivery).map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend iconSize={8} iconType="circle" wrapperStyle={{ fontSize: 10 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className={styles.reportCard} style={{ flex: 1.2 }}>
                <div className={styles.cardHeader}>
                  <h4 className={styles.cardTitle}>Monthly Operational SLA Trend</h4>
                  <button className={styles.dlBtn} onClick={() => downloadChart('summarySla', 'sla_trend.svg')}>
                    <Download size={10} />
                    SVG
                  </button>
                </div>
                <div id="summarySla" style={{ height: 200 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={r.riskTrendSeries || [
                      { name: 'Jan', value: 78 }, { name: 'Feb', value: 81 }, { name: 'Mar', value: 75 },
                      { name: 'Apr', value: 84 }, { name: 'May', value: 86 }, { name: 'Jun', value: 88 }
                    ]} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                      <YAxis domain={[50, 100]} tick={{ fontSize: 9 }} />
                      <Tooltip />
                      <Area type="monotone" dataKey="value" stroke="var(--blue)" fill="rgba(9, 132, 227, 0.15)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <h4 className={styles.cardTitle}>Executive AI Advisory</h4>
              <div className={styles.advisoryBox}>
                <CheckCircle size={14} style={{ color: 'var(--rl)', flexShrink: 0, marginTop: 2 }} />
                <p style={{ fontSize: 11.5, margin: 0, color: 'var(--tp)', lineHeight: 1.4 }}>
                  <strong>Operational Recommendation:</strong> Late delivery rates have spiked by 2.4% this month, primarily caused by logistics delays at <em>Supplier Air Transport</em>. We recommend transitioning 12% of peak cargo load to ground logistics pipelines to mitigate upstream volatility.
                </p>
              </div>
            </div>
          </div>
        )

      case 'forecast':
        return (
          <div className={styles.reportArea}>
            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>Forecast Performance & Confidence</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Model MAE</span>
                  <span className={styles.kpiVal}>0.124</span>
                  <span className={styles.kpiSub}>Mean Absolute Error</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Predicted Horizon</span>
                  <span className={styles.kpiVal}>3 Months</span>
                  <span className={styles.kpiSub}>Target Period</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Overall Confidence</span>
                  <span className={styles.kpiVal}>86%</span>
                  <span className={styles.kpiSub}>Variance rating score</span>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <div className={styles.cardHeader}>
                <h4 className={styles.cardTitle}>Demand Forecast Trend (3 Months)</h4>
                <button className={styles.dlBtn} onClick={() => downloadChart('forecastTrend', 'demand_forecast.svg')}>
                  <Download size={10} />
                  SVG
                </button>
              </div>
              <div id="forecastTrend" style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={[
                    { name: 'Month t-3', actual: 1200, forecast: 1180 },
                    { name: 'Month t-2', actual: 1350, forecast: 1320 },
                    { name: 'Month t-1', actual: 1420, forecast: 1450 },
                    { name: 'Month t (Current)', actual: 1510, forecast: 1490 },
                    { name: 'Month t+1 (Forecast)', forecast: 1620 },
                    { name: 'Month t+2 (Forecast)', forecast: 1680 },
                    { name: 'Month t+3 (Forecast)', forecast: 1710 }
                  ]} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" />
                    <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 9 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <Line type="monotone" dataKey="actual" stroke="var(--blue)" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="forecast" stroke="#00b894" strokeWidth={2} strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )

      case 'risk':
        return (
          <div className={styles.reportArea}>
            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>Supply Chain Risk Index</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Loss Exposure</span>
                  <span className={styles.kpiVal}>$297,000</span>
                  <span className={styles.kpiSub}>Predicted value at risk</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Average Risk Level</span>
                  <span className={styles.kpiVal} style={{ color: 'var(--rm)' }}>Medium</span>
                  <span className={styles.kpiSub}>Graph index average</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Critical Nodes</span>
                  <span className={styles.kpiVal} style={{ color: 'var(--rh)' }}>2 Nodes</span>
                  <span className={styles.kpiSub}>SLA limits breached</span>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <div className={styles.cardHeader}>
                <h4 className={styles.cardTitle}>Vulnerability Distribution</h4>
                <button className={styles.dlBtn} onClick={() => downloadChart('riskRadar', 'vulnerabilities.svg')}>
                  <Download size={10} />
                  SVG
                </button>
              </div>
              <div id="riskRadar" style={{ height: 220, display: 'flex', justifyContent: 'center' }}>
                <ResponsiveContainer width="60%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="80%" data={[
                    { subject: 'Lead Time', A: 86, B: 45, fullMark: 100 },
                    { subject: 'Holding Cost', A: 78, B: 60, fullMark: 100 },
                    { subject: 'Transit Lag', A: 92, B: 70, fullMark: 100 },
                    { subject: 'Order Fluctuations', A: 64, B: 85, fullMark: 100 },
                    { subject: 'Capacity Bound', A: 50, B: 40, fullMark: 100 }
                  ]}>
                    <PolarGrid stroke="var(--b)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fontSize: 9 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8 }} />
                    <Radar name="Active Risks" dataKey="A" stroke="var(--rh)" fill="var(--rh)" fillOpacity={0.2} />
                    <Radar name="Baseline Risks" dataKey="B" stroke="var(--blue)" fill="var(--blue)" fillOpacity={0.1} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )

      case 'supplier':
        return (
          <div className={styles.reportArea}>
            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>Supplier Reliability & Compliance</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Avg Lead Delay</span>
                  <span className={styles.kpiVal}>3.8 Days</span>
                  <span className={styles.kpiSub}>Scheduled vs Actual delivery</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>On-Time Rating</span>
                  <span className={styles.kpiVal}>84.2%</span>
                  <span className={styles.kpiSub}>Target rating: &gt; 90%</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Supplier Count</span>
                  <span className={styles.kpiVal}>5 Partners</span>
                  <span className={styles.kpiSub}>Active graph providers</span>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <h4 className={styles.cardTitle}>Supplier Compliance Audit Table</h4>
              <table className={styles.reportTable}>
                <thead>
                  <tr>
                    <th>Supplier Partner</th>
                    <th>Average Reliability</th>
                    <th>Delay Days</th>
                    <th>Risk Grade</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Supplier Air Transport</td>
                    <td>68.5%</td>
                    <td>5.2 Days</td>
                    <td><span className="badge bdg-high">D (High Risk)</span></td>
                  </tr>
                  <tr>
                    <td>Supplier Ground Carrier</td>
                    <td>88.2%</td>
                    <td>2.1 Days</td>
                    <td><span className="badge bdg-med">B (Med Risk)</span></td>
                  </tr>
                  <tr>
                    <td>Supplier Fast Delivery</td>
                    <td>94.5%</td>
                    <td>0.8 Days</td>
                    <td><span className="badge bdg-low">A (Low Risk)</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )

      case 'warehouse':
        return (
          <div className={styles.reportArea}>
            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>Warehouse Capacity & Stock Metrics</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Avg Storage Space</span>
                  <span className={styles.kpiVal}>81.4%</span>
                  <span className={styles.kpiSub}>Total capacity used</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Bottleneck Index</span>
                  <span className={styles.kpiVal} style={{ color: 'var(--rm)' }}>0.54</span>
                  <span className={styles.kpiSub}>Stockout probability ratio</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Total Warehouses</span>
                  <span className={styles.kpiVal}>5 Locations</span>
                  <span className={styles.kpiSub}>Registered hubs</span>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <div className={styles.cardHeader}>
                <h4 className={styles.cardTitle}>Warehouse Space Allocation</h4>
                <button className={styles.dlBtn} onClick={() => downloadChart('whSpace', 'wh_space.svg')}>
                  <Download size={10} />
                  SVG
                </button>
              </div>
              <div id="whSpace" style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { name: 'Zone 1', usage: 88, threshold: 85 },
                    { name: 'Zone 2', usage: 72, threshold: 85 },
                    { name: 'Zone 3', usage: 94, threshold: 85 },
                    { name: 'Zone 4', usage: 65, threshold: 85 },
                    { name: 'Zone 5', usage: 82, threshold: 85 }
                  ]} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 9 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <Bar dataKey="usage" name="Space Used %" fill="var(--blue)" radius={[3, 3, 0, 0]} />
                    <Line type="monotone" dataKey="threshold" name="Alert Threshold" stroke="var(--rh)" strokeDasharray="4 4" strokeWidth={1.5} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )

      case 'entity':
        return (
          <div className={styles.reportArea}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14 }}>
              <span style={{ fontSize: 11, color: 'var(--tm)' }}>Inspect Entity Instance:</span>
              <select
                className={styles.entitySelect}
                value={selectedEntityId}
                onChange={e => setSelectedEntityId(e.target.value)}
              >
                {entityInstances.map(id => <option key={id} value={id}>{id}</option>)}
              </select>
            </div>

            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>{activeEntityData.id} Deep Dive</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Exposure Loss</span>
                  <span className={styles.kpiVal}>${activeEntityData.exposure.toLocaleString()}</span>
                  <span className={styles.kpiSub}>Financial risk</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Risk Score</span>
                  <span className={styles.kpiVal} style={{ color: activeEntityData.riskScore >= 70 ? 'var(--rh)' : 'var(--rm)' }}>
                    {activeEntityData.riskScore}%
                  </span>
                  <span className={styles.kpiSub}>Disruption probability</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Model Accuracy</span>
                  <span className={styles.kpiVal} style={{ color: 'var(--rl)' }}>{activeEntityData.accuracy}%</span>
                  <span className={styles.kpiSub}>Confidence ratio score</span>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <h4 className={styles.cardTitle}>Entity Connections Breakdown</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { target: 'Supplier Air Transport', type: 'SUPPLIES', weight: 0.92 },
                  { target: 'Warehouse Zone 1', type: 'STORED_IN', weight: 0.78 },
                  { target: 'Carrier Ground Transport', type: 'SHIPS_TO', weight: 0.84 }
                ].map((conn, idx) => (
                  <div key={idx} style={{
                    display: 'flex', justifyContent: 'space-between', padding: '8px 12px',
                    background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 6, fontSize: 11
                  }}>
                    <div>
                      <span style={{ fontWeight: 600, color: 'var(--tp)' }}>{conn.target}</span>
                      <span className="badge" style={{ marginLeft: 8, background: 'rgba(9, 132, 227, 0.08)', color: 'var(--blue)' }}>
                        {conn.type}
                      </span>
                    </div>
                    <span style={{ color: 'var(--ts)', fontVariantNumeric: 'tabular-nums' }}>Weight: {conn.weight.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      case 'incident':
        return (
          <div className={styles.reportArea}>
            <div className={styles.reportSection}>
              <h3 className={styles.secTitle}>Operational Disruption Incidents</h3>
              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Critical Breaches</span>
                  <span className={styles.kpiVal} style={{ color: 'var(--rh)' }}>2 Incidents</span>
                  <span className={styles.kpiSub}>Urgent actions required</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Mean Time To Resolution</span>
                  <span className={styles.kpiVal}>4.2 Hours</span>
                  <span className={styles.kpiSub}>RCA generation speed</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>System Status</span>
                  <span className={styles.kpiVal} style={{ color: 'var(--rl)' }}>Healthy</span>
                  <span className={styles.kpiSub}>No active outages</span>
                </div>
              </div>
            </div>

            <div className={styles.reportCard}>
              <h4 className={styles.cardTitle}>Active Incident Queue</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { name: 'Supplier Delivery Delay Alert', severity: 'Critical', region: 'Western Europe', date: '2026-07-12' },
                  { name: 'Warehouse Holding Over capacity Space', severity: 'Medium', region: 'North America', date: '2026-07-14' },
                  { name: 'Carrier Ground Transport Transit Lag', severity: 'High', region: 'Latin America', date: '2026-07-15' }
                ].map((item, idx) => (
                  <div key={idx} style={{
                    display: 'flex', justifyContent: 'space-between', padding: '10px 14px',
                    background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 6, fontSize: 11
                  }}>
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--tp)' }}>{item.name}</div>
                      <div style={{ fontSize: 9, color: 'var(--tm)', marginTop: 2 }}>{item.region} · {item.date}</div>
                    </div>
                    <span className={`badge ${item.severity === 'Critical' || item.severity === 'High' ? 'bdg-high' : 'bdg-med'}`}>
                      {item.severity}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="page active" style={{ height: 'calc(100vh - 44px)', overflow: 'hidden', display: 'flex', flexDirection: 'row' }}>
      
      {/* Sidebar - Report Selectors */}
      <div className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <FileText size={16} style={{ color: 'var(--blue)' }} />
          <span className={styles.sidebarTitle}>Executive Reports</span>
        </div>
        <div className={styles.reportsList}>
          {reportsList.map(r => {
            const Icon = r.icon
            const isActive = activeReport === r.id
            return (
              <div
                key={r.id}
                onClick={() => setActiveReport(r.id)}
                className={`${styles.reportItem} ${isActive ? styles.reportItemActive : ''}`}
              >
                <div className={styles.itemIconWrap} style={{ color: isActive ? 'var(--blue)' : 'var(--ts)' }}>
                  <Icon size={14} />
                </div>
                <div>
                  <div className={styles.itemName} style={{ color: isActive ? 'var(--blue)' : 'var(--tp)' }}>{r.name}</div>
                  <div className={styles.itemDesc}>{r.desc}</div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Global Export Panel */}
        <div className={styles.exportPanel}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--tm)', textTransform: 'uppercase', marginBottom: 8 }}>Export actions</div>
          <button className={styles.expBtn} onClick={handlePrint}>
            <Printer size={12} />
            Print Report (PDF)
          </button>
          <button className={styles.expBtn} onClick={exportExcel}>
            <Download size={12} />
            Export Data (Excel CSV)
          </button>
        </div>
      </div>

      {/* Main Report Document Canvas */}
      <div ref={reportRef} className={styles.canvas}>
        <div className={styles.canvasHeader}>
          <div>
            <h2 className={styles.canvasTitle}>
              {reportsList.find(x => x.id === activeReport)?.name}
            </h2>
            <div className={styles.canvasMeta}>
              Enterprise AMASCI Platform Audit Report · {new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-secondary btn-sm" onClick={handlePrint}>
              <Printer size={11} />
              Print
            </button>
            <button className="btn btn-primary btn-sm" onClick={exportExcel}>
              <Download size={11} />
              Export
            </button>
          </div>
        </div>

        <div className={styles.reportScrollable}>
          {renderReportContent()}
        </div>
      </div>
    </div>
  )
}
