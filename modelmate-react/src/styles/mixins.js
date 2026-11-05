// Style bases lifted from the prototype's shared constants.
import { color, line, font } from './tokens';

export const iconBox = (size, extra = {}) => ({
  width: size, height: size, flex: 'none',
  borderRadius: size >= 40 ? 12 : 11,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  ...extra,
});

export const chipBase = {
  fontFamily: font.mono, fontSize: 8.5, letterSpacing: '1px',
  padding: '2px 8px', borderRadius: 20,
};

export const stActive = {
  ...chipBase,
  background: 'rgba(74,222,128,.12)', color: color.green, border: '1px solid rgba(74,222,128,.3)',
};
export const stWarn = {
  ...chipBase,
  background: 'rgba(251,146,60,.12)', color: color.orange, border: '1px solid rgba(251,146,60,.3)',
};
export const stDim = {
  ...chipBase,
  background: 'rgba(255,255,255,.06)', color: color.textDim, border: `1px solid ${line.mid}`,
};

// Filter chips (chipOn / chipOff)
export const chipOn = {
  fontFamily: font.mono, fontSize: 10,
  background: 'rgba(215,244,82,.12)', color: color.lime,
  border: '1px solid rgba(215,244,82,.4)',
  padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
};
export const chipOff = {
  fontFamily: font.mono, fontSize: 10,
  border: `1px solid ${line.mid}`, color: color.textDim,
  padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
};

// Panels
export const panel = {
  background: color.surface,
  border: `1px solid ${line.hair}`,
  borderRadius: 16,
};

// Form field label + inputs
export const fieldLbl = {
  fontFamily: font.mono, fontSize: 9, letterSpacing: '1.6px',
  color: color.textMuted, marginBottom: 6,
};
export const inputSt = {
  width: '100%', background: color.bgPanel,
  border: `1px solid ${line.soft}`, borderRadius: 10,
  padding: '9px 12px', color: color.text,
  fontFamily: font.body, fontSize: 12.5, outline: 'none',
};
export const areaSt = { ...inputSt, resize: 'vertical', lineHeight: 1.5 };

// Section eyebrow (mono, letterspaced)
export const eyebrow = {
  fontFamily: font.mono, fontSize: 9.5, letterSpacing: '1.8px',
  color: color.textMuted, marginBottom: 8,
};

// Primary lime CTA
export const ctaLime = {
  display: 'flex', alignItems: 'center', gap: 8,
  background: color.lime, color: color.limeInk,
  fontWeight: 800, fontSize: 13, borderRadius: 10,
  padding: '10px 16px', cursor: 'pointer', border: 'none',
};

// Avatar
export const avatar = (size, grad, fontSize) => ({
  width: size, height: size, flex: 'none', borderRadius: '50%',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontWeight: 800, fontSize, background: grad.bg, color: grad.ink,
});

export const segOn = {
  fontSize: 12, fontWeight: 800, background: color.lime, color: color.limeInk,
  borderRadius: 8, padding: '6px 14px', cursor: 'pointer',
};
export const segOff = {
  fontSize: 12, fontWeight: 700, color: color.textDim,
  padding: '6px 14px', cursor: 'pointer',
};
