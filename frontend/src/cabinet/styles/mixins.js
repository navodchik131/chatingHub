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
  boxSizing: 'border-box',
};
export const chipOff = {
  fontFamily: font.mono, fontSize: 10,
  border: `1px solid ${line.strong}`, color: color.textDim,
  padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
  boxSizing: 'border-box',
};

/** Subtle hover border — не белая вспышка line.hover (.3) */
export const borderHoverOff = line.strong;
export const borderHoverLime = 'rgba(215,244,82,.55)';
export const borderHoverPink = 'rgba(240,168,200,.55)';
export const borderHoverGreen = 'rgba(74,222,128,.65)';

const pillAccents = {
  lime: {
    bg: 'rgba(215,244,82,.12)', border: 'rgba(215,244,82,.45)', color: color.lime,
    hoverOn: borderHoverLime, hoverOff: borderHoverOff,
  },
  pink: {
    bg: 'rgba(240,168,200,.12)', border: 'rgba(240,168,200,.4)', color: color.pink,
    hoverOn: borderHoverPink, hoverOff: borderHoverOff,
  },
  purple: {
    bg: 'rgba(192,132,252,.08)', border: 'rgba(192,132,252,.45)', color: color.purple,
    hoverOn: 'rgba(192,132,252,.55)', hoverOff: borderHoverOff,
  },
};

/** Character / model name pill — единая обводка и hover без скачка. */
export function pillStyle({ on, accent = 'lime' }) {
  const a = pillAccents[accent] || pillAccents.lime;
  return {
    base: on
      ? {
          fontSize: 12, fontWeight: 800, background: a.bg, color: a.color,
          border: `1px solid ${a.border}`, padding: '6px 14px', borderRadius: 9,
          cursor: 'pointer', boxSizing: 'border-box',
        }
      : {
          fontSize: 12, fontWeight: 700, color: color.textDim,
          border: `1px solid ${line.strong}`, padding: '6px 14px', borderRadius: 9,
          cursor: 'pointer', boxSizing: 'border-box',
        },
    hover: { borderColor: on ? a.hoverOn : a.hoverOff },
  };
}

/** AI model / card picker in studio sidebar. */
export function cardPickStyle(on) {
  return {
    base: {
      flex: 1, minWidth: 130, borderRadius: 11, padding: '10px 12px', cursor: 'pointer',
      boxSizing: 'border-box',
      ...(on
        ? { background: 'rgba(215,244,82,.08)', border: '1px solid rgba(215,244,82,.45)' }
        : { background: color.bgPanel, border: `1px solid ${line.strong}` }),
    },
    hover: { borderColor: on ? borderHoverLime : borderHoverOff },
  };
}

/** Mode tile on Images page. */
export function modeCardStyle(on) {
  return {
    base: {
      borderRadius: 16, padding: '14px 16px', cursor: 'pointer', boxSizing: 'border-box',
      ...(on
        ? { background: 'rgba(215,244,82,.07)', border: '1px solid rgba(215,244,82,.45)' }
        : { background: color.surface, border: `1px solid ${line.hair}` }),
    },
    hover: { borderColor: on ? borderHoverLime : borderHoverOff },
  };
}

/** Archive thumb in reference slot — всегда 2px, без смены толщины. */
export function refThumbStyle(picked) {
  return {
    base: {
      aspectRatio: '3/4', borderRadius: 7, cursor: 'pointer', boxSizing: 'border-box',
      border: `2px solid ${picked ? color.lime : 'transparent'}`,
    },
    hover: { borderColor: picked ? borderHoverLime : 'rgba(215,244,82,.35)' },
  };
}

/** Upload drop zone for reference — 2px border, зелёный hover если файл уже есть. */
export function refUploadStyle(hasFile) {
  return {
    base: {
      boxSizing: 'border-box',
      border: `2px ${hasFile ? 'solid' : 'dashed'} ${hasFile ? 'rgba(74,222,128,.5)' : line.dashed}`,
    },
    hover: { borderColor: hasFile ? borderHoverGreen : 'rgba(215,244,82,.4)' },
  };
}

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
export const selectSt = {
  ...inputSt,
  padding: '10px 12px',
  cursor: 'pointer',
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
  boxSizing: 'border-box', border: '1px solid transparent',
};
export const segOff = {
  fontSize: 12, fontWeight: 700, color: color.textDim,
  padding: '6px 14px', cursor: 'pointer',
  boxSizing: 'border-box', border: `1px solid ${line.strong}`,
};
