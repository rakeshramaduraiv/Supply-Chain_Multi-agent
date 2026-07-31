const fs = require('fs')

const css = `/* ForecastPage.module.css — Oracle Fusion Analytics Inspired */

/* ── ORACLE HEADER BAND ── */
.oracleHeader {
  background: linear-gradient(135deg, #1a2332 0%, #0f1923 60%, #0d1f35 100%);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 10px;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  box-shadow: 0 4px 24px rgba(0,0,0,0.18);
}
.oracleHeaderLeft { display: flex; flex-direction: column; gap: 4px; }
.oracleHeaderTitle {
  font-size: 18px;
  font-weight: 700;
  color: #f0f4ff;
  letter-spacing: -0.3px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.oracleHeaderSub { font-size: 12px; color: rgba(255,255,255,0.45); letter-spacing: 0.02em; }
.oracleHeaderRight { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.oraclePill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.75);
  white-space: nowrap;
}
.oraclePillDot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.oracleConfBadge {
  padding: 5px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(0,184,148,0.15);
  color: #00d4a8;
  border: 1px solid rgba(0,184,148,0.3);
  letter-spacing: 0.02em;
}

/* ── TAB BAR ── */
.tabBar {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--b);
  width: 100%;
}
.tabBtn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 20px;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  font-size: 12px;
  font-weight: 500;
  color: var(--tm);
  background: transparent;
  cursor: pointer;
  transition: all 140ms ease;
  font-family: var(--font);
  white-space: nowrap;
}
.tabBtn:hover { color: var(--tp); background: var(--s2); }
.tabBtn.active {
  color: #0984e3;
  border-bottom-color: #0984e3;
  font-weight: 600;
  background: transparent;
}
.tabIcon { display: flex; align-items: center; }

/* ── ORACLE KPI STRIP ── */
.kpiStrip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 1px;
  background: var(--b);
  border: 1px solid var(--b);
  border-radius: 8px;
  overflow: hidden;
}
.kpiTile {
  background: var(--s1);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  position: relative;
  transition: background 120ms;
}
.kpiTile:hover { background: var(--s2); }
.kpiTileAccent {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
}
.kpiTileLabel {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--tm);
  margin-top: 6px;
}
.kpiTileValue {
  font-size: 24px;
  font-weight: 700;
  color: var(--tp);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5px;
}
.kpiTileValue.success { color: #00b894; }
.kpiTileValue.warning { color: #e67e22; }
.kpiTileValue.danger  { color: #d63031; }
.kpiTileValue.info    { color: #0984e3; }
.kpiTileSub {
  font-size: 10px;
  color: var(--tm);
  display: flex;
  align-items: center;
  gap: 4px;
  line-height: 1.3;
}
.kpiTileTrend {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
}
.trendUp   { background: rgba(0,184,148,.1);    color: #00b894; }
.trendDown { background: rgba(214,48,49,.08);   color: #d63031; }
.trendFlat { background: rgba(134,142,150,.08); color: var(--tm); }

/* ── HEADER STRIP (forecast tab) ── */
.headerStrip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 1px;
  background: var(--b);
  border: 1px solid var(--b);
  border-radius: 8px;
  overflow: hidden;
}
.headerCell { background: var(--s1); padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }
.headerLabel { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .07em; color: var(--tm); }
.headerValue { font-size: 15px; font-weight: 600; color: var(--tp); font-variant-numeric: tabular-nums; line-height: 1.2; }
.headerSub   { font-size: 10px; color: var(--tm); line-height: 1.3; }

/* ── CHART CONTAINERS ── */
.chartWrap   { padding: 16px 14px; min-height: 0; }
.chartLegend { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; }
.legendItem  { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ts); }
.legendDot   { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.legendLine  { width: 18px; height: 2px; border-radius: 1px; flex-shrink: 0; }
.sectionBadge { font-size: 10px; font-weight: 500; color: var(--tm); background: var(--s2); border: 1px solid var(--b); border-radius: 4px; padding: 2px 7px; }
.chartTitle  { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--tm); margin-bottom: 12px; }
.breakdownLegend { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.breakdownLegendItem { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--ts); }
.breakdownSwatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }

/* ── RECOMMENDATIONS ── */
.recoGrid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.recoProblemList { display: flex; flex-direction: column; gap: 6px; }
.recoProblemItem {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 10px 12px; border-radius: 6px;
  border: 1px solid var(--b); background: var(--s2); transition: background 140ms;
}
.recoProblemItem:hover { background: var(--s1); }
.recoProblemText  { flex: 1; }
.recoProblemTitle { font-size: 12px; font-weight: 600; color: var(--tp); margin-bottom: 2px; }
.recoProblemDesc  { font-size: 11px; color: var(--ts); line-height: 1.5; }
.actionTable { display: flex; flex-direction: column; gap: 5px; }
.actionItem {
  display: flex; gap: 10px; align-items: center; padding: 9px 12px;
  border-radius: 6px; border-left: 3px solid; background: var(--s1);
  border-top: 1px solid var(--b); border-right: 1px solid var(--b); border-bottom: 1px solid var(--b);
}
.actionItem.critical { border-left-color: var(--rh); }
.actionItem.high     { border-left-color: var(--rm); }
.actionItem.medium   { border-left-color: var(--blue); }
.actionItem.low      { border-left-color: var(--rl); }
.actionPriority {
  font-size: 9px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; padding: 2px 6px; border-radius: 3px; white-space: nowrap; flex-shrink: 0;
}
.priorityCritical { background: var(--rhb); color: var(--rh); }
.priorityHigh     { background: var(--rmb); color: var(--rm); }
.priorityMedium   { background: rgba(9,132,227,.08); color: var(--blue); }
.priorityLow      { background: var(--rlb); color: var(--rl); }
.actionText     { flex: 1; font-size: 12px; color: var(--tp); }
.actionCategory { font-size: 10px; color: var(--tm); font-family: var(--mono); flex-shrink: 0; }

/* ── BUSINESS SUMMARY ── */
.businessSummary {
  background: linear-gradient(135deg, rgba(9,132,227,.04) 0%, rgba(108,92,231,.04) 100%);
  border: 1px solid rgba(9,132,227,.15); border-radius: 8px;
  padding: 14px 16px; font-size: 13px; color: var(--ts);
  line-height: 1.7; margin-bottom: 14px; position: relative;
}
.businessSummary::before {
  content: '"'; position: absolute; top: 8px; left: 12px;
  font-size: 28px; color: var(--blue); opacity: .25; font-family: Georgia, serif; line-height: 1;
}
.summaryText { padding-left: 12px; }

/* ── CONFIDENCE METER ── */
.confidenceMeterBar  { height: 6px; border-radius: 3px; background: var(--s3); overflow: hidden; margin-top: 4px; }
.confidenceMeterFill { height: 100%; border-radius: 3px; transition: width .6s ease; }

/* ── AGENT PILLS ── */
.agentPill    { display: flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 500; border: 1px solid var(--b); background: var(--s2); white-space: nowrap; }
.agentPillDot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }

/* ── VALIDATION ── */
.validationLayout { display: grid; grid-template-columns: 380px 1fr; gap: 12px; align-items: start; }
.periodInput  { display: flex; flex-direction: column; gap: 4px; }
.periodLabel  { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--tm); }
.csvSchema    { background: var(--s2); border: 1px solid var(--b); border-radius: 6px; padding: 10px 12px; }
.csvSchemaTitle { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--tm); margin-bottom: 8px; }
.csvSchemaRow { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid var(--b); font-size: 11px; }
.csvSchemaRow:last-child { border-bottom: none; }
.csvSchemaField { color: var(--tp); font-family: var(--mono); }
.csvSchemaType  { color: var(--blue); font-family: var(--mono); font-size: 10px; }
.metricsGrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px; }
.metricCard  { background: var(--s2); border: 1px solid var(--b); border-radius: 6px; padding: 10px 12px; text-align: center; }
.metricLabel { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--tm); margin-bottom: 6px; }
.metricValue { font-size: 18px; font-weight: 700; color: var(--tp); font-variant-numeric: tabular-nums; line-height: 1; letter-spacing: -.3px; }
.metricValue.good    { color: var(--rl); }
.metricValue.neutral { color: var(--blue); }
.metricValue.bad     { color: var(--rh); }
.validationCharts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.validationBanner {
  display: flex; gap: 12px; align-items: center; padding: 14px 16px;
  border-radius: 8px; border: 1px solid; background: var(--rlb); border-color: rgba(0,184,148,.25);
}
.validationBannerIcon  { font-size: 22px; flex-shrink: 0; }
.validationBannerTitle { font-size: 14px; font-weight: 600; color: var(--tp); }
.validationBannerSub   { font-size: 12px; color: var(--ts); margin-top: 2px; }

/* ── WORKFLOW TIMELINE ── */
.workflowTimeline { display: flex; align-items: center; padding: 16px 20px; background: var(--s1); border: 1px solid var(--b); border-radius: 8px; overflow-x: auto; gap: 0; }
.workflowStep  { display: flex; align-items: center; flex-shrink: 0; }
.workflowNode  { display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 90px; }
.workflowCircle { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; border: 2px solid var(--bs); background: var(--s2); transition: all 200ms; flex-shrink: 0; }
.workflowCircle.done    { border-color: var(--rl); background: var(--rlb); }
.workflowCircle.active  { border-color: var(--blue); background: rgba(9,132,227,.08); box-shadow: 0 0 0 4px rgba(9,132,227,.08); }
.workflowCircle.pending { border-color: var(--b); background: var(--s2); }
.workflowLabel { font-size: 10px; font-weight: 500; color: var(--tm); text-align: center; max-width: 80px; line-height: 1.3; }
.workflowLabel.done   { color: var(--rl); }
.workflowLabel.active { color: var(--tp); font-weight: 600; }
.workflowDate { font-size: 9px; color: var(--tm); text-align: center; font-variant-numeric: tabular-nums; }
.workflowLine { flex: 1; height: 2px; background: var(--b); min-width: 40px; max-width: 80px; margin: 0 4px; margin-bottom: 24px; }
.workflowLine.done { background: var(--rl); }

/* ── EMPTY STATE ── */
.notReady      { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 24px; text-align: center; gap: 12px; }
.notReadyIcon  { font-size: 40px; opacity: .4; }
.notReadyTitle { font-size: 16px; font-weight: 600; color: var(--ts); }
.notReadyDesc  { font-size: 13px; color: var(--tm); max-width: 320px; line-height: 1.6; }

/* ── CYCLE CONTROLLER ── */
.cycleController {
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(135deg, #1a2332 0%, #0f1923 100%);
  border: 1px solid rgba(96,165,250,0.2); border-radius: 10px;
  padding: 16px 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  gap: 16px; flex-wrap: wrap;
}
.cycleTitle { font-size: 15px; font-weight: 700; color: #f0f4ff; display: flex; align-items: center; gap: 8px; }
.cyclePhaseBadge {
  font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px;
  background: rgba(59,130,246,0.2); color: #60a5fa;
  border: 1px solid rgba(59,130,246,0.3); letter-spacing: 0.03em;
}

/* ── COMPARISON TABLE ── */
.compTable { width: 100%; border-collapse: collapse; font-size: 12px; }
.compTable th { text-align: left; padding: 10px 14px; background: var(--s2); color: var(--tm); font-weight: 600; text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em; border-bottom: 1px solid var(--b); }
.compTable td { padding: 12px 14px; border-bottom: 1px solid var(--b); color: var(--tp); }
.compTable tr:last-child td { border-bottom: none; }

/* ── PATH CHAIN ── */
.pathChain { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 14px 16px; background: var(--s2); border-radius: 8px; border: 1px solid var(--b); }
.pathNode  { display: flex; align-items: center; gap: 6px; background: var(--s1); border: 1px solid var(--b); border-radius: 6px; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--tp); }
.pathArrow { color: var(--blue); font-weight: 700; font-size: 14px; }

/* ── CF + TPKE CARDS ── */
.cfCard {
  background: linear-gradient(135deg, rgba(0,184,148,0.08) 0%, rgba(9,132,227,0.08) 100%);
  border: 1px solid rgba(0,184,148,0.3); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.tpkeCard {
  background: linear-gradient(135deg, rgba(108,92,231,0.08) 0%, rgba(162,155,254,0.05) 100%);
  border: 1px solid rgba(108,92,231,0.3); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.tpkeParamGrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.tpkeParamBox  { background: var(--s1); border: 1px solid var(--b); border-radius: 6px; padding: 8px 12px; display: flex; flex-direction: column; gap: 2px; }
.tpkeParamLabel { font-size: 9px; font-weight: 600; color: var(--tm); text-transform: uppercase; }
.tpkeParamVal   { font-size: 14px; font-weight: 700; color: var(--tp); font-family: var(--mono); }

/* ── RESPONSIVE ── */
@media (max-width: 1300px) {
  .kpiStrip         { grid-template-columns: repeat(3, 1fr); }
  .headerStrip      { grid-template-columns: repeat(3, 1fr); }
  .recoGrid         { grid-template-columns: 1fr; }
  .validationLayout { grid-template-columns: 1fr; }
  .metricsGrid      { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 900px) {
  .kpiStrip         { grid-template-columns: repeat(2, 1fr); }
  .headerStrip      { grid-template-columns: repeat(2, 1fr); }
  .validationCharts { grid-template-columns: 1fr; }
  .metricsGrid      { grid-template-columns: repeat(2, 1fr); }
}
`

fs.writeFileSync('src/pages/ForecastPage.module.css', css, 'utf8')
console.log('CSS OK:', css.length)
