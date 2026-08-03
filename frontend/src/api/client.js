import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const http = axios.create({
  baseURL: BASE,
  timeout: 300_000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.response.use(
  r => r,
  err => {
    const detail = err.response?.data?.detail
    let message = err.message || 'Request failed'
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail)) message = detail.map(d => d.msg || JSON.stringify(d)).join('; ')
    else if (detail && typeof detail === 'object') message = detail.msg || JSON.stringify(detail)
    return Promise.reject({ message, status: err.response?.status })
  }
)

const multipart = (url, fd) => axios.post(`${BASE}${url}`, fd, {
  headers: { 'Content-Type': 'multipart/form-data' },
  timeout: 300_000,
})

export const api = {
  // System
  health:             () => http.get('/api/v1/health'),
  live:               () => http.get('/api/v1/live'),
  ready:              () => http.get('/api/v1/ready'),

  // Dataset Analytics (real DataCo values, no DB needed)
  getDatasetSummary:    () => http.get('/api/v1/dataset/summary'),
  getDatasetAnalytics:  () => http.get('/api/v1/dataset/analytics'),
  getNextForecastPeriod:() => http.get('/api/v1/dataset/next-forecast-period'),
  getAutoForecast:      () => http.get('/api/v1/dataset/auto-forecast'),
  getErrorDiagnostics:  (period) => http.get('/api/v1/dataset/error-diagnostics', { params: { period_start: period } }),

  // Dashboard
  getDashboard:       () => http.get('/api/v1/dashboard'),
  getKpis:            () => http.get('/api/v1/dashboard/kpis'),
  getForecastDash:    () => http.get('/api/v1/dashboard/forecast'),
  getRiskDash:        () => http.get('/api/v1/dashboard/risk'),
  getGraphDash:       () => http.get('/api/v1/dashboard/graph'),
  getTpkeDash:        () => http.get('/api/v1/dashboard/tpke'),
  getRootcauseDash:   () => http.get('/api/v1/dashboard/rootcause'),
  getTrends:          () => http.get('/api/v1/dashboard/trends'),
  getComparison:      (b) => http.post('/api/v1/dashboard/comparison', b || { comparison_type: 'period' }),
  getExecSummary:     () => http.get('/api/v1/dashboard/executive-summary'),
  exportDashboard:    () => http.get('/api/v1/dashboard/export'),

  // Data / Upload
  uploadTrain:        (f, desc='') => { const fd = new FormData(); fd.append('file', f); fd.append('description', desc); return multipart('/api/v1/data/upload/train', fd) },
  uploadForecast:     (f, desc='') => { const fd = new FormData(); fd.append('file', f); fd.append('description', desc); return multipart('/api/v1/data/upload/forecast', fd) },
  uploadActual:       (f, desc='') => { const fd = new FormData(); fd.append('file', f); fd.append('description', desc); return multipart('/api/v1/data/upload/actual', fd) },
  getDatasetHistory:  () => http.get('/api/v1/data/dataset/history'),
  getDataset:         (id) => http.get(`/api/v1/data/dataset/${id}`),
  getDatasetProfile:  (id) => http.get(`/api/v1/data/dataset/${id}/profile`),
  processDataset:     (id) => http.post(`/api/v1/data/process/${id}`),

  // ML
  train:              (b) => http.post('/api/v1/ml/train', b),
  trainAll:           () => http.post('/api/v1/ml/train/all'),
  trainUpload:        (f) => { const fd = new FormData(); fd.append('file', f); return multipart('/api/v1/ml/train/upload', fd) },
  predict:            (b) => http.post('/api/v1/ml/predict', b),
  predictDataset:     (b) => http.post('/api/v1/ml/predict/dataset', b),
  forecast:           (b) => http.post('/api/v1/ml/forecast', b),
  getModels:          () => http.get('/api/v1/ml/models'),
  getLatestModels:    () => http.get('/api/v1/ml/models/latest'),
  getTrainingHistory: () => http.get('/api/v1/ml/training-history'),
  getMetrics:         (type) => http.get(`/api/v1/ml/metrics/${type}`),
  getFeatureImportance: (type) => http.get(`/api/v1/ml/feature-importance/${type}`),
  evaluateModel:      (b) => http.post('/api/v1/ml/model/evaluate', b),

  // Knowledge Graph
  buildGraph:         () => http.post('/api/v1/graph/build'),
  rebuildGraph:       () => http.post('/api/v1/graph/rebuild'),
  getGraphStats:      () => http.get('/api/v1/graph/statistics'),
  getGraphNodes:      (p) => http.get('/api/v1/graph/nodes', { params: p }),
  getGraphEntity:     (id) => http.get(`/api/v1/graph/entity/${id}`),
  getSubgraph:        (p) => http.get('/api/v1/graph/subgraph', { params: p }),
  getRelationships:   () => http.get('/api/v1/graph/relationships'),
  getShortestPath:    (p) => http.get('/api/v1/graph/shortest-path', { params: p }),
  getCentrality:      (label) => http.get(`/api/v1/graph/centrality/${label}`),
  getGraphSchema:     () => http.get('/api/v1/graph/schema/info'),
  initGraphSchema:    () => http.post('/api/v1/graph/schema/initialize'),
  updateGraph:        (b) => http.post('/api/v1/graph/update', b),
  validateGraph:      () => http.get('/api/v1/graph/validate'),
  exportGraph:        () => http.post('/api/v1/graph/export'),
  importGraph:        (b) => http.post('/api/v1/graph/import', b),
  getGraphVersions:   () => http.get('/api/v1/graph/versions'),
  getActiveVersion:   () => http.get('/api/v1/graph/versions/active'),
  rollbackVersion:    (b) => http.post('/api/v1/graph/versions/rollback', b),

  // GraphRAG
  queryGraphRAG:      (b) => http.post('/api/v1/graphrag/query', b),
  getGraphRAGHistory: () => http.get('/api/v1/graphrag/history'),
  getGraphRAGStats:   () => http.get('/api/v1/graphrag/statistics'),
  getGraphRAGContext: (b) => http.post('/api/v1/graphrag/context', b),
  getGraphRAGSubgraph:(b) => http.post('/api/v1/graphrag/subgraph', b),
  getRootCauseRAG:    (b) => http.post('/api/v1/graphrag/root-cause', b),
  getDependencies:    (b) => http.post('/api/v1/graphrag/dependencies', b),
  getGraphRAGCache:   () => http.get('/api/v1/graphrag/cache'),
  clearGraphRAGCache: () => http.delete('/api/v1/graphrag/cache'),

  // RCA
  analyzeRCA:         (b) => http.post('/api/v1/rca/analyze', b),
  getRCAHistory:      () => http.get('/api/v1/rca/history'),
  getRCALatest:       () => http.get('/api/v1/rca/latest'),
  getRCAPath:         (b) => http.post('/api/v1/rca/path', b),
  getRCAStats:        () => http.get('/api/v1/rca/statistics'),
  getRCASubgraph:     (b) => http.post('/api/v1/rca/subgraph', b),
  getRCAReport:       (id) => http.get(`/api/v1/rca/report/${id}`),

  // TPKE
  getTpkeStatus:      () => http.get('/api/v1/tpke/status'),
  getTpkeEdges:       () => http.get('/api/v1/tpke/edges'),
  getTpkeSummary:     () => http.get('/api/v1/tpke/summary'),
  getTpkeHistory:     () => http.get('/api/v1/tpke/history'),
  evolveTpke:         (b) => http.post('/api/v1/tpke/evolve', b),
  decayTpke:          (b) => http.post('/api/v1/tpke/decay', b),

  // Admin / Initialization
  getInitStatus:      () => http.get('/api/v1/admin/initialization/status'),
  initialize:         (b) => http.post('/api/v1/admin/initialization/initialize', b),
  retrain:            (b) => http.post('/api/v1/admin/initialization/retrain', b),
  getInitHistory:     () => http.get('/api/v1/admin/initialization/history'),

  // Business
  getBusinessDashboard: () => http.get('/api/v1/business/dashboard'),
  getBusinessSystem:    () => http.get('/api/v1/business/system'),
  getBusinessForecast:  () => http.get('/api/v1/business/forecast'),
  getBusinessGraph:     () => http.get('/api/v1/business/graph'),
  getBusinessAnalytics: () => http.get('/api/v1/business/analytics'),
  getBusinessIntel:     () => http.get('/api/v1/business/intelligence'),
  getBusinessIncident:  () => http.get('/api/v1/business/incident'),
  getBusinessAlerts:    () => http.get('/api/v1/business/alerts'),
  dismissBusinessAlert: (id) => http.post(`/api/v1/business/alerts/${id}/dismiss`),
  uploadBusinessMonthly:(f, period) => { const fd = new FormData(); fd.append('file', f); fd.append('period', period || new Date().toISOString().slice(0,7)); return multipart('/api/v1/business/upload/monthly', fd) },
  uploadBusinessActual: (f, period) => { const fd = new FormData(); fd.append('file', f); fd.append('period', period || new Date().toISOString().slice(0,7)); return multipart('/api/v1/business/upload/actual', fd) },

  // Live Operations Enterprise Dashboard
  getLiveOpsEntities:        (params) => http.get('/api/v1/business/live-ops/entities', { params }),
  getLiveOpsEntityAnalytics: (params) => http.get('/api/v1/business/live-ops/entity-analytics', { params }),
  getLiveOpsRelationships:   (entity_id) => http.get('/api/v1/business/live-ops/relationships', { params: { entity_id } }),

  // Enterprise AI Supply Chain Investigator
  investigateIncident:    (b) => http.post('/api/v1/rca/investigation/analyze-incident', b),
  simulateCounterfactual: (b) => http.post('/api/v1/rca/investigation/simulate-counterfactual', b),
  getInvestigationHistory: () => http.get('/api/v1/rca/investigation/history'),

  // Enterprise AI Investigation Copilot
  queryCopilot:           (b) => http.post('/api/v1/graphrag/copilot/query', b),
}
