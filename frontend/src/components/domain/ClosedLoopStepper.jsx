import React, { useState, useEffect } from 'react';
import { wsClient } from '../../api/client';
import styles from './ClosedLoopStepper.module.css';

const STAGES = [
  { id: 1, label: 'Historical Dataset', desc: 'DataCo 2015-2017' },
  { id: 2, label: 'Feature Engineering', desc: 'Temporal & Lags' },
  { id: 3, label: 'Knowledge Graph', desc: 'Base Topology' },
  { id: 4, label: 'Multi-Agent Prediction', desc: 'Collaborative Chain' },
  { id: 5, label: 'Prediction Integration', desc: 'Node Properties' },
  { id: 6, label: 'KG Update', desc: 'Meta-Version ++' },
  { id: 7, label: 'Forecast', desc: '2018-01 Target' },
  { id: 8, label: 'Actual Upload', desc: 'Synthetic Ingestion' },
  { id: 9, label: 'Validation', desc: 'MAPE Calculation' },
  { id: 10, label: 'KG Update', desc: 'Actual Outcomes' },
  { id: 11, label: 'Root Cause Analysis', desc: '5-Layer Synthesis' },
  { id: 12, label: 'TPKE Evolution', desc: 'Pattern Extraction' },
  { id: 13, label: 'KG Evolution', desc: ':CAUSES & Edges' },
  { id: 14, label: 'Context Builder', desc: '6-Module Payload' },
  { id: 15, label: 'Enterprise GraphRAG', desc: '12-Stage Pipeline' },
  { id: 16, label: 'LLM Recommendations', desc: '6-Field Output' },
  { id: 17, label: 'Agent Memory', desc: 'Next Cycle Feedback' }
];

export default function ClosedLoopStepper() {
  const [activeStage, setActiveStage] = useState(17);
  const [lastEvent, setLastEvent] = useState('Closed-Loop System Active');
  const [cycleCount, setCycleCount] = useState(1);

  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event && event.type) {
        setLastEvent(event.type);
        if (event.type.includes('Started')) setActiveStage(1);
        else if (event.type.includes('Multi-Agent')) setActiveStage(4);
        else if (event.type.includes('Forecast')) setActiveStage(7);
        else if (event.type.includes('Actuals')) setActiveStage(8);
        else if (event.type.includes('Root Cause')) setActiveStage(11);
        else if (event.type.includes('TPKE')) setActiveStage(12);
        else if (event.type.includes('Memory')) {
          setActiveStage(17);
          setCycleCount(prev => prev + 1);
        }
      }
    });
    return () => unsub();
  }, []);

  return (
    <div className={styles.stepperContainer}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <span className={styles.pulseDot}></span>
          <h3 className={styles.title}>17-Stage Closed-Loop Intelligent Pipeline</h3>
        </div>
        <div className={styles.metaBadge}>
          <span>Cycle #{cycleCount}</span>
          <span className={styles.divider}>•</span>
          <span>Event: <strong>{lastEvent}</strong></span>
        </div>
      </div>

      <div className={styles.stageGrid}>
        {STAGES.map((s) => {
          const isDone = s.id <= activeStage;
          const isCurrent = s.id === activeStage;

          return (
            <div
              key={s.id}
              className={`${styles.stageCard} ${isDone ? styles.done : ''} ${isCurrent ? styles.current : ''}`}
            >
              <div className={styles.stageNumber}>{s.id}</div>
              <div className={styles.stageInfo}>
                <div className={styles.stageLabel}>{s.label}</div>
                <div className={styles.stageDesc}>{s.desc}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
