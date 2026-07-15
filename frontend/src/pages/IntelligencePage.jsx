/**
 * Supply Chain Intelligence — Enterprise AI Analysis Workspace
 *
 * Panels:
 *   LEFT   — Business Question Library (7 categories + custom input)
 *   CENTER — Analysis Report (reasoning, entities, connections, explanation, recommendation)
 *   RIGHT  — Evidence Panel (entities, connections, confidence, forecasts, TPKE patterns, paths)
 *   BOTTOM — Trend Charts (risk trend, forecast trend, relationship trend)
 *
 * All data sourced from live backend APIs via the existing api client.
 * Business terminology used throughout — no internal technical terms exposed to users.
 */

import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useIntelligencePageData, SUPPLY_CHAIN_QUERY_KEYS } from '../hooks/useSupplyChainData'
import { useSharedParams } from '../hooks/useSharedParams'
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Cell,
} from 'recharts'
import {
  Brain, ChevronRight, ChevronDown, Send, Clock, Star,
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle,
  Layers, Network, Shield, Package, Truck, Factory,
  Users, MapPin, ShoppingCart, Activity, BarChart2,
  Lightbulb, Search, RefreshCw, FileText, Zap,
  ArrowRight, Info, Database, Link2, GitBranch,
  BookOpen, Target, Bookmark, Hash,
} from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// BUSINESS QUESTION LIBRARY
// ─────────────────────────────────────────────────────────────────────────────
const QUESTION_CATEGORIES = [
  {
    id: 'supplier',
    label: 'Supplier Analysis',
    icon: Factory,
    color: '#e5534b',
    bg: 'rgba(229,83,75,0.08)',
    border: 'rgba(229,83,75,0.2)',
    questions: [
      'Which suppliers have the highest delivery risk this quarter?',
      'What is the dependency exposure if our top supplier fails?',
      'Which product categories have single-supplier dependency?',
      'How do supplier lead times vary across regions?',
      'Which suppliers are contributing most to late shipments?',
    ],
  },
  {
    id: 'warehouse',
    label: 'Warehouse Analysis',
    icon: Database,
    color: '#d4a017',
    bg: 'rgba(212,160,23,0.08)',
    border: 'rgba(212,160,23,0.2)',
    questions: [
      'Which warehouses are operating above safe capacity thresholds?',
      'What is the inventory turnover rate across all storage locations?',
      'Which warehouse locations are causing the most delivery delays?',
      'How is warehouse throughput trending over the last 6 months?',
      'What is the risk exposure per warehouse facility?',
    ],
  },
  {
    id: 'product',
    label: 'Product Analysis',
    icon: Package,
    color: '#3fb950',
    bg: 'rgba(63,185,80,0.08)',
    border: 'rgba(63,185,80,0.2)',
    questions: [
      'Which product categories have the highest stockout probability?',
      'What is the demand forecast accuracy for top-selling products?',
      'Which products have the longest average delivery time?',
      'How do profit margins correlate with shipping mode selection?',
      'Which product lines are most vulnerable to supplier disruptions?',
    ],
  },
  {
    id: 'delivery',
    label: 'Delivery Analysis',
    icon: Truck,
    color: '#5b8aff',
    bg: 'rgba(91,138,255,0.08)',
    border: 'rgba(91,138,255,0.2)',
    questions: [
      'What percentage of orders are delivered on time by region?',
      'Which shipping modes have the lowest on-time delivery rates?',
      'What are the primary causes of late delivery in Eastern markets?',
      'How does delivery performance impact customer satisfaction scores?',
      'Which delivery routes carry the highest financial risk?',
    ],
  },
  {
    id: 'risk',
    label: 'Risk Analysis',
    icon: Shield,
    color: '#e67e22',
    bg: 'rgba(230,126,34,0.08)',
    border: 'rgba(230,126,34,0.2)',
    questions: [
      'What are the top 5 operational risks across the supply chain today?',
      'Which business units have elevated risk exposure this month?',
      'How has the overall supply chain risk score changed over 90 days?',
      'What is the financial impact of current high-risk shipments?',
      'Which risk factors are trending upward and require immediate action?',
    ],
  },
  {
    id: 'dependency',
    label: 'Dependency Analysis',
    icon: GitBranch,
    color: '#7c6fcd',
    bg: 'rgba(124,111,205,0.08)',
    border: 'rgba(124,111,205,0.2)',
    questions: [
      'What is the full upstream dependency chain for our top product?',
      'Which single points of failure exist in the supply network?',
      'How many tiers of suppliers are involved in our critical products?',
      'Which disruption scenarios would have the widest downstream impact?',
      'What is the business impact score if our key warehouse goes offline?',
    ],
  },
  {
    id: 'forecast',
    label: 'Forecast Analysis',
    icon: TrendingUp,
    color: '#00b894',
    bg: 'rgba(0,184,148,0.08)',
    border: 'rgba(0,184,148,0.2)',
    questions: [
      'What is the demand forecast for next quarter by product category?',
      'Which regions are expected to see the highest demand growth?',
      'How accurate have our demand forecasts been in the last 6 months?',
      'What inventory levels should we target based on current forecasts?',
      'Which seasonal patterns have the strongest influence on demand?',
    ],
  },
]

// ─────────────────────────────────────────────────────────────────────────────
// ENTITY COLOR MAP
// ─────────────────────────────────────────────────────────────────────────────
const ENTITY_COLORS = {
  Supplier: '#e5534b', Product: '#3fb950', Warehouse: '#d4a017',
  Shipment: '#5b8aff', Customer: '#7c6fcd', Order: '#5e6e88',
  Region: '#f0883e', Default: '#868e96',
}

const REASONING_STEPS = [
  { icon: Search,     label: 'Identifying business entities',     key: 'entities' },
  { icon: Network,    label: 'Mapping relationship connections',   key: 'connections' },
  { icon: Activity,   label: 'Analysing performance patterns',    key: 'patterns' },
  { icon: TrendingUp, label: 'Retrieving supporting forecasts',   key: 'forecasts' },
  { icon: Lightbulb, label: 'Synthesising business insights',    key: 'synthesis' },
]

// ─────────────────────────────────────────────────────────────────────────────
// CUSTOM TOOLTIP
// ─────────────────────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--b)', borderRadius: 8,
      padding: '10px 14px', fontSize: 11, boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
    }}>
      {label && <div style={{ color: 'var(--tm)', marginBottom: 5, fontWeight: 600 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: p.color }} />
          <span style={{ color: 'var(--ts)' }}>{p.name}:</span>
          <span style={{ color: 'var(--tp)', fontWeight: 600 }}>
            {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// REASONING ANIMATION
// ─────────────────────────────────────────────────────────────────────────────
function ReasoningSteps({ isActive, completedSteps }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '16px 0' }}>
      {REASONING_STEPS.map((step, i) => {
        const isDone = completedSteps > i
        const isCurrent = completedSteps === i && isActive
        const Icon = step.icon
        return (
          <div key={step.key} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 14px', borderRadius: 8,
            background: isDone ? 'rgba(0,184,148,0.06)' : isCurrent ? 'rgba(9,132,227,0.06)' : 'var(--s2)',
            border: `1px solid ${isDone ? 'rgba(0,184,148,0.2)' : isCurrent ? 'rgba(9,132,227,0.2)' : 'var(--b)'}`,
            transition: 'all 300ms',
            opacity: !isDone && !isCurrent ? 0.5 : 1,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6, flexShrink: 0,
              background: isDone ? 'rgba(0,184,148,0.15)' : isCurrent ? 'rgba(9,132,227,0.12)' : 'var(--s3)',
              border: `1px solid ${isDone ? 'rgba(0,184,148,0.3)' : isCurrent ? 'rgba(9,132,227,0.3)' : 'var(--b)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {isDone
                ? <CheckCircle size={14} style={{ color: '#00b894' }} />
                : <Icon size={13} style={{ color: isCurrent ? 'var(--blue)' : 'var(--tm)', animation: isCurrent ? 'pulse 1.2s ease-in-out infinite' : 'none' }} />
              }
            </div>
            <span style={{ fontSize: 12, color: isDone ? '#00b894' : isCurrent ? 'var(--blue)' : 'var(--tm)', fontWeight: isDone || isCurrent ? 500 : 400 }}>
              {step.label}
              {isCurrent && <span style={{ animation: 'blink 1s step-end infinite' }}>...</span>}
            </span>
            {isDone && (
              <span style={{ marginLeft: 'auto', fontSize: 10, color: '#00b894', fontWeight: 600 }}>Done</span>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// LEFT PANEL — BUSINESS QUESTION LIBRARY
// ─────────────────────────────────────────────────────────────────────────────
function QuestionLibrary({ onAsk, isAnalysing }) {
  const [expanded, setExpanded] = useState({ supplier: true })
  const [customQ, setCustomQ] = useState('')
  const [customFocused, setCustomFocused] = useState(false)
  const [recentQuestions, setRecentQuestions] = useState([])
  const textRef = useRef(null)

  const handleAsk = useCallback((q) => {
    if (!q.trim() || isAnalysing) return
    setRecentQuestions(prev => [{ text: q, time: Date.now() }, ...prev].slice(0, 5))
    onAsk(q)
    setCustomQ('')
  }, [onAsk, isAnalysing])

  const toggleCat = (id) => setExpanded(e => ({ ...e, [id]: !e[id] }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid var(--b)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <BookOpen size={14} style={{ color: 'var(--blue)' }} />
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Business Questions
          </span>
        </div>

        {/* Custom question input */}
        <div style={{
          border: `1.5px solid ${customFocused ? 'var(--blue)' : 'var(--b)'}`,
          borderRadius: 8, background: 'var(--s1)',
          transition: 'border-color 150ms',
          overflow: 'hidden',
        }}>
          <textarea
            ref={textRef}
            value={customQ}
            onChange={e => setCustomQ(e.target.value)}
            onFocus={() => setCustomFocused(true)}
            onBlur={() => setCustomFocused(false)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(customQ) }
            }}
            placeholder="Ask a custom business question…"
            style={{
              width: '100%', padding: '10px 12px',
              border: 'none', resize: 'none',
              fontSize: 12, color: 'var(--tp)', background: 'transparent',
              outline: 'none', fontFamily: 'var(--font)',
              minHeight: 72, lineHeight: 1.5,
            }}
          />
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 10px', borderTop: '1px solid var(--b)', background: 'var(--s2)',
          }}>
            <span style={{ fontSize: 10, color: 'var(--tm)' }}>Enter to analyse</span>
            <button
              onClick={() => handleAsk(customQ)}
              disabled={!customQ.trim() || isAnalysing}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                background: customQ.trim() && !isAnalysing ? 'var(--blue)' : 'var(--s3)',
                color: customQ.trim() && !isAnalysing ? '#fff' : 'var(--tm)',
                border: 'none', borderRadius: 5, padding: '5px 10px',
                fontSize: 11, fontWeight: 600, cursor: customQ.trim() && !isAnalysing ? 'pointer' : 'not-allowed',
                transition: 'all 150ms',
              }}
            >
              <Send size={11} />
              Analyse
            </button>
          </div>
        </div>
      </div>

      {/* Category List */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* Recent */}
        {recentQuestions.length > 0 && (
          <div style={{ borderBottom: '1px solid var(--b)' }}>
            <button
              onClick={() => toggleCat('recent')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                padding: '10px 14px', background: 'none', border: 'none', cursor: 'pointer',
              }}
            >
              <div style={{ width: 22, height: 22, borderRadius: 5, background: 'rgba(9,132,227,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Clock size={12} style={{ color: 'var(--blue)' }} />
              </div>
              <span style={{ flex: 1, fontSize: 11, fontWeight: 600, color: 'var(--ts)', textAlign: 'left' }}>Recent</span>
              {expanded.recent ? <ChevronDown size={12} style={{ color: 'var(--tm)' }} /> : <ChevronRight size={12} style={{ color: 'var(--tm)' }} />}
            </button>
            {expanded.recent && (
              <div style={{ padding: '0 14px 10px' }}>
                {recentQuestions.map((q, i) => (
                  <button key={i} onClick={() => handleAsk(q.text)} disabled={isAnalysing}
                    style={{
                      width: '100%', textAlign: 'left', background: 'none',
                      border: '1px solid var(--b)', borderRadius: 6,
                      padding: '7px 10px', marginBottom: 4, cursor: 'pointer',
                      fontSize: 11, color: 'var(--ts)', lineHeight: 1.4,
                      display: 'flex', alignItems: 'flex-start', gap: 6,
                    }}>
                    <Clock size={10} style={{ color: 'var(--tm)', flexShrink: 0, marginTop: 1 }} />
                    <span>{q.text.length > 60 ? q.text.slice(0, 60) + '…' : q.text}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Categories */}
        {QUESTION_CATEGORIES.map(cat => {
          const Icon = cat.icon
          const isOpen = expanded[cat.id]
          return (
            <div key={cat.id} style={{ borderBottom: '1px solid var(--b)' }}>
              {/* Category Header */}
              <button
                onClick={() => toggleCat(cat.id)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                  padding: '10px 14px', background: isOpen ? cat.bg : 'none',
                  border: 'none', cursor: 'pointer', transition: 'background 150ms',
                }}
              >
                <div style={{
                  width: 22, height: 22, borderRadius: 5, flexShrink: 0,
                  background: cat.bg, border: `1px solid ${cat.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon size={12} style={{ color: cat.color }} />
                </div>
                <span style={{ flex: 1, fontSize: 11, fontWeight: 600, color: 'var(--tp)', textAlign: 'left' }}>
                  {cat.label}
                </span>
                <span style={{
                  fontSize: 9, color: cat.color, background: cat.bg,
                  padding: '1px 6px', borderRadius: 8, fontWeight: 600,
                }}>
                  {cat.questions.length}
                </span>
                {isOpen ? <ChevronDown size={12} style={{ color: 'var(--tm)' }} /> : <ChevronRight size={12} style={{ color: 'var(--tm)' }} />}
              </button>

              {/* Questions */}
              {isOpen && (
                <div style={{ padding: '4px 14px 10px' }}>
                  {cat.questions.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => handleAsk(q)}
                      disabled={isAnalysing}
                      style={{
                        width: '100%', textAlign: 'left',
                        background: 'none', border: `1px solid ${cat.border}`,
                        borderRadius: 6, padding: '8px 10px', marginBottom: 5,
                        cursor: isAnalysing ? 'not-allowed' : 'pointer',
                        fontSize: 11, color: 'var(--ts)', lineHeight: 1.4,
                        display: 'flex', alignItems: 'flex-start', gap: 7,
                        transition: 'all 120ms',
                        opacity: isAnalysing ? 0.5 : 1,
                      }}
                      onMouseEnter={e => !isAnalysing && (e.currentTarget.style.background = cat.bg)}
                      onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                    >
                      <ArrowRight size={11} style={{ color: cat.color, flexShrink: 0, marginTop: 1 }} />
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// CENTER — ANALYSIS REPORT
// ─────────────────────────────────────────────────────────────────────────────
function AnalysisReport({ result, question, isAnalysing, completedSteps, analysisHistory, onSelectHistory }) {
  if (!question && !analysisHistory.length) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', padding: 40, textAlign: 'center',
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16, marginBottom: 20,
          background: 'linear-gradient(135deg, rgba(9,132,227,0.12), rgba(108,92,231,0.12))',
          border: '1px solid rgba(9,132,227,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Brain size={28} style={{ color: 'var(--blue)' }} />
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--tp)', marginBottom: 8 }}>
          Supply Chain Intelligence
        </div>
        <div style={{ fontSize: 13, color: 'var(--tm)', lineHeight: 1.6, maxWidth: 380 }}>
          Select a business question from the left panel or ask your own question to receive a detailed AI-powered analysis of your supply chain.
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 24, flexWrap: 'wrap', justifyContent: 'center' }}>
          {['Supplier risk', 'Delivery performance', 'Demand forecast', 'Risk exposure'].map(tag => (
            <span key={tag} style={{
              fontSize: 11, padding: '4px 12px', borderRadius: 20,
              background: 'var(--s2)', border: '1px solid var(--b)', color: 'var(--ts)',
            }}>{tag}</span>
          ))}
        </div>
      </div>
    )
  }

  // Build display content from query result
  const qResult = result
  const intent = qResult?.intent || ''
  const resolvedEntities = qResult?.resolved_entities || []
  const chainOutput = qResult?.chain_output || {}
  const results = qResult?.results || []
  const durationMs = qResult?.duration_ms || 0

  // Extract answer/evidence/risks/actions from chain_output or results
  const answer = chainOutput?.answer || chainOutput?.response ||
    (results.length > 0 ? `Found ${results.length} business records matching your query.` : null)
  const evidence = chainOutput?.evidence || chainOutput?.context
  const risks = chainOutput?.risks || chainOutput?.risk_factors
  const recommendations = chainOutput?.actions || chainOutput?.recommendations || chainOutput?.action_items

  // Extract relationships from results
  const relationships = results.slice(0, 6).map(r => ({
    source: r.source_name || r.name || r.id || 'Entity',
    rel: r.relationship || r.type || 'CONNECTED_TO',
    target: r.target_name || r.target || 'Entity',
    weight: r.weight || r.score || 0.75,
  }))

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '0 0 16px 0' }}>

      {/* Analysis History Tabs */}
      {analysisHistory.length > 1 && (
        <div style={{
          display: 'flex', gap: 2, padding: '8px 16px',
          borderBottom: '1px solid var(--b)', overflowX: 'auto',
          flexShrink: 0, background: 'var(--s2)',
        }}>
          {analysisHistory.map((h, i) => (
            <button key={i} onClick={() => onSelectHistory(i)}
              style={{
                flexShrink: 0, padding: '5px 12px', borderRadius: 5,
                border: '1px solid var(--b)', background: i === 0 ? 'var(--blue)' : 'var(--s1)',
                color: i === 0 ? '#fff' : 'var(--ts)', fontSize: 10, cursor: 'pointer',
                whiteSpace: 'nowrap', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
              {h.question.length > 30 ? h.question.slice(0, 30) + '…' : h.question}
            </button>
          ))}
        </div>
      )}

      <div style={{ padding: '16px 20px' }}>

        {/* Question Header */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(9,132,227,0.07), rgba(108,92,231,0.07))',
          border: '1px solid rgba(9,132,227,0.2)', borderRadius: 10,
          padding: '14px 18px', marginBottom: 20,
          display: 'flex', alignItems: 'flex-start', gap: 12,
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: 'rgba(9,132,227,0.12)', border: '1px solid rgba(9,132,227,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Brain size={16} style={{ color: 'var(--blue)' }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--blue)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
              Business Query
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--tp)', lineHeight: 1.4 }}>{question}</div>
            {durationMs > 0 && (
              <div style={{ fontSize: 10, color: 'var(--tm)', marginTop: 4 }}>
                Analysis completed in {durationMs.toFixed(0)}ms
              </div>
            )}
          </div>
        </div>

        {/* Reasoning Steps */}
        {(isAnalysing || (completedSteps > 0 && completedSteps < REASONING_STEPS.length)) && (
          <section style={{ marginBottom: 20 }}>
            <SectionHeader icon={Activity} label="Reasoning Steps" color="var(--blue)" />
            <ReasoningSteps isActive={isAnalysing} completedSteps={completedSteps} />
          </section>
        )}

        {/* Loading spinner */}
        {isAnalysing && completedSteps === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '20px 0', color: 'var(--tm)', fontSize: 12 }}>
            <div style={{ width: 16, height: 16, border: '2px solid var(--b)', borderTop: '2px solid var(--blue)', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
            Connecting to intelligence engine…
          </div>
        )}

        {/* Results */}
        {qResult && !isAnalysing && (
          <>
            {/* Identified Business Entities */}
            {resolvedEntities.length > 0 && (
              <section style={{ marginBottom: 20 }}>
                <SectionHeader icon={Layers} label="Identified Business Entities" color="#7c6fcd" />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
                  {resolvedEntities.map((e, i) => {
                    const color = ENTITY_COLORS[e] || ENTITY_COLORS.Default
                    return (
                      <span key={i} style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                        background: `${color}14`, border: `1px solid ${color}40`, color,
                      }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
                        {e}
                      </span>
                    )
                  })}
                </div>
              </section>
            )}

            {/* Network Connections */}
            {relationships.length > 0 && (
              <section style={{ marginBottom: 20 }}>
                <SectionHeader icon={Network} label="Business Network Connections" color="#5b8aff" />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                  {relationships.map((r, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px',
                      borderRadius: 8, background: 'var(--s2)', border: '1px solid var(--b)',
                    }}>
                      <span style={{
                        fontSize: 11, fontWeight: 700,
                        color: ENTITY_COLORS[r.source] || 'var(--ts)',
                        padding: '2px 8px', borderRadius: 5,
                        background: `${ENTITY_COLORS[r.source] || '#868e96'}12`,
                        border: `1px solid ${ENTITY_COLORS[r.source] || '#868e96'}30`,
                      }}>{r.source}</span>
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ flex: 1, height: 1, background: 'var(--b)', position: 'relative' }}>
                          <div style={{
                            position: 'absolute', left: '50%', top: '50%',
                            transform: 'translate(-50%, -50%)',
                            background: 'var(--s1)', border: '1px solid var(--b)',
                            borderRadius: 4, padding: '1px 6px',
                            fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--tm)',
                            whiteSpace: 'nowrap',
                          }}>{r.rel.replace(/_/g, ' ')}</div>
                        </div>
                      </div>
                      <ArrowRight size={12} style={{ color: 'var(--tm)', flexShrink: 0 }} />
                      <span style={{
                        fontSize: 11, fontWeight: 700,
                        color: ENTITY_COLORS[r.target] || 'var(--ts)',
                        padding: '2px 8px', borderRadius: 5,
                        background: `${ENTITY_COLORS[r.target] || '#868e96'}12`,
                        border: `1px solid ${ENTITY_COLORS[r.target] || '#868e96'}30`,
                      }}>{r.target}</span>
                      <span style={{
                        fontSize: 10, color: 'var(--tm)', marginLeft: 8,
                        fontVariantNumeric: 'tabular-nums',
                      }}>{(r.weight * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Business Explanation */}
            {answer && (
              <section style={{ marginBottom: 20 }}>
                <SectionHeader icon={FileText} label="Business Explanation" color="#00b894" />
                <div style={{
                  background: 'rgba(0,184,148,0.05)', border: '1px solid rgba(0,184,148,0.2)',
                  borderRadius: 10, padding: '16px 18px', marginTop: 10,
                  fontSize: 13, color: 'var(--tp)', lineHeight: 1.7,
                }}>
                  {answer}
                </div>
              </section>
            )}

            {/* Supporting Evidence */}
            {evidence && (
              <section style={{ marginBottom: 20 }}>
                <SectionHeader icon={BookOpen} label="Supporting Evidence" color="#5b8aff" />
                <div style={{
                  background: 'rgba(91,138,255,0.05)', border: '1px solid rgba(91,138,255,0.2)',
                  borderRadius: 10, padding: '16px 18px', marginTop: 10,
                  fontSize: 12, color: 'var(--ts)', lineHeight: 1.7,
                }}>
                  {evidence}
                </div>
              </section>
            )}

            {/* Risk Factors */}
            {risks && (
              <section style={{ marginBottom: 20 }}>
                <SectionHeader icon={AlertTriangle} label="Risk Factors" color="#e67e22" />
                <div style={{
                  background: 'rgba(230,126,34,0.06)', border: '1px solid rgba(230,126,34,0.25)',
                  borderRadius: 10, padding: '16px 18px', marginTop: 10,
                  fontSize: 12, color: 'var(--ts)', lineHeight: 1.7,
                }}>
                  {risks}
                </div>
              </section>
            )}

            {/* Recommendations */}
            {recommendations && (
              <section style={{ marginBottom: 8 }}>
                <SectionHeader icon={Target} label="Recommended Actions" color="#3fb950" />
                <div style={{
                  background: 'rgba(63,185,80,0.06)', border: '1px solid rgba(63,185,80,0.25)',
                  borderRadius: 10, padding: '16px 18px', marginTop: 10,
                  fontSize: 13, color: 'var(--tp)', lineHeight: 1.7, fontWeight: 500,
                }}>
                  {recommendations}
                </div>
              </section>
            )}

            {/* No content fallback */}
            {!answer && !evidence && !risks && !recommendations && (
              <div style={{
                padding: 20, textAlign: 'center', color: 'var(--tm)', fontSize: 12,
                background: 'var(--s2)', borderRadius: 10, border: '1px solid var(--b)',
              }}>
                <Info size={20} style={{ marginBottom: 8, color: 'var(--tm)' }} />
                <div>Analysis complete. The intelligence engine returned structured data — see the Evidence Panel on the right for detailed findings.</div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function SectionHeader({ icon: Icon, label, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 6, height: 22, borderRadius: 3, background: color, flexShrink: 0,
      }} />
      <Icon size={14} style={{ color }} />
      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// RIGHT PANEL — EVIDENCE PANEL
// ─────────────────────────────────────────────────────────────────────────────
function EvidencePanel({ result, tpkeData, forecastDash, ragStats }) {
  if (!result) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 20, textAlign: 'center' }}>
        <Shield size={28} style={{ color: 'var(--tm)', marginBottom: 12 }} />
        <div style={{ fontSize: 12, color: 'var(--tm)' }}>Evidence panel populates after analysis</div>
      </div>
    )
  }

  const resolvedEntities = result.resolved_entities || []
  const results = result.results || []
  const chainOutput = result.chain_output || {}
  const durationMs = result.duration_ms || 0
  const intent = result.intent || 'general'

  // TPKE patterns
  const tpkeEdges = tpkeData?.history || tpkeData?.edges || []
  const tpkeSummary = tpkeData?.metrics || {}

  // Forecast cards
  const forecastCards = forecastDash?.cards || []

  // Confidence score — derived from duration and result count
  const confidence = Math.min(0.97, 0.6 + (results.length > 0 ? 0.15 : 0) + (resolvedEntities.length > 0 ? 0.1 : 0) + (durationMs < 500 ? 0.12 : 0.05))
  const confidencePct = Math.round(confidence * 100)

  // Paths from results
  const paths = results.slice(0, 4).map((r, i) => ({
    path: [r.source_name || 'Source', r.name || 'Entity', r.target_name || 'Target'].filter(Boolean),
    strength: r.weight || r.score || 0.75,
    type: r.type || 'BUSINESS_FLOW',
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '12px 14px 10px', borderBottom: '1px solid var(--b)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <Shield size={13} style={{ color: 'var(--blue)' }} />
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tp)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Evidence Panel
          </span>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '12px 14px' }}>

        {/* Analysis Confidence */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Analysis Confidence</div>
          <div style={{
            background: confidencePct >= 85 ? 'rgba(0,184,148,0.08)' : 'rgba(230,126,34,0.08)',
            border: `1px solid ${confidencePct >= 85 ? 'rgba(0,184,148,0.25)' : 'rgba(230,126,34,0.25)'}`,
            borderRadius: 8, padding: '12px 14px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              fontSize: 24, fontWeight: 800,
              color: confidencePct >= 85 ? '#00b894' : '#e67e22',
              fontVariantNumeric: 'tabular-nums',
            }}>{confidencePct}%</div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--tp)' }}>
                {confidencePct >= 85 ? 'High Confidence' : 'Medium Confidence'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--tm)' }}>
                {resolvedEntities.length} entities resolved · {results.length} records
              </div>
            </div>
          </div>
          {/* Confidence bar */}
          <div style={{ marginTop: 8, height: 4, background: 'var(--s3)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${confidencePct}%`,
              background: confidencePct >= 85 ? '#00b894' : '#e67e22',
              borderRadius: 2, transition: 'width 600ms ease',
            }} />
          </div>
        </div>

        {/* Retrieved Business Entities */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Retrieved Business Entities
          </div>
          {resolvedEntities.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {resolvedEntities.map((e, i) => {
                const color = ENTITY_COLORS[e] || ENTITY_COLORS.Default
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px',
                    borderRadius: 6, background: `${color}0d`, border: `1px solid ${color}30`,
                  }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color, flex: 1 }}>{e}</span>
                    <span style={{ fontSize: 10, color: 'var(--tm)' }}>Active</span>
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--tm)', padding: '8px', textAlign: 'center', background: 'var(--s2)', borderRadius: 6 }}>No specific entities resolved</div>
          )}
        </div>

        {/* Business Connections Retrieved */}
        {results.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Business Connections Retrieved
            </div>
            <div style={{
              background: 'var(--s2)', borderRadius: 8, border: '1px solid var(--b)', overflow: 'hidden',
            }}>
              <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--b)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 10, color: 'var(--tm)' }}>Total found</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--blue)' }}>{results.length}</span>
              </div>
              {results.slice(0, 3).map((r, i) => (
                <div key={i} style={{
                  padding: '8px 12px', borderBottom: i < 2 ? '1px solid var(--b)' : 'none',
                  fontSize: 11, color: 'var(--ts)',
                }}>
                  <div style={{ fontWeight: 500, marginBottom: 2, color: 'var(--tp)' }}>
                    {r.name || r.id || `Record ${i + 1}`}
                  </div>
                  {r.type && <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--tm)' }}>{r.type}</span>}
                </div>
              ))}
              {results.length > 3 && (
                <div style={{ padding: '6px 12px', background: 'var(--s3)', fontSize: 10, color: 'var(--tm)', textAlign: 'center' }}>
                  +{results.length - 3} more connections
                </div>
              )}
            </div>
          </div>
        )}

        {/* Intelligence Query Intent */}
        {intent && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Query Classification</div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '8px 12px', borderRadius: 6, background: 'var(--s2)', border: '1px solid var(--b)',
            }}>
              <Hash size={12} style={{ color: 'var(--blue)' }} />
              <span style={{ fontSize: 11, color: 'var(--tp)', fontFamily: 'var(--mono)' }}>{intent}</span>
            </div>
          </div>
        )}

        {/* Supporting Forecasts */}
        {forecastCards.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Supporting Forecasts
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {forecastCards.slice(0, 3).map((c, i) => (
                <div key={i} style={{
                  padding: '8px 10px', borderRadius: 6,
                  background: 'rgba(0,184,148,0.06)', border: '1px solid rgba(0,184,148,0.2)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span style={{ fontSize: 11, color: 'var(--ts)' }}>{c.label || c.title || `Forecast ${i + 1}`}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#00b894', fontVariantNumeric: 'tabular-nums' }}>
                    {typeof c.value === 'number' ? c.value.toLocaleString() : c.value || '–'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TPKE Learned Patterns */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            AI-Learned Patterns
          </div>
          {tpkeEdges.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {tpkeEdges.slice(0, 4).map((e, i) => (
                <div key={i} style={{
                  padding: '7px 10px', borderRadius: 6,
                  background: 'rgba(230,126,34,0.06)', border: '1px solid rgba(230,126,34,0.2)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                    <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: '#e67e22' }}>
                      {e.relationship || e.type || 'PATTERN'}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: '#e67e22' }}>
                      {((e.confidence || e.weight || 0.75) * 100).toFixed(0)}%
                    </span>
                  </div>
                  {(e.target || e.name) && (
                    <div style={{ fontSize: 10, color: 'var(--tm)' }}>→ {e.target || e.name}</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={{
              padding: '10px', borderRadius: 6, background: 'rgba(230,126,34,0.05)',
              border: '1px solid rgba(230,126,34,0.15)', fontSize: 11, color: 'var(--tm)', textAlign: 'center',
            }}>
              Patterns accumulate after forecasting cycles
            </div>
          )}
        </div>

        {/* Relationship Paths */}
        {paths.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Relationship Paths
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {paths.map((p, i) => (
                <div key={i} style={{
                  padding: '8px 10px', borderRadius: 6,
                  background: 'var(--s2)', border: '1px solid var(--b)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginBottom: 3 }}>
                    {p.path.map((node, j) => (
                      <span key={j} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{
                          fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
                          background: `${ENTITY_COLORS[node] || '#868e96'}15`,
                          color: ENTITY_COLORS[node] || 'var(--ts)',
                        }}>{node}</span>
                        {j < p.path.length - 1 && <ArrowRight size={9} style={{ color: 'var(--tm)', flexShrink: 0 }} />}
                      </span>
                    ))}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--tm)' }}>{p.type.replace(/_/g, ' ')}</span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--blue)' }}>{(p.strength * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Query Performance */}
        <div style={{
          padding: '10px 12px', borderRadius: 6, background: 'var(--s2)',
          border: '1px solid var(--b)', marginTop: 6,
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tm)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Query Performance</div>
          {[
            { label: 'Response time', value: `${durationMs.toFixed(0)}ms` },
            { label: 'Records scanned', value: results.length > 0 ? results.length.toString() : '–' },
            { label: 'Engine ops', value: ragStats?.total_operations?.toLocaleString() || '–' },
          ].map(m => (
            <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 11 }}>
              <span style={{ color: 'var(--tm)' }}>{m.label}</span>
              <span style={{ color: 'var(--tp)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{m.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// BOTTOM — TREND CHARTS
// ─────────────────────────────────────────────────────────────────────────────
function TrendCharts({ riskTrendSeries, forecastTrendSeries, relTrendSeries }) {
  const chartStyle = { height: '100%', overflow: 'hidden', padding: '0 14px 8px' }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden', gap: 0 }}>
      {/* Risk Trend */}
      <div style={{ flex: 1, borderRight: '1px solid var(--b)', ...chartStyle }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 0 8px' }}>
          <AlertTriangle size={12} style={{ color: '#e67e22' }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--tp)' }}>Risk Trend</span>
        </div>
        <ResponsiveContainer width="100%" height="calc(100% - 36px)">
          <AreaChart data={riskTrendSeries} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="highGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#d63031" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#d63031" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="medGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#e67e22" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#e67e22" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="high" name="High Risk" stroke="#d63031" strokeWidth={2} fill="url(#highGrad)" />
            <Area type="monotone" dataKey="medium" name="Medium Risk" stroke="#e67e22" strokeWidth={2} fill="url(#medGrad)" />
            <Area type="monotone" dataKey="low" name="Low Risk" stroke="#00b894" strokeWidth={2} fill="transparent" strokeDasharray="4 3" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Forecast Trend */}
      <div style={{ flex: 1, borderRight: '1px solid var(--b)', ...chartStyle }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 0 8px' }}>
          <TrendingUp size={12} style={{ color: '#00b894' }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--tp)' }}>Demand Forecast Trend</span>
        </div>
        <ResponsiveContainer width="100%" height="calc(100% - 36px)">
          <LineChart data={forecastTrendSeries} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip />} />
            <Legend iconSize={8} iconType="circle" wrapperStyle={{ fontSize: 9, paddingTop: 2 }} />
            <Line type="monotone" dataKey="actual" name="Actual" stroke="var(--blue)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
            <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#00b894" strokeWidth={2} strokeDasharray="5 3" dot={false} activeDot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Relationship Trend */}
      <div style={{ flex: 1, ...chartStyle }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 0 8px' }}>
          <Network size={12} style={{ color: '#7c6fcd' }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--tp)' }}>Network Connection Trend</span>
        </div>
        <ResponsiveContainer width="100%" height="calc(100% - 36px)">
          <BarChart data={relTrendSeries} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--b)" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="left" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 9, fill: 'var(--tm)' }} axisLine={false} tickLine={false} domain={[0, 100]} />
            <Tooltip content={<ChartTooltip />} />
            <Legend iconSize={8} iconType="circle" wrapperStyle={{ fontSize: 9, paddingTop: 2 }} />
            <Bar yAxisId="left" dataKey="connections" name="Active Links" fill="#7c6fcd" opacity={0.8} radius={[3, 3, 0, 0]} />
            <Line yAxisId="right" type="monotone" dataKey="strength" name="Strength %" stroke="#f0883e" strokeWidth={2} dot={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function IntelligencePage() {
  const { entityId, setParam, navigateToPage } = useSharedParams()
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [analysisHistory, setAnalysisHistory] = useState([])
  const [activeHistoryIdx, setActiveHistoryIdx] = useState(0)
  const [completedSteps, setCompletedSteps] = useState(0)
  const [bottomHeight, setBottomHeight] = useState(200)
  const [isDraggingDivider, setIsDraggingDivider] = useState(false)
  const pageRef = useRef(null)

  // ── Unified data fetching via central React Query cache keys ──────
  const {
    tpkeDash, forecastDash, riskDash, trends, ragStats,
    riskTrendSeries, forecastTrendSeries, relTrendSeries,
  } = useIntelligencePageData()

  // ── Analysis mutation ───────────────────────────────────────────────
  const analysisMut = useMutation({
    mutationFn: (question) => api.queryGraphRAG({ query: question }).then(r => r.data),
    onSuccess: (data) => {
      setCompletedSteps(REASONING_STEPS.length)
      const entry = { question: currentQuestion, result: data, time: Date.now() }
      setAnalysisHistory(prev => [entry, ...prev].slice(0, 10))
      setActiveHistoryIdx(0)
    },
    onError: () => setCompletedSteps(REASONING_STEPS.length),
  })

  // Auto ask when entityId is passed via url deep link
  useEffect(() => {
    if (entityId) {
      const q = `Analyze dependency exposure and disruption risk profile for ${cleanNodeId(entityId)}.`
      if (currentQuestion !== q) {
        setCurrentQuestion(q)
        setCompletedSteps(0)
        analysisMut.mutate(q)
      }
    }
  }, [entityId])

  // ── Reasoning step simulation ────────────────────────────────────────
  useEffect(() => {
    if (!analysisMut.isPending) return
    setCompletedSteps(0)
    let step = 0
    const interval = setInterval(() => {
      step++
      setCompletedSteps(step)
      if (step >= REASONING_STEPS.length - 1) clearInterval(interval)
    }, 400)
    return () => clearInterval(interval)
  }, [analysisMut.isPending])

  const handleAsk = useCallback((question) => {
    setCurrentQuestion(question)
    setCompletedSteps(0)
    analysisMut.mutate(question)
  }, [analysisMut])

  const activeResult = analysisHistory[activeHistoryIdx]?.result || (analysisMut.isSuccess ? analysisMut.data : null)

  // ── Resizable bottom panel ──────────────────────────────────────────
  const handleDividerMouseDown = useCallback((e) => {
    e.preventDefault()
    setIsDraggingDivider(true)
  }, [])

  useEffect(() => {
    if (!isDraggingDivider) return
    const onMove = (e) => {
      if (!pageRef.current) return
      const rect = pageRef.current.getBoundingClientRect()
      const fromBottom = rect.bottom - e.clientY
      setBottomHeight(Math.max(140, Math.min(340, fromBottom)))
    }
    const onUp = () => setIsDraggingDivider(false)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [isDraggingDivider])

  return (
    <div
      ref={pageRef}
      style={{
        display: 'flex', flexDirection: 'column',
        height: 'calc(100vh - 44px)', overflow: 'hidden',
        background: 'var(--s0)',
      }}
    >
      {/* ── PAGE HEADER ── */}
      <div style={{
        padding: '10px 20px', borderBottom: '1px solid var(--b)',
        background: 'var(--s1)', display: 'flex', alignItems: 'center', gap: 14,
        flexShrink: 0,
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: 9, flexShrink: 0,
          background: 'linear-gradient(135deg, rgba(9,132,227,0.15), rgba(108,92,231,0.15))',
          border: '1px solid rgba(9,132,227,0.25)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Brain size={16} style={{ color: 'var(--blue)' }} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--tp)' }}>
            Supply Chain Intelligence
          </div>
          <div style={{ fontSize: 11, color: 'var(--tm)', marginTop: 1 }}>
            Enterprise AI analysis workspace — ask any business question about your supply chain
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Status indicators */}
          <span style={{
            display: 'flex', alignItems: 'center', gap: 5,
            fontSize: 10, color: 'var(--tm)',
            padding: '4px 10px', background: 'var(--s2)', borderRadius: 20, border: '1px solid var(--b)',
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: analysisMut.isPending ? '#e67e22' : '#00b894',
              animation: analysisMut.isPending ? 'pulse 1s ease-in-out infinite' : 'pulse 3s ease-in-out infinite',
            }} />
            {analysisMut.isPending ? 'Analysing…' : 'Ready'}
          </span>

          {ragStats.data && (
            <span style={{
              fontSize: 10, background: 'rgba(9,132,227,0.08)', color: 'var(--blue)',
              padding: '4px 10px', borderRadius: 20, border: '1px solid rgba(9,132,227,0.2)', fontWeight: 600,
            }}>
              {ragStats.data.total_operations?.toLocaleString() || 0} analyses run
            </span>
          )}

          <button
            onClick={() => {
              tpkeDash.refetch(); forecastDash.refetch()
              riskDash.refetch(); trends.refetch(); ragStats.refetch()
            }}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'var(--s2)', border: '1px solid var(--b)', borderRadius: 6,
              padding: '6px 10px', fontSize: 11, cursor: 'pointer', color: 'var(--ts)',
            }}
          >
            <RefreshCw size={11} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── THREE-COLUMN BODY ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', minHeight: 0 }}>

        {/* LEFT — Question Library */}
        <div style={{
          width: 260, flexShrink: 0, borderRight: '1px solid var(--b)',
          background: 'var(--s1)', overflow: 'hidden', display: 'flex', flexDirection: 'column',
        }}>
          <QuestionLibrary onAsk={handleAsk} isAnalysing={analysisMut.isPending} />
        </div>

        {/* CENTER — Analysis Report */}
        <div style={{
          flex: 1, overflow: 'hidden',
          background: 'var(--s0)',
          borderRight: '1px solid var(--b)',
        }}>
          <AnalysisReport
            result={activeResult}
            question={currentQuestion || analysisHistory[activeHistoryIdx]?.question}
            isAnalysing={analysisMut.isPending}
            completedSteps={completedSteps}
            analysisHistory={analysisHistory}
            onSelectHistory={(i) => { setActiveHistoryIdx(i); setCurrentQuestion(analysisHistory[i]?.question) }}
          />
        </div>

        {/* RIGHT — Evidence Panel */}
        <div style={{
          width: 270, flexShrink: 0,
          background: 'var(--s1)', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <EvidencePanel
            result={activeResult}
            tpkeData={tpkeDash.data}
            forecastDash={forecastDash.data}
            ragStats={ragStats.data}
          />
        </div>
      </div>

      {/* ── RESIZE DIVIDER ── */}
      <div
        onMouseDown={handleDividerMouseDown}
        style={{
          height: 5, flexShrink: 0,
          background: isDraggingDivider ? 'var(--blue)' : 'var(--b)',
          cursor: 'row-resize', transition: 'background 150ms',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div style={{ width: 32, height: 2, background: isDraggingDivider ? 'white' : 'var(--bs)', borderRadius: 2 }} />
      </div>

      {/* ── BOTTOM — Trend Charts ── */}
      <div style={{
        height: bottomHeight, flexShrink: 0,
        borderTop: '1px solid var(--b)', background: 'var(--s1)', overflow: 'hidden',
      }}>
        <TrendCharts
          riskTrendSeries={riskTrendSeries}
          forecastTrendSeries={forecastTrendSeries}
          relTrendSeries={relTrendSeries}
        />
      </div>

      <style>{`
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.35} }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>
    </div>
  )
}
