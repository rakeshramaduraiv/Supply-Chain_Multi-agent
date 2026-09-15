// src/pages/FiguresPage.jsx — DO NOT modify ForecastPage.jsx
import Fig1Ablation         from '../components/figures/Fig1Ablation'
import Fig2TPKETimeline     from '../components/figures/Fig2TPKETimeline'
import Fig3GraphStructure   from '../components/figures/Fig3GraphStructure'
import Fig4ROC              from '../components/figures/Fig4ROC'
import Fig5WalkForward      from '../components/figures/Fig5WalkForward'
import Fig6LeakageCorrection from '../components/figures/Fig6LeakageCorrection'

export default function FiguresPage() {
  return (
    <div style={{
      minHeight: '100vh',
      background: '#f1f5f9',
      fontFamily: 'system-ui,-apple-system,sans-serif',
      padding: '32px',
    }}>
      <div style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#0f172a' }}>Publication Figures</div>
        <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
          AMASCI — DataCo Smart Supply Chain · Jan 2015 – Sep 2017 Training Window · All values from live backend
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 48 }}>
        <Fig1Ablation />
        <Fig2TPKETimeline />
        <Fig3GraphStructure />
        <Fig4ROC />
        <Fig5WalkForward />
        <Fig6LeakageCorrection />
      </div>
    </div>
  )
}
