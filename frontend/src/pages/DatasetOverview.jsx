import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from 'recharts'
import { api } from '../api/client'
import KpiCard from '../components/ui/KpiCard'
import DataTable from '../components/ui/DataTable'
import Spinner from '../components/ui/Spinner'
import InfoBox from '../components/ui/InfoBox'
import UploadZone from '../components/ui/UploadZone'
import { useToast } from '../components/ui/Toast'
import { CheckCircle } from 'lucide-react'

const FEATURE_GROUPS = [
  {
    title: 'Demand Features',
    fields: [
      { label: 'Monthly Demand', description: 'Sales history aggregated by calendar period.', agent: 'Demand Agent' },
      { label: 'Demand Trend', description: 'Change direction over recent weeks.', agent: 'Demand Agent' },
      { label: 'Rolling Mean', description: 'Smoothed demand level for stability.', agent: 'Demand Agent' },
      { label: 'Seasonality', description: 'Weekly and monthly seasonal patterns.', agent: 'Demand Agent' },
    ],
  },
  {
    title: 'Inventory Features',
    fields: [
      { label: 'Inventory Risk', description: 'Probability of stock imbalance by warehouse.', agent: 'Inventory Agent' },
      { label: 'Stock Movement', description: 'Inbound/outbound inventory velocity.', agent: 'Inventory Agent' },
      { label: 'Warehouse Utilization', description: 'Capacity utilization versus demand.', agent: 'Inventory Agent' },
    ],
  },
  {
    title: 'Supplier Features',
    fields: [
      { label: 'Supplier Reliability', description: 'On-time delivery history for suppliers.', agent: 'Supplier Agent' },
      { label: 'Supplier Delay Rate', description: 'Late shipment frequency by partner.', agent: 'Supplier Agent' },
      { label: 'Supplier Performance', description: 'Profit, cost and delivery quality.', agent: 'Supplier Agent' },
    ],
  },
  {
    title: 'Logistics Features',
    fields: [
      { label: 'Delay Ratio', description: 'Late delivery ratio by route.', agent: 'Logistics Agent' },
      { label: 'Shipping Efficiency', description: 'Transport performance versus plan.', agent: 'Logistics Agent' },
      { label: 'Route Performance', description: 'Carrier and corridor reliability.', agent: 'Logistics Agent' },
    ],
  },
  {
    title: 'Financial Features',
    fields: [
      { label: 'Profit Margin', description: 'Revenue minus cost per order.', agent: 'Demand Agent' },
      { label: 'Revenue Trend', description: 'Time series of sales revenue.', agent: 'Demand Agent' },
      { label: 'Order Value', description: 'Order monetary value distribution.', agent: 'Demand Agent' },
    ],
  },
]

const AGENT_FLOWS = [
  {
    key: 'demand',
    name: 'Demand Agent',
    inputs: ['Product', 'Category', 'Sales', 'Quantity', 'Date', 'Region'],
    target: 'Future Demand',
  },
  {
    key: 'inventory',
    name: 'Inventory Agent',
    inputs: ['Warehouse', 'Inventory', 'Sales', 'Quantity'],
    target: 'Stock Risk',
  },
  {
    key: 'supplier',
    name: 'Supplier Agent',
    inputs: ['Supplier', 'Delay', 'Profit', 'Shipping Mode'],
    target: 'Supplier Risk',
  },
  {
    key: 'logistics',
    name: 'Logistics Agent',
    inputs: ['Warehouse', 'Region', 'Shipping Mode', 'Delivery Status'],
    target: 'Delivery Delay',
  },
]

const PREVIEW_TABS = [
  { id: 'training', label: 'Training' },
  { id: 'testing', label: 'Testing' },
  { id: 'forecast', label: 'Forecast' },
]

const STATUS_COLOR = {
  completed: 'var(--inv)',
  active: 'var(--blue)',
  pending: 'var(--tm)',
}

export default function DatasetOverview() {
  const [activePreviewTab, setActivePreviewTab] = useState('training')
  const [columnFilter, setColumnFilter] = useState('')
  const [trainFile, setTrainFile] = useState(null)
  const [forecastFile, setForecastFile] = useState(null)
  const [actualFile, setActualFile] = useState(null)
  const queryClient = useQueryClient()
  const toast = useToast()

  const summaryQuery = useQuery({ queryKey: ['datasetSummary'], queryFn: () => api.getDatasetSummary().then(r => r.data) })
  const analyticsQuery = useQuery({ queryKey: ['datasetAnalytics'], queryFn: () => api.getDatasetAnalytics().then(r => r.data) })
  const historyQuery = useQuery({ queryKey: ['datasetHistory'], queryFn: () => api.getDatasetHistory().then(r => r.data.data) })
  const forecastPeriodQuery = useQuery({ queryKey: ['nextForecastPeriod'], queryFn: () => api.getNextForecastPeriod().then(r => r.data) })
  const graphStatsQuery = useQuery({ queryKey: ['graphStats'], queryFn: () => api.getGraphStats().then(r => r.data), retry: false })

  const uploadTraining = useMutation({
    mutationFn: (file) => api.uploadTrain(file).then(r => r.data),
    onSuccess: () => {
      toast.success('Historical dataset uploaded successfully.')
      setTrainFile(null)
      queryClient.invalidateQueries(['datasetHistory'])
    },
    onError: (err) => toast.error(err.message || 'Training dataset upload failed'),
  })

  const uploadForecast = useMutation({
    mutationFn: (file) => api.uploadForecast(file).then(r => r.data),
    onSuccess: () => {
      toast.success('Forecast dataset uploaded successfully.')
      setForecastFile(null)
      queryClient.invalidateQueries(['datasetHistory'])
    },
    onError: (err) => toast.error(err.message || 'Forecast dataset upload failed'),
  })

  const uploadActual = useMutation({
    mutationFn: (file) => api.uploadActual(file).then(r => r.data),
    onSuccess: () => {
      toast.success('Actual dataset uploaded successfully.')
      setActualFile(null)
      queryClient.invalidateQueries(['datasetHistory'])
    },
    onError: (err) => toast.error(err.message || 'Actual dataset upload failed'),
  })

  const isLoading = summaryQuery.isLoading || analyticsQuery.isLoading || historyQuery.isLoading || forecastPeriodQuery.isLoading
  const hasError = summaryQuery.isError || analyticsQuery.isError || historyQuery.isError || forecastPeriodQuery.isError

  if (isLoading) {
    return <Spinner large text="Loading dataset management metadata from backend APIs..." />
  }

  if (hasError) {
    const errorMessage = summaryQuery.error?.message || analyticsQuery.error?.message || historyQuery.error?.message || forecastPeriodQuery.error?.message
    return <InfoBox type="error">{errorMessage || 'Unable to load dataset management data.'}</InfoBox>
  }

  const summary = summaryQuery.data || {}
  const analytics = analyticsQuery.data || {}
  const history = historyQuery.data || { datasets: [] }
  const forecastPeriod = forecastPeriodQuery.data || {}
  const graphStats = graphStatsQuery.data || {}

  const datasetHistory = Array.isArray(history.datasets) ? history.datasets : []
  const latestDataset = [...datasetHistory].sort((a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime())[0]
  const dataSource = latestDataset?.filename ? latestDataset.filename : 'DataCo Smart Supply Chain Dataset'
  const datasetVersion = latestDataset?.version ? `v${latestDataset.version}` : 'v1.0'
  const trainingWindow = analytics.walk_forward_split ? `${analytics.walk_forward_split.train_start} → ${analytics.walk_forward_split.train_end}` : `${summary.date_range_start} → ${summary.training_data_end_date || summary.date_range_end}`
  const testingWindow = analytics.walk_forward_split ? `${analytics.walk_forward_split.test_start} → ${analytics.walk_forward_split.test_end}` : 'Not available'
  const forecastWindow = forecastPeriod.period_start && forecastPeriod.period_end ? `${forecastPeriod.period_start} → ${forecastPeriod.period_end}` : 'Pending'
  const agentCount = analytics.training_metrics ? Object.keys(analytics.training_metrics).length : 4
  const datasetHealthLabel = summary.ready ? 'Ready for modeling' : 'Pending processing'
  const pipelineStatus = summary.ready ? 'completed' : 'pending'

  const previewHistoryColumns = [
    { key: 'filename', label: 'File', sortable: true },
    { key: 'dataset_type', label: 'Type', sortable: true },
    { key: 'row_count', label: 'Rows', sortable: true, render: (value) => value?.toLocaleString() },
    { key: 'version', label: 'Version', sortable: true },
    { key: 'quality_score', label: 'Quality', sortable: true },
    { key: 'status', label: 'Status', sortable: true },
    { key: 'uploaded_at', label: 'Uploaded At', sortable: true },
  ]

  const filteredHistory = datasetHistory.filter(row => {
    if (!columnFilter) return true
    const normalized = columnFilter.toLowerCase()
    return [row.filename, row.dataset_type, row.status, row.dataset_id].some(value => String(value || '').toLowerCase().includes(normalized))
  })

  const tabHistory = useMemo(() => {
    if (activePreviewTab === 'forecast') {
      return filteredHistory.filter(row => String(row.filename || '').toLowerCase().includes('forecast'))
    }
    if (activePreviewTab === 'testing') {
      return filteredHistory.filter(row => String(row.dataset_type || '').toLowerCase() === 'actuals')
    }
    return filteredHistory.filter(row => [String(row.dataset_type || '').toLowerCase(), String(row.filename || '').toLowerCase()].some(value => value.includes('historical') || value.includes('train')))
  }, [activePreviewTab, filteredHistory])

  const missingChartData = [
    { name: 'Present', value: Math.max(0, 100 - (summary.total_null_percent || 0)), color: '#0984e3' },
    { name: 'Missing', value: summary.total_null_percent || 0, color: 'rgba(214,48,49,0.85)' },
  ]

  const regionData = analytics.region_breakdown?.map(item => ({ name: item['Order Region'] || item.region || item.name || 'Unknown', value: item.order_count || item.count || 0 })) || []
  const monthlyOrders = analytics.monthly_trend?.map(item => ({ period: item.period, orders: item.orders || item.total_sales || 0 })) || []

  return (
    <div className="page active">
      <div className="page-head">
        <div>
          <div className="page-title">Dataset Management</div>
          <div className="page-sub">Historical supply chain dataset used for training, testing, feature engineering, and intelligent forecasting.</div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
          <span className="badge bdg-blue">Version: {datasetVersion}</span>
          <span className="badge bdg-purple">Last updated: {latestDataset?.uploaded_at || summary.date_range_end || 'Unknown'}</span>
          <span className="badge bdg-low">Training: {trainingWindow}</span>
          <span className="badge bdg-orange">Forecast: {forecastWindow}</span>
        </div>
      </div>

      <div className="g4">
        <KpiCard label="Historical Records" value={summary.total_orders?.toLocaleString() || '—'} foot={`${summary.date_range_start} → ${summary.date_range_end}`} color="var(--blue)" />
        <KpiCard label="Training Records" value={analytics.walk_forward_split?.train_rows?.toLocaleString() || '—'} foot={trainingWindow} color="var(--dem)" />
        <KpiCard label="Testing Records" value={analytics.walk_forward_split?.test_rows?.toLocaleString() || '—'} foot={testingWindow} color="var(--log)" />
        <KpiCard label="Feature Columns" value={summary.column_count || '—'} foot={`${summary.numeric_columns || 0} numeric · ${summary.categorical_columns || 0} categorical`} color="var(--inv)" />
      </div>

      <div className="g4">
        <KpiCard label="Target Variables" value={Object.keys(analytics.training_metrics || {}).length || 4} foot="Demand, Inventory, Supplier, Logistics" color="var(--tpke)" />
        <KpiCard label="Missing Values" value={`${summary.total_null_percent?.toFixed(1) || 0}%`} foot={`${summary.total_null_cells?.toLocaleString() || 0} missing cells`} color="var(--rh)" />
        <KpiCard label="Duplicate Records" value={summary.duplicate_rows?.toLocaleString() || '—'} foot="Data integrity review" color="var(--rm)" />
        <KpiCard label="Dataset Size" value={`${summary.memory_mb?.toFixed(1) || 0} MB`} foot={latestDataset?.filename?.split('.').pop()?.toUpperCase() || 'Parquet'} color="var(--blue)" />
      </div>

      <div className="g21">
        <div>
          <div className="card">
            <div className="card-head"><span className="card-title">Data Preprocessing Pipeline</span></div>
            <div className="card-body" style={{ display: 'grid', gap: 14 }}>
              <div className="process-grid">
                {[
                  { title: 'Raw Dataset', description: 'Source supply chain records from DataCo.', value: `${summary.total_orders?.toLocaleString() || '—'} rows` },
                  { title: 'Missing Value Handling', description: 'Identify and impute or remove nulls for stable modeling.', value: `${summary.total_null_percent?.toFixed(1) || 0}% missing` },
                  { title: 'Duplicate Removal', description: 'Detect duplicate order and shipment rows for clean training data.', value: `${summary.duplicate_rows?.toLocaleString() || 0} removed` },
                  { title: 'Categorical Encoding', description: 'Transform labels like region, category and mode into model-ready vectors.', value: `${summary.categorical_columns || 0} fields` },
                  { title: 'Date Processing', description: 'Normalize order and shipment dates for seasonality and trend features.', value: `${summary.datetime_columns || 0} date fields` },
                  { title: 'Feature Scaling', description: 'Standardize numerical features for stable agent behavior.', value: `${summary.numeric_columns || 0} numeric fields` },
                  { title: 'Processed Dataset', description: 'Final AI-ready table used by all agents and forecast engines.', value: `${summary.column_count || 0} columns` },
                ].map(step => (
                  <div key={step.title} className="process-step">
                    <div className="step-title">{step.title}</div>
                    <div className="step-meta">{step.description}</div>
                    <div className="step-foot">{step.value}</div>
                    <div className="step-status" style={{ color: STATUS_COLOR[pipelineStatus], borderColor: STATUS_COLOR[pipelineStatus] }}>{pipelineStatus === 'completed' ? 'Completed' : 'Pending'}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><span className="card-title">Feature Engineering Reference</span></div>
            <div className="card-body" style={{ display: 'grid', gap: 18 }}>
              {FEATURE_GROUPS.map(group => (
                <div key={group.title} className="feature-card">
                  <div className="section-lbl">{group.title}</div>
                  <div className="feature-list">
                    {group.fields.map(field => (
                      <div key={field.label} className="feature-row">
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--tp)' }}>{field.label}</div>
                          <div style={{ color: 'var(--tm)', fontSize: 12 }}>{field.description}</div>
                        </div>
                        <div style={{ color: 'var(--blue)', fontSize: 12, fontWeight: 600 }}>{field.agent}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="side-panel">
          <div className="section-lbl">How one dataset becomes multiple agent datasets</div>
          <div style={{ display: 'grid', gap: 14 }}>
            {AGENT_FLOWS.map(agent => {
              const metrics = analytics.training_metrics?.[agent.key]
              const modelLabel = metrics?.task === 'regression' ? 'LightGBM Regressor' : metrics?.task === 'classification' ? 'LightGBM Classifier' : 'LightGBM'
              return (
                <div key={agent.key} className="agent-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--tp)' }}>{agent.name}</div>
                      <div style={{ color: 'var(--tm)', fontSize: 12 }}>{agent.target}</div>
                    </div>
                    <span className="badge bdg-blue">{modelLabel}</span>
                  </div>
                  <div style={{ display: 'grid', gap: 6 }}>
                    <div style={{ fontSize: 12, color: 'var(--tm)' }}>Input Features</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{agent.inputs.map(input => <span key={input} className="badge bdg-low">{input}</span>)}</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                      <div>
                        <div className="agent-metric-lbl">Feature count</div>
                        <div className="agent-metric-val">{agent.inputs.length}</div>
                      </div>
                      <div>
                        <div className="agent-metric-lbl">Training rows</div>
                        <div className="agent-metric-val">{metrics?.n_training_samples?.toLocaleString() ?? 'Backend'}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="g21">
        <div>
          <div className="card">
            <div className="card-head"><span className="card-title">Training Dataset Preview</span></div>
            <div className="card-body" style={{ display: 'grid', gap: 14 }}>
              <div className="tab-group">
                {PREVIEW_TABS.map(tab => (
                  <button key={tab.id} className={`tab-button${activePreviewTab === tab.id ? ' active' : ''}`} onClick={() => setActivePreviewTab(tab.id)}>{tab.label}</button>
                ))}
              </div>
              <div className="preview-toolbar">
                <div style={{ color: 'var(--tm)', fontSize: 12 }}>
                  {activePreviewTab === 'training' && 'Historical training datasets uploaded to backend and curated for agent training.'}
                  {activePreviewTab === 'testing' && 'Testing and validation data captures holdout periods for model evaluation.'}
                  {activePreviewTab === 'forecast' && 'Forecast dataset versions are used to generate next-period predictions.'}
                </div>
                <input type="text" className="filter-input" placeholder="Search uploads or dataset IDs" value={columnFilter} onChange={(e) => setColumnFilter(e.target.value)} />
              </div>
              <DataTable columns={previewHistoryColumns} data={tabHistory} emptyMessage="No dataset uploads found for this category." loading={historyQuery.isLoading} />
            </div>
          </div>

          <div className="card">
            <div className="card-head"><span className="card-title">Data Quality Analysis</span></div>
            <div className="card-body" style={{ display: 'grid', gap: 18 }}>
              <div className="g2">
                <div className="card" style={{ border: '1px solid var(--b)' }}>
                  <div className="card-head"><span className="card-title">Missing Values</span></div>
                  <div className="card-body" style={{ minHeight: 220 }}>
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie data={missingChartData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={84} paddingAngle={4}>
                          {missingChartData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                        </Pie>
                        <Legend verticalAlign="bottom" height={24} iconType="circle" wrapperStyle={{ fontSize: 12, color: 'var(--tm)' }} />
                        <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="card" style={{ border: '1px solid var(--b)' }}>
                  <div className="card-head"><span className="card-title">Regional Distribution</span></div>
                  <div className="card-body" style={{ minHeight: 220 }}>
                    {regionData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={regionData.slice(0, 8)} margin={{ left: 0, right: 0, top: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={40} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Bar dataKey="value" fill="var(--blue)" />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div style={{ color: 'var(--tm)', padding: '20px', textAlign: 'center' }}>No regional distribution data available.</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="g2">
                <div className="card" style={{ border: '1px solid var(--b)' }}>
                  <div className="card-head"><span className="card-title">Monthly Records</span></div>
                  <div className="card-body" style={{ minHeight: 220 }}>
                    {monthlyOrders.length > 0 ? (
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={monthlyOrders} margin={{ left: 0, right: 10, top: 10, bottom: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Line type="monotone" dataKey="orders" stroke="var(--tpke)" strokeWidth={2} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div style={{ color: 'var(--tm)', padding: '20px', textAlign: 'center' }}>Monthly record trend is not available.</div>
                    )}
                  </div>
                </div>
                <div className="card" style={{ border: '1px solid var(--b)' }}>
                  <div className="card-head"><span className="card-title">Order Value Distribution</span></div>
                  <div className="card-body" style={{ minHeight: 220 }}>
                    {analytics.order_value_distribution?.length > 0 ? (
                      <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                          <Pie data={analytics.order_value_distribution} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label />
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div style={{ color: 'var(--tm)', padding: '20px', textAlign: 'center' }}>Order distribution data is not available.</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="g21">
        <div className="card">
          <div className="card-head"><span className="card-title">Data Flow to AI</span></div>
          <div className="card-body" style={{ display: 'grid', gap: 14 }}>
            <div className="flow-row">
              {[
                'Historical Dataset',
                'Data Cleaning',
                'Feature Engineering',
                'Feature Selection',
                'Demand Dataset',
                'Inventory Dataset',
                'Supplier Dataset',
                'Logistics Dataset',
                'Model Training',
                'Predictions',
              ].map((step, index) => (
                <div key={step} className={`flow-step${index === 5 ? ' active' : ''}`}>
                  <div>{step}</div>
                </div>
              ))}
            </div>
            <div style={{ color: 'var(--tm)', fontSize: 12 }}>
              The AI pipeline is orchestrated by the backend. The frontend visualizes the path from DataCo raw records through cleaning, feature construction, dataset selection and agent-specific training targets, all the way to backend-generated predictions.
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Upload Management</span></div>
          <div className="card-body" style={{ display: 'grid', gap: 18 }}>
            <div className="g3">
              <div className="card" style={{ border: '1px solid var(--b)' }}>
                <div className="card-head"><span className="card-title">Historical Dataset</span></div>
                <div className="card-body" style={{ display: 'grid', gap: 12 }}>
                  <UploadZone accept=".csv" hint="Upload training CSV" onFile={setTrainFile} hasFile={!!trainFile} fileName={trainFile?.name} onClear={() => setTrainFile(null)} disabled={uploadTraining.isLoading} />
                  <button className="btn btn-primary btn-full" disabled={!trainFile || uploadTraining.isLoading} onClick={() => uploadTraining.mutate(trainFile)}>
                    {uploadTraining.isLoading ? 'Uploading...' : 'Upload Historical Dataset'}
                  </button>
                </div>
              </div>
              <div className="card" style={{ border: '1px solid var(--b)' }}>
                <div className="card-head"><span className="card-title">Forecast Dataset</span></div>
                <div className="card-body" style={{ display: 'grid', gap: 12 }}>
                  <UploadZone accept=".csv" hint="Upload forecast CSV" onFile={setForecastFile} hasFile={!!forecastFile} fileName={forecastFile?.name} onClear={() => setForecastFile(null)} disabled={uploadForecast.isLoading} />
                  <button className="btn btn-primary btn-full" disabled={!forecastFile || uploadForecast.isLoading} onClick={() => uploadForecast.mutate(forecastFile)}>
                    {uploadForecast.isLoading ? 'Uploading...' : 'Upload Forecast Dataset'}
                  </button>
                </div>
              </div>
              <div className="card" style={{ border: '1px solid var(--b)' }}>
                <div className="card-head"><span className="card-title">Actual Dataset</span></div>
                <div className="card-body" style={{ display: 'grid', gap: 12 }}>
                  <UploadZone accept=".csv" hint="Upload actuals CSV" onFile={setActualFile} hasFile={!!actualFile} fileName={actualFile?.name} onClear={() => setActualFile(null)} disabled={uploadActual.isLoading} />
                  <button className="btn btn-primary btn-full" disabled={!actualFile || uploadActual.isLoading} onClick={() => uploadActual.mutate(actualFile)}>
                    {uploadActual.isLoading ? 'Uploading...' : 'Upload Actual Dataset'}
                  </button>
                </div>
              </div>
            </div>
            <div>
              <div className="section-lbl">Upload history</div>
              <DataTable columns={previewHistoryColumns} data={datasetHistory} emptyMessage="No upload history is available from backend." loading={historyQuery.isLoading} />
            </div>
          </div>
        </div>
      </div>

      <div className="g2">
        <div className="side-panel">
          <div className="section-lbl">Dataset Information</div>
          <div className="panel-row"><span>Current Dataset</span><strong>{dataSource}</strong></div>
          <div className="panel-row"><span>Dataset Version</span><strong>{datasetVersion}</strong></div>
          <div className="panel-row"><span>Training Window</span><strong>{trainingWindow}</strong></div>
          <div className="panel-row"><span>Testing Window</span><strong>{testingWindow}</strong></div>
          <div className="panel-row"><span>Feature Count</span><strong>{summary.column_count || '—'}</strong></div>
          <div className="panel-row"><span>Agent Count</span><strong>{agentCount}</strong></div>
          <div className="panel-row"><span>Knowledge Graph</span><strong>{graphStats.graph_health || 'Unknown'}</strong></div>
          <div className="panel-row"><span>Latest Forecast</span><strong>{forecastPeriod.recommendation || forecastWindow}</strong></div>
        </div>
        <div className="side-panel">
          <div className="section-lbl">Transformation Summary</div>
          {[
            'Raw Dataset',
            'Processed Dataset',
            'Engineered Features',
            'Agent-specific Features',
            'Machine Learning',
            'Knowledge Graph',
            'GraphRAG',
          ].map(step => (
            <div key={step} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '10px 0', borderBottom: '1px solid rgba(15, 23, 42, 0.06)' }}>
              <span style={{ color: 'var(--tm)', fontSize: 12 }}>{step}</span>
              <CheckCircle size={14} color="var(--inv)" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
