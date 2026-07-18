import Hoverable from './Hoverable';
import { color, line, font } from '../styles/tokens';
import { stActive, stWarn, stDim, chipOn, chipOff, panel, fieldLbl, inputSt, selectSt, areaSt, pillStyle, borderHoverOff, borderHoverLime } from '../styles/mixins';

export const toneStyle = { active: stActive, warn: stWarn, dim: stDim };

/** Status pill: ACTIVE / PENDING / DRAFT etc. */
export const StatusChip = ({ tone = 'dim', children, style }) => (
  <span style={{ ...toneStyle[tone], ...style }}>{children}</span>
);

/** Mono eyebrow label above a section. */
export const Eyebrow = ({ children, size = 9.5, spacing = '1.8px', style }) => (
  <div
    style={{
      fontFamily: font.mono, fontSize: size, letterSpacing: spacing,
      color: color.textMuted, ...style,
    }}
  >
    {children}
  </div>
);

/** Card surface used across pages. */
export const Panel = ({ children, style, ...rest }) => (
  <div style={{ ...panel, ...style }} {...rest}>
    {children}
  </div>
);

/** Filter/selection chip with on/off state. */
export const Chip = ({ on, onClick, children, style }) => (
  <Hoverable
    as="span"
    style={{ ...(on ? chipOn : chipOff), ...style }}
    hover={{ borderColor: on ? borderHoverLime : borderHoverOff }}
    onClick={onClick}
  >
    {children}
  </Hoverable>
);

/** Named pill (character picker etc.) — accent: lime | pink | purple */
export const SelectPill = ({ on, onClick, children, accent = 'lime', style }) => {
  const { base, hover } = pillStyle({ on, accent });
  return (
    <Hoverable as="span" style={{ ...base, ...style }} hover={hover} onClick={onClick}>
      {children}
    </Hoverable>
  );
};

/** Section heading in the display face. */
export const PageTitle = ({ children, size = 20, style }) => (
  <div
    style={{
      fontFamily: font.display, fontWeight: 600, fontSize: size,
      letterSpacing: size > 22 ? '-.5px' : undefined, ...style,
    }}
  >
    {children}
  </div>
);

/** Primary lime action. */
export const LimeButton = ({ children, onClick, style }) => (
  <Hoverable
    style={{
      display: 'flex', alignItems: 'center', gap: 8,
      background: color.lime, color: color.limeInk,
      fontWeight: 800, fontSize: 13, borderRadius: 10,
      padding: '10px 16px', cursor: 'pointer', ...style,
    }}
    hover={{ background: color.limeHi }}
    onClick={onClick}
  >
    {children}
  </Hoverable>
);

/** Back link ("← Section"). */
export const BackLink = ({ onClick, children }) => (
  <Hoverable
    style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      fontSize: 12.5, fontWeight: 700, color: color.textDim,
      cursor: 'pointer', marginBottom: 14,
    }}
    hover={{ color: color.text }}
    onClick={onClick}
  >
    ← {children}
  </Hoverable>
);

/** Icon in a rounded tinted box. */
export const IconBox = ({ size = 40, iconSize = 19, tint, children, style }) => (
  <div
    style={{
      width: size, height: size, flex: 'none',
      borderRadius: size >= 40 ? 12 : 11,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      ...tint, ...style,
    }}
  >
    <span style={{ display: 'flex', width: iconSize, height: iconSize }}>{children}</span>
  </div>
);

/** Circular initial avatar. */
export const Avatar = ({ size = 32, grad, children, style }) => (
  <div
    style={{
      width: size, height: size, flex: 'none', borderRadius: '50%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 800, fontSize: size <= 32 ? 13 : 14,
      background: grad.bg, color: grad.ink, position: 'relative', ...style,
    }}
  >
    {children}
  </div>
);

/** Labelled text field. */
export const Field = ({ label, value, placeholder, type = 'text', area, rows = 2, onChange, style, readOnly }) => (
  <div style={{ display: 'flex', flexDirection: 'column', ...style }}>
    {label && <div style={fieldLbl}>{label}</div>}
    {area ? (
      <textarea
        rows={rows}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={onChange}
        style={{ ...areaSt, fontFamily: font.body }}
      />
    ) : (
      <input
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={onChange}
        readOnly={readOnly}
        style={{ ...inputSt, ...(readOnly ? { opacity: 0.7, cursor: 'default' } : {}) }}
      />
    )}
  </div>
);

/** Fake select control (design shows a static dropdown affordance). */
export const SelectBox = ({ label, value, style }) => (
  <div style={{ display: 'flex', flexDirection: 'column', ...style }}>
    {label && <div style={fieldLbl}>{label}</div>}
    <Hoverable
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: color.bgPanel, border: `1px solid ${line.soft}`,
        borderRadius: 10, padding: '9px 12px', cursor: 'pointer', fontSize: 12.5,
      }}
      hover={{ borderColor: 'rgba(215,244,82,.4)' }}
    >
      {value}
      <span style={{ color: color.textMuted }}>▾</span>
    </Hoverable>
  </div>
);

/** Pill toggle knob. */
export const Toggle = ({ on }) => (
  <div
    style={{
      width: 38, height: 22, borderRadius: 12, flex: 'none', position: 'relative',
      cursor: 'pointer', background: on ? color.lime : 'rgba(255,255,255,.15)',
    }}
  >
    <div
      style={{
        width: 18, height: 18, borderRadius: '50%', position: 'absolute', top: 2,
        ...(on ? { right: 2, background: color.limeInk } : { left: 2, background: color.bgPanel }),
      }}
    />
  </div>
);

/** Square checkbox used in operator rights/model access. */
export const Checkbox = ({ on }) => (
  <div
    style={{
      width: 20, height: 20, flex: 'none', borderRadius: 6,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      cursor: 'pointer', fontSize: 12, fontWeight: 900,
      ...(on
        ? { background: color.lime, color: color.limeInk }
        : { border: '1.5px solid rgba(255,255,255,.2)', color: 'transparent' }),
    }}
  >
    ✓
  </div>
);

/** Info note block (blue-tinted). */
export const NoteBlock = ({ children, style }) => (
  <div
    style={{
      background: 'rgba(56,189,248,.06)', border: '1px solid rgba(56,189,248,.2)',
      borderRadius: 10, padding: '10px 12px', fontSize: 11,
      color: color.textMid, lineHeight: 1.55, ...style,
    }}
  >
    {children}
  </div>
);

/** Modal overlay shared by lightbox and media dialogs. */
export const Overlay = ({ onClose, children, z = 60 }) => (
  <div
    onClick={onClose}
    style={{
      position: 'fixed', inset: 0, background: 'rgba(6,7,9,.86)',
      zIndex: z, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
    }}
  >
    {children}
  </div>
);

/** Close button used in overlays. */
export const CloseButton = ({ onClick, label }) => (
  <Hoverable
    style={{
      display: 'flex', alignItems: 'center', gap: 6,
      border: `1px solid ${line.strong}`, borderRadius: 9,
      padding: '7px 12px', fontSize: 12, fontWeight: 700,
      color: color.textDim, cursor: 'pointer',
    }}
    hover={{ color: color.text, borderColor: borderHoverOff }}
    onClick={onClick}
  >
    ✕ {label}
  </Hoverable>
);

/** Fades a page in, matching the prototype's mmFade animation. */
export const Fade = ({ children, style, ...rest }) => (
  <div style={{ animation: 'mmFade .25s ease', ...style }} {...rest}>
    {children}
  </div>
);
