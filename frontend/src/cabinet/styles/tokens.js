// Design tokens extracted verbatim from ModelMate OS.dc.html
// Do not invent values here — every entry traces back to the prototype.

export const color = {
  bg: '#0A0B0D',
  bgPanel: '#0D0E11',
  surface: '#121316',
  surfaceHi: '#15161A',
  raised: '#1A1C20',
  sheet: '#131417',

  text: '#F2F3F0',
  textMid: '#C9CDD1',
  textDim: '#9BA0A6',
  textFaint: '#8A8F95',
  textMuted: '#6B7076',
  textGhost: '#5C6066',
  navIdle: '#B7BBC0',
  navMobileIdle: '#7A7F86',

  lime: '#D7F452',
  limeHi: '#E8FA8A',
  limeInk: '#171A05',
  limeInkSoft: '#3D4213',
  limeOlive: '#AEBF52',

  purple: '#C084FC',
  purpleHi: '#D8B4FE',
  purpleInk: '#1A0A14',
  pink: '#F0A8C8',
  pinkHot: '#F472B6',
  indigo: '#818CF8',

  green: '#4ADE80',
  greenInk: '#06240F',
  blue: '#38BDF8',
  orange: '#FB923C',
  red: '#F87171',
  yellow: '#FACC15',
};

export const line = {
  hair: 'rgba(255,255,255,.07)',
  soft: 'rgba(255,255,255,.09)',
  mid: 'rgba(255,255,255,.12)',
  strong: 'rgba(255,255,255,.14)',
  hover: 'rgba(255,255,255,.3)',
  dashed: 'rgba(255,255,255,.18)',
};

export const font = {
  display: "'Unbounded', system-ui, sans-serif",
  body: "'Manrope', system-ui, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, monospace",
};

export const radius = {
  sm: '6px',
  md: '10px',
  lg: '12px',
  xl: '16px',
  pill: '20px',
};

// Placeholder gradients (G) used for frame/photo tiles.
export const G = [
  'linear-gradient(160deg,#3B2A4F,#1A1428)',
  'linear-gradient(160deg,#4F2A3E,#241019)',
  'linear-gradient(160deg,#2A3E4F,#101A24)',
  'linear-gradient(160deg,#2A4F3B,#0F241A)',
  'linear-gradient(160deg,#4F3E2A,#241C10)',
  'linear-gradient(160deg,#33265C,#150F28)',
];

// Guide step gradients (gGrad).
export const gGrad = [
  'linear-gradient(135deg,#F472B6,#C084FC)',
  'linear-gradient(135deg,#4ADE80,#38BDF8)',
  'linear-gradient(135deg,#D7F452,#4ADE80)',
  'linear-gradient(135deg,#C084FC,#818CF8)',
  'linear-gradient(135deg,#FB923C,#F472B6)',
];

// Avatar gradients (avG) — background + ink color pairs.
export const avG = [
  { bg: 'linear-gradient(135deg,#38BDF8,#818CF8)', ink: '#0A1526' },
  { bg: 'linear-gradient(135deg,#FB923C,#F87171)', ink: '#26140A' },
  { bg: 'linear-gradient(135deg,#4ADE80,#38BDF8)', ink: '#0A2614' },
  { bg: 'linear-gradient(135deg,#F472B6,#C084FC)', ink: '#260A1C' },
  { bg: 'linear-gradient(135deg,#FACC15,#FB923C)', ink: '#262008' },
];

export const BREAKPOINT_MOBILE = 760;
export const BREAKPOINT_NARROW = 1120;
