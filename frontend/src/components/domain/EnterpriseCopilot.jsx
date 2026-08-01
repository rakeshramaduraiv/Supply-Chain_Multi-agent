/**
 * EnterpriseCopilot.jsx — Grounded AI Investigation Assistant Drawer
 *
 * Answers domain queries across Root Cause, Knowledge Graph, Forecast,
 * Prediction, TPKE, Counterfactual, Business Impact, and Operations.
 *
 * Formats 7 mandatory output sections:
 * Summary ➔ Evidence ➔ Reasoning ➔ Recommendation ➔ Confidence ➔ Business Impact ➔ Expected Improvement
 *
 * Multi-turn conversational memory grounded in live GraphRAG & Answer Validator.
 * Zero mock data.
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../../api/client'
import {
  Brain, Send, X, ShieldCheck, Zap, Activity, GitBranch, Layers, Lightbulb,
  ArrowRight, RefreshCw, CheckSquare
} from 'lucide-react'
import styles from './EnterpriseCopilot.module.css'

const DOMAINS = [
  'Root Cause', 'Knowledge Graph', 'Forecast', 'Prediction',
  'TPKE', 'Counterfactual', 'Business Impact', 'Operations'
]

const QUICK_PROMPTS = [
  "Why did Supplier Air Transport experience late delivery spikes?",
  "What is the TPKE temporal edge confidence for Western Europe?",
  "Simulate shifting 20% order volume to secondary carrier.",
  "What is the predicted demand forecast accuracy for Q1 2018?",
]

export default function EnterpriseCopilot({ isOpen, onClose, entityId = 'supplier_main' }) {
  const [activeDomain, setActiveDomain] = useState('Root Cause')
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])

  const copilotMut = useMutation({
    mutationFn: (qText) => api.queryCopilot({
      query: qText,
      entity_id: entityId,
      domain_category: activeDomain,
      conversation_history: messages.map(m => ({ role: m.role, content: m.text })),
    }).then(r => r.data),
    onSuccess: (res, qText) => {
      const copilotData = res?.data || {}
      setMessages(prev => [
        ...prev,
        { role: 'user', text: qText },
        { role: 'assistant', data: copilotData }
      ])
    }
  })

  if (!isOpen) return null

  const handleSend = (qStr) => {
    const textToUse = (qStr || query).trim()
    if (!textToUse || copilotMut.isPending) return
    setQuery('')
    copilotMut.mutate(textToUse)
  }

  return (
    <div className={styles.copilotOverlay}>
      <div className={styles.copilotDrawer}>
        
        {/* Header */}
        <div className={styles.drawerHeader}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Brain size={18} style={{ color: 'var(--blue)' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--tp)' }}>
                AMASCI Enterprise AI Copilot
              </div>
              <div style={{ fontSize: '10px', color: 'var(--tm)' }}>
                GraphRAG · Context Builder · Evidence Ranking · Answer Validator
              </div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tm)' }}>
            <X size={16} />
          </button>
        </div>

        {/* Domain Category Switcher Bar */}
        <div className={styles.domainBar}>
          {DOMAINS.map(d => (
            <button
              key={d}
              className={`${styles.domainChip} ${activeDomain === d ? styles.domainChipActive : ''}`}
              onClick={() => setActiveDomain(d)}
            >
              {d}
            </button>
          ))}
        </div>

        {/* Conversation Thread */}
        <div className={styles.messageArea}>
          {messages.length === 0 ? (
            <div style={{ background: 'var(--s0)', border: '1px solid var(--b)', borderRadius: '8px', padding: '14px', fontSize: '11px', color: 'var(--ts)', lineHeight: 1.5 }}>
              <div style={{ fontWeight: 700, color: 'var(--tp)', marginBottom: '4px' }}>
                Copilot initialized for domain category "{activeDomain}".
              </div>
              Ask any question on root cause, graph grounding, counterfactual interventions, or prediction variance.
              <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontWeight: 700, color: 'var(--tm)' }}>Try asking:</span>
                {QUICK_PROMPTS.map((p, idx) => (
                  <div key={idx} style={{ color: 'var(--blue)', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => handleSend(p)}>
                    • {p}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => {
              if (msg.role === 'user') {
                return <div key={i} className={styles.userBubble}>{msg.text}</div>
              }
              const d = msg.data || {}
              const evList = d.evidence || []
              const reasoning = d.reasoning || []
              const impact = d.business_impact || {}
              const exp = d.expected_improvement || {}
              const rec = d.recommendation || {}
              const conf = d.confidence || {}

              return (
                <div key={i} className={styles.copilotCard}>
                  {/* 1. Summary */}
                  <div style={{ fontSize: '11.5px', color: 'var(--tp)', lineHeight: 1.4 }}>
                    <strong>1. Summary:</strong> {d.summary}
                  </div>

                  {/* 2. Evidence */}
                  <div className={styles.sectionBox}>
                    <div style={{ fontWeight: 700, color: 'var(--blue)', marginBottom: '4px' }}>2. Evidence (Ranked Facts):</div>
                    {evList.map((ev, idx) => (
                      <div key={idx} style={{ fontSize: '10px', color: 'var(--ts)', display: 'flex', justifyContent: 'space-between' }}>
                        <span>• #{ev.rank}: {ev.fact}</span>
                        <span style={{ fontWeight: 700, color: '#00b894' }}>{ev.source} ({Math.round(ev.weight * 100)}%)</span>
                      </div>
                    ))}
                  </div>

                  {/* 3. Reasoning Chain */}
                  <div className={styles.sectionBox}>
                    <div style={{ fontWeight: 700, color: '#7c6fcd', marginBottom: '4px' }}>3. Reasoning Chain:</div>
                    {reasoning.map((step, idx) => (
                      <div key={idx} style={{ fontSize: '10px', color: 'var(--ts)' }}>
                        Step {step.step}: <strong>{step.phase}</strong> — {step.finding}
                      </div>
                    ))}
                  </div>

                  {/* 4. Recommendation */}
                  <div className={styles.sectionBox} style={{ borderColor: 'rgba(59,130,246,0.3)', background: 'rgba(59,130,246,0.04)' }}>
                    <div style={{ fontWeight: 700, color: 'var(--blue)', marginBottom: '2px' }}>4. Actionable Recommendation:</div>
                    <div style={{ fontSize: '10.5px', color: 'var(--tp)' }}>{rec.primary_action}</div>
                    <div style={{ fontSize: '9.5px', color: 'var(--tm)', marginTop: '2px' }}>
                      Priority: <strong>{rec.priority}</strong> · Cost: <strong>{rec.execution_cost}</strong> · Expected Savings: <strong>{rec.expected_savings}</strong>
                    </div>
                  </div>

                  {/* 5. Confidence */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--tm)', borderTop: '1px solid var(--b)', paddingTop: '4px' }}>
                    <span>5. Grounding Confidence: <strong style={{ color: '#00b894' }}>{conf.overall_confidence}%</strong></span>
                    <span>Status: <strong style={{ color: '#00b894' }}>{conf.validation_status}</strong></span>
                  </div>

                  {/* 6 & 7. Business Impact & Expected Improvement */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <div className={styles.sectionBox}>
                      <div style={{ fontSize: '9px', color: 'var(--tm)', textTransform: 'uppercase' }}>6. Business Impact</div>
                      <div style={{ fontSize: '12px', fontWeight: 800, color: '#d63031' }}>${impact.financial_loss?.toLocaleString() || 0}</div>
                      <div style={{ fontSize: '9.5px', color: 'var(--ts)' }}>{impact.affected_orders} Orders · {impact.expected_delay_days}d Delay</div>
                    </div>
                    <div className={styles.sectionBox}>
                      <div style={{ fontSize: '9px', color: 'var(--tm)', textTransform: 'uppercase' }}>7. Expected Improvement</div>
                      <div style={{ fontSize: '12px', fontWeight: 800, color: '#00b894' }}>{exp.cost_savings}</div>
                      <div style={{ fontSize: '9.5px', color: 'var(--ts)' }}>Delay {exp.delay_reduction} · Risk {exp.risk_reduction}</div>
                    </div>
                  </div>

                </div>
              )
            })
          )}
        </div>

        {/* Input Row */}
        <div className={styles.inputArea}>
          <input
            placeholder={`Ask Copilot about ${activeDomain.toLowerCase()}...`}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSend() }}
            style={{
              flex: 1, padding: '8px 12px', border: '1px solid var(--b)', borderRadius: '6px',
              fontSize: '11px', background: 'var(--s0)', color: 'var(--tp)', outline: 'none',
            }}
          />
          <button
            className="btn btn-primary btn-sm"
            onClick={() => handleSend()}
            disabled={!query.trim() || copilotMut.isPending}
          >
            <Send size={13} />
          </button>
        </div>

      </div>
    </div>
  )
}
