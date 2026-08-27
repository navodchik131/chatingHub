import { useMemo, useRef } from 'react';
import { color, line, font } from '../styles/tokens';

/** Формат секунд как m:ss.d */
function fmtSec(sec) {
  const s = Math.max(0, Number(sec) || 0);
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${m}:${r.toFixed(1).padStart(m > 0 ? 4 : 3, '0')}`;
}

/**
 * Таймлайн отрезка реф-видео для Motion Control.
 * Клик по дорожке двигает активную границу (in/out).
 */
export default function MotionTrimTimeline({
  durationSec,
  trimIn,
  trimOut,
  activeEdge,
  onTrimIn,
  onTrimOut,
  onActiveEdgeChange,
  lang = 'ru',
}) {
  const trackRef = useRef(null);
  const total = Math.max(0.5, Number(durationSec) || 5);
  const start = Math.max(0, Math.min(trimIn, trimOut - 0.25));
  const end = Math.min(total, Math.max(trimOut, start + 0.25));
  const genLen = Math.max(0.25, end - start);

  const ticks = useMemo(() => {
    const n = Math.min(6, Math.max(3, Math.ceil(total / 3)));
    return Array.from({ length: n + 1 }, (_, i) => {
      const t = (total / n) * i;
      return { t, label: fmtSec(t), left: `${(t / total) * 100}%` };
    });
  }, [total]);

  const seek = (e) => {
    const el = trackRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const t = Math.round(ratio * total * 10) / 10;
    if (activeEdge === 'in') onTrimIn(Math.min(t, end - 0.25));
    else onTrimOut(Math.max(t, start + 0.25));
  };

  const step = (edge, delta) => {
    if (edge === 'in') {
      onTrimIn(Math.max(0, Math.min(end - 0.25, Math.round((start + delta) * 10) / 10)));
    } else {
      onTrimOut(Math.min(total, Math.max(start + 0.25, Math.round((end + delta) * 10) / 10)));
    }
  };

  const edgeBtn = (edge, label) => ({
    flex: 1,
    textAlign: 'center',
    fontSize: 11,
    fontWeight: 800,
    borderRadius: 8,
    padding: '7px 10px',
    cursor: 'pointer',
    border: `1px solid ${activeEdge === edge ? 'rgba(215,244,82,.45)' : line.strong}`,
    ...(activeEdge === edge
      ? { background: 'rgba(215,244,82,.12)', color: color.lime }
      : { color: color.textDim }),
  });

  return (
    <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${line.hair}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 11 }}>
        <div style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1.4, color: color.textGhost }}>
          {lang === 'ru' ? 'ОТРЕЗОК ДЛЯ ГЕНЕРАЦИИ' : 'CLIP FOR GENERATION'}
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 5 }}>
          <div style={edgeBtn('in', 'in')} onClick={() => onActiveEdgeChange('in')}>
            {lang === 'ru' ? 'начало' : 'in'}
          </div>
          <div style={edgeBtn('out', 'out')} onClick={() => onActiveEdgeChange('out')}>
            {lang === 'ru' ? 'конец' : 'out'}
          </div>
        </div>
      </div>

      <div
        ref={trackRef}
        role="presentation"
        onClick={seek}
        style={{
          position: 'relative',
          height: 58,
          borderRadius: 12,
          cursor: 'crosshair',
          background: '#0F1013',
          boxShadow: `inset 0 0 0 1px ${line.strong}`,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: 0,
            width: `${(start / total) * 100}%`,
            background: 'rgba(10,11,13,.66)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            right: 0,
            width: `${((total - end) / total) * 100}%`,
            background: 'rgba(10,11,13,.66)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${(start / total) * 100}%`,
            width: `${((end - start) / total) * 100}%`,
            display: 'flex',
            boxShadow: 'inset 0 0 0 2px #D7F452',
            borderRadius: 6,
          }}
        >
          <div style={{ width: 4, background: color.lime, borderRadius: '4px 0 0 4px' }} />
          <div style={{ flex: 1 }} />
          <div style={{ width: 4, background: color.lime, borderRadius: '0 4px 4px 0' }} />
        </div>
      </div>

      <div style={{ position: 'relative', height: 22, marginTop: 6 }}>
        {ticks.map((t) => (
          <div
            key={t.label}
            style={{
              position: 'absolute',
              left: t.left,
              transform: 'translateX(-50%)',
              fontFamily: font.mono,
              fontSize: 9,
              color: color.textGhost,
            }}
          >
            {t.label}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap', marginTop: 8 }}>
        {[
          { edge: 'in', label: lang === 'ru' ? 'НАЧАЛО' : 'IN', value: start },
          { edge: 'out', label: lang === 'ru' ? 'КОНЕЦ' : 'OUT', value: end },
        ].map((f) => (
          <div
            key={f.edge}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: color.bgPanel,
              border: `1px solid ${line.soft}`,
              borderRadius: 11,
              padding: '6px 10px',
            }}
          >
            <div style={{ fontFamily: font.mono, fontSize: 8.5, letterSpacing: 1.2, color: color.textGhost }}>
              {f.label}
            </div>
            <button type="button" onClick={() => step(f.edge, -0.1)} style={ctrlBtn}>−</button>
            <div style={{ fontFamily: font.mono, fontSize: 11.5, color: color.text, minWidth: 52, textAlign: 'center' }}>
              {fmtSec(f.value)}
            </div>
            <button type="button" onClick={() => step(f.edge, 0.1)} style={ctrlBtn}>+</button>
          </div>
        ))}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'rgba(215,244,82,.08)',
            border: '1px solid rgba(215,244,82,.28)',
            borderRadius: 11,
            padding: '8px 13px',
          }}
        >
          <div style={{ fontFamily: font.mono, fontSize: 8.5, letterSpacing: 1.2, color: 'rgba(215,244,82,.7)' }}>
            {lang === 'ru' ? 'ДЛИНА' : 'LEN'}
          </div>
          <div style={{ fontFamily: font.mono, fontWeight: 700, fontSize: 13, color: color.lime }}>
            {genLen.toFixed(2)} {lang === 'ru' ? 'с' : 's'}
          </div>
        </div>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={() => {
            onTrimIn(0);
            onTrimOut(total);
          }}
          style={{
            border: 'none',
            background: 'none',
            fontFamily: font.mono,
            fontSize: 9.5,
            color: color.textDim,
            cursor: 'pointer',
          }}
        >
          {lang === 'ru' ? 'сбросить' : 'reset'}
        </button>
      </div>
      <div style={{ fontSize: 10.5, color: color.textDim, lineHeight: 1.45, marginTop: 9 }}>
        {lang === 'ru'
          ? `В генерацию уйдёт только этот отрезок: ${fmtSec(start)} – ${fmtSec(end)}. Смета считается по длине клипа.`
          : `Only this segment will be sent: ${fmtSec(start)} – ${fmtSec(end)}. Billing uses clip length.`}
      </div>
    </div>
  );
}

const ctrlBtn = {
  border: 'none',
  background: 'rgba(255,255,255,.06)',
  color: color.textDim,
  borderRadius: 6,
  width: 24,
  height: 24,
  cursor: 'pointer',
  fontWeight: 800,
};
