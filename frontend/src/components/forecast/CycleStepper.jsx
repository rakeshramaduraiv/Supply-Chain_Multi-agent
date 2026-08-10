/**
 * CycleStepper.jsx — 8-step Continuous Decision-Support Forecasting Lifecycle
 */
import { Play, Upload, CheckCircle, GitBranch, Network, Layers, RefreshCw, ArrowRightCircle, Loader } from 'lucide-react'
import styles from '../../pages/ForecastPage.module.css'

function StepLogPanel({ log }) {
  if (!log?.lines?.length) return null
  return (
    <div style={{
      marginTop: 4, background: 'var(--s0)', border: '1px solid var(--b)',
      borderRadius: 5, padding: '5px 7px', display: 'flex', flexDirection: 'column', gap: 2,
    }}>
      {log.lines.map((line, i) => (
        <div key={i} style={{ fontSize: '9px', color: log.done && i === log.lines.length - 1 ? '#00b894' : 'var(--ts)', fontFamily: 'var(--mono)', lineHeight: 1.4 }}>
          {line}
        </div>
      ))}
    </div>
  )
}

export default function CycleStepper({
  cycleStep, setCycleStep,
  cycleMonth, cycleTrainedUntil,
  cycleActualsUploaded, isIngestingActuals,
  cycleUploadResult, cycleRcaMut, cycleRetrainMut,
  stepLogs, clearLog, appendLog,
  overallConf, categoryForecasts,
  activeGraphVersion, activeTpkeVersion,
  forecastAnimating, forecastTimerRef,
  setForecastAnimating, setForecastTick, setActiveTab,
  setCycleActualsUploaded, setCycleModelRetrained,
  setCycleTrainedUntil, setCycleMonth, setCycleUploadResult,
  setCycleRcaResult, setCycleRetrainResult, setStepLogs,
  setIsIngestingActuals, setActualsFile,
  navigateToPage, toast, qc,
  FORECAST_MONTHS,
}) {
  const timelineSteps = [
    {
      step: 1, name: 'Pre-Event Forecast', status: cycleStep >= 1 ? 'Completed' : 'Waiting',
      comp: '100%', exec: '1.4s', conf: `${(overallConf * 100).toFixed(1)}%`,
      summary: `Generated ${categoryForecasts.length || 0} category forecasts for ${cycleMonth} · Trained on data through ${cycleTrainedUntil}`,
    },
    {
      step: 2, name: 'Actuals Ingestion',
      status: cycleActualsUploaded ? 'Completed' : cycleStep === 2 ? 'Active' : 'Waiting',
      comp: cycleActualsUploaded ? '100%' : '0%', exec: cycleActualsUploaded ? '2.1s' : '—', conf: '—',
      summary: cycleActualsUploaded ? `Ingested actual records for ${cycleMonth}` : `Awaiting actual file upload for ${cycleMonth}`,
    },
    {
      step: 3, name: 'Validation & Deviation', status: cycleStep >= 3 ? 'Completed' : 'Waiting',
      comp: cycleStep >= 3 ? '100%' : '0%', exec: '0.8s', conf: '—',
      summary: cycleStep >= 3 ? `MAPE: ${cycleUploadResult?.mape_val?.toFixed(2) ?? '—'}%` : 'Pending actuals ingestion',
    },
    {
      step: 4, name: 'Root Cause Analysis', status: cycleStep >= 4 ? 'Completed' : 'Waiting',
      comp: cycleStep >= 4 ? '100%' : '0%', exec: '3.2s', conf: '—',
      summary: cycleStep >= 4 ? 'Root cause identified via graph traversal' : 'Pending validation stage',
    },
    {
      step: 5, name: 'Knowledge Graph Mutation', status: cycleStep >= 5 ? 'Completed' : 'Waiting',
      comp: cycleStep >= 5 ? '100%' : '0%', exec: '1.1s', conf: '—',
      summary: cycleStep >= 5 ? `Updated Neo4j node risk for ${activeGraphVersion}` : 'Pending RCA resolution',
    },
    {
      step: 6, name: 'TPKE Evolution', status: cycleStep >= 6 ? 'Completed' : 'Waiting',
      comp: cycleStep >= 6 ? '100%' : '0%', exec: '2.5s', conf: '—',
      summary: cycleStep >= 6 ? `Evolved edge confidence weights (${activeTpkeVersion})` : 'Pending graph mutation',
    },
    {
      step: 7, name: 'Agent Memory & Weights', status: cycleStep >= 7 ? 'Completed' : 'Waiting',
      comp: cycleStep >= 7 ? '100%' : '0%', exec: '1.9s', conf: '—',
      summary: cycleStep >= 7 ? 'Retrained agent memory on recent monthly distribution' : 'Pending TPKE completion',
    },
    {
      step: 8, name: 'Next Forecast Readiness', status: cycleStep >= 8 ? 'Completed' : 'Waiting',
      comp: cycleStep >= 8 ? '100%' : '90%', exec: '0.2s', conf: '—',
      summary: cycleStep >= 8 ? `Cycle ready for next period (${cycleMonth})` : 'Awaiting cycle completion',
    },
  ]

  return (
    <div id="lifecycle-anchor" className={styles.timelineCard}>
      <div className={styles.timelineHead}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--tp)' }}>
            Continuous Decision-Support Forecasting Lifecycle
          </div>
          <div style={{ fontSize: '11px', color: 'var(--tm)' }}>
            Historical Data ➔ Pre-Event Forecast ➔ Validation ➔ Root Cause ➔ Graph Mutation ➔ TPKE Learning ➔ Next Period
          </div>
        </div>
        <span className="badge bdg-blue">Step {cycleStep} of 8</span>
      </div>

      <div className={styles.timelineGrid}>
        {timelineSteps.map(st => (
          <div
            key={st.step}
            className={`${styles.stepItem} ${cycleStep === st.step ? styles.stepItemActive : ''}`}
            onClick={() => setCycleStep(st.step)}
          >
            <div className={styles.stepHeader}>
              <span style={{ color: 'var(--tm)' }}>STEP {st.step}</span>
              <span className={`badge ${st.status === 'Completed' ? 'bdg-low' : st.status === 'Active' ? 'bdg-blue' : 'bdg-med'}`}>
                {st.status}
              </span>
            </div>
            <div className={styles.stepTitle}>{st.name}</div>
            <div className={styles.stepMeta}>
              <span>Exec: {st.exec}</span>
              <span>Conf: {st.conf}</span>
            </div>
            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: st.comp }} />
            </div>
            <div className={styles.stepSummary}>{st.summary}</div>

            {st.step === 1 && cycleStep === 1 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  onClick={() => {
                    clearLog(1)
                    appendLog(1, `🤖 Running multi-agent forecast for ${cycleMonth}…`)
                    appendLog(1, `📊 LightGBM trained on data through ${cycleTrainedUntil}…`)
                    setForecastAnimating(true)
                    setForecastTick(0)
                    setActiveTab('intelligence')
                    setTimeout(() => document.getElementById('agent-grid-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
                    let t = 0
                    forecastTimerRef.current = setInterval(() => {
                      t += 5
                      setForecastTick(t)
                      if (t >= 100) {
                        clearInterval(forecastTimerRef.current)
                        setForecastAnimating(false)
                        setForecastTick(100)
                        appendLog(1, `✅ ${categoryForecasts.length || 6} category forecasts generated`, true)
                        setCycleStep(2)
                      }
                    }, 45)
                  }}
                >
                  <Play size={11} /> Generate Forecast for {cycleMonth}
                </button>
                <StepLogPanel log={stepLogs[1]} />
              </div>
            )}

            {st.step === 2 && cycleStep === 2 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <div style={{ fontSize: '9px', color: 'var(--blue)', marginBottom: 4 }}>
                  Forecast period: <strong>{cycleMonth}</strong>
                </div>
                {cycleActualsUploaded ? (
                  <div style={{ fontSize: '9px', color: '#00b894', fontWeight: 700, padding: '4px 0' }}>
                    ✅ Actuals ingested — proceed to Step 3
                  </div>
                ) : isIngestingActuals ? (
                  <div style={{ fontSize: '9px', color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Loader size={11} className={styles.spin} /> Ingesting actuals…
                  </div>
                ) : (
                  <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                    onClick={() => {
                      setActiveTab('validation')
                      setTimeout(() => document.getElementById('upload-zone-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
                    }}
                  >
                    <Upload size={11} /> Upload Actuals for {cycleMonth}
                  </button>
                )}
                <StepLogPanel log={stepLogs[2]} />
              </div>
            )}

            {st.step === 3 && cycleStep === 3 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  onClick={() => {
                    clearLog(3)
                    appendLog(3, '🔢 Computing MAPE, MAE, RMSE from matched records…')
                    const mape = cycleUploadResult?.mape_val?.toFixed(2) ?? '—'
                    setTimeout(() => {
                      appendLog(3, `📊 MAPE: ${mape}%`)
                      appendLog(3, '✅ Deviation analysis complete', true)
                      setCycleStep(4)
                      setActiveTab('validation')
                      setTimeout(() => document.getElementById('error-diagnostics-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
                    }, 900)
                  }}
                >
                  <CheckCircle size={11} /> Run Validation
                </button>
                <StepLogPanel log={stepLogs[3]} />
              </div>
            )}

            {st.step === 4 && cycleStep === 4 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  disabled={cycleRcaMut.isPending}
                  onClick={() => {
                    cycleRcaMut.mutate()
                    setTimeout(() => {
                      const incidents = JSON.parse(localStorage.getItem('amasci_forecast_incidents') || '[]')
                      const periodIncident = incidents.find(i => i.period === cycleMonth)
                      localStorage.setItem('amasci_rca_focus', JSON.stringify({
                        period: cycleMonth,
                        incidentId: periodIncident?.id || null,
                        filterYear: cycleMonth.slice(0, 4),
                      }))
                      navigateToPage('/risk')
                    }, 1200)
                  }}
                >
                  {cycleRcaMut.isPending
                    ? <><Loader size={11} className={styles.spin} /> Analyzing…</>
                    : <><GitBranch size={11} /> Run Root Cause Analysis</>}
                </button>
                <StepLogPanel log={stepLogs[4]} />
              </div>
            )}

            {st.step === 5 && cycleStep === 5 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  onClick={() => {
                    clearLog(5)
                    appendLog(5, '🔗 Propagating RCA findings to Neo4j nodes…')
                    setTimeout(() => {
                      appendLog(5, `📌 Risk scores updated — graph ${activeGraphVersion}`)
                      appendLog(5, '✅ Knowledge Graph mutation applied', true)
                      qc.invalidateQueries({ queryKey: ['supplyChain'] })
                      setCycleStep(6)
                      localStorage.setItem('amasci_graph_focus', JSON.stringify({
                        mode: 'kg_mutation', version: activeGraphVersion, layer: 'reasoning',
                        highlightNode: 'carrier_ground', period: cycleMonth,
                        message: `KG Mutation applied — risk scores updated for ${cycleMonth} · Graph ${activeGraphVersion}`,
                      }))
                      navigateToPage('/graph')
                    }, 700)
                  }}
                >
                  <Network size={11} /> Apply Graph Mutation
                </button>
                <StepLogPanel log={stepLogs[5]} />
              </div>
            )}

            {st.step === 6 && cycleStep === 6 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  onClick={() => {
                    clearLog(6)
                    appendLog(6, '⚡ Running temporal edge decay pass…')
                    appendLog(6, '🔄 Strengthening pattern edges from deviation events…')
                    setTimeout(() => {
                      appendLog(6, `✅ TPKE edges evolved — ${activeTpkeVersion}`, true)
                      setCycleStep(7)
                      localStorage.setItem('amasci_graph_focus', JSON.stringify({
                        mode: 'tpke_evolution', version: activeTpkeVersion, layer: 'prediction',
                        highlightNode: 'supplier_main', period: cycleMonth,
                        scrollTo: 'tpke_evolution_section',
                        message: `TPKE edges evolved — ${activeTpkeVersion} · Period: ${cycleMonth}`,
                      }))
                      navigateToPage('/graph')
                    }, 800)
                  }}
                >
                  <Layers size={11} /> Evolve TPKE Edges
                </button>
                <StepLogPanel log={stepLogs[6]} />
              </div>
            )}

            {st.step === 7 && cycleStep === 7 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  disabled={cycleRetrainMut.isPending}
                  onClick={() => cycleRetrainMut.mutate()}
                >
                  {cycleRetrainMut.isPending
                    ? <><Loader size={11} className={styles.spin} /> Retraining…</>
                    : <><RefreshCw size={11} /> Retrain Agent Memory</>}
                </button>
                <StepLogPanel log={stepLogs[7]} />
              </div>
            )}

            {st.step === 8 && cycleStep === 8 && (
              <div className={styles.stepAction} onClick={e => e.stopPropagation()}>
                <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                  onClick={() => {
                    const nextIdx = FORECAST_MONTHS.findIndex(m => m.period === cycleMonth) + 1
                    const next = FORECAST_MONTHS[nextIdx]
                    if (next) {
                      setCycleTrainedUntil(cycleMonth)
                      setCycleMonth(next.period)
                      setCycleActualsUploaded(false)
                      setCycleModelRetrained(false)
                      setCycleUploadResult(null)
                      setCycleRcaResult(null)
                      setCycleRetrainResult(null)
                      setStepLogs({})
                      setIsIngestingActuals(false)
                      setActualsFile(null)
                      setCycleStep(1)
                      localStorage.removeItem('amasci_rca_focus')
                      toast.success(`Cycle advanced → forecasting ${next.label}`)
                      setActiveTab('intelligence')
                      setTimeout(() => document.getElementById('lifecycle-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
                    } else {
                      toast.info('All 2018 forecast months completed — cycle finished')
                    }
                  }}
                >
                  <ArrowRightCircle size={11} /> Advance to Next Month
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
