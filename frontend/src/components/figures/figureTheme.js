// src/components/figures/figureTheme.js
// Okabe-Ito colorblind-safe palette — do not substitute colours.

export const PALETTE = {
  primary:   '#0072B2',
  accent:    '#D55E00',
  green:     '#009E73',
  pink:      '#CC79A7',
  grey:      '#666666',
  lightGrey: '#CCCCCC',
  dark:      '#1a1a1a',
  gridline:  '#EFEFEF',
}

// Legacy alias used by existing components
export const COLORS = {
  blue:      PALETTE.primary,
  orange:    PALETTE.accent,
  green:     PALETTE.green,
  pink:      PALETTE.pink,
  grey:      PALETTE.grey,
  lightGrey: PALETTE.lightGrey,
}

export const FONT = { title: 20, caption: 14, footnote: 11, axisLabel: 13, tick: 12, legend: 12 }

export const CANVAS = { width: 1200, height: 700, padding: 32, background: '#FFFFFF' }

export const AXIS_STYLE = {
  tick:  { fontSize: FONT.tick,      fill: '#333' },
  label: { fontSize: FONT.axisLabel, fill: '#222' },
}

export const LEGEND_STYLE = { fontSize: FONT.legend }

// Pass to every recharts component — disables all animations for stable screenshots
export const NO_ANIMATION = { isAnimationActive: false }
