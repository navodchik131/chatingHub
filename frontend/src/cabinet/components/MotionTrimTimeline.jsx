import { useCallback, useEffect, useRef, useState } from 'react';
import Hoverable from './Hoverable';
import { color, line, font } from '../styles/tokens';

/** Формат секунд m:ss.d */
function fmtSec(sec) {
  const s = Math.max(0, Number(sec) || 0);
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${m}:${r.toFixed(1).padStart(m > 0 ? 4 : 3, '0')}`;
}

const MIN_CLIP = 0.25;

/**
 * Trim UI: превью видео + filmstrip + перетаскиваемые ручки in/out.
 */
export default function MotionTrimTimeline({
  videoSrc,
  durationSec,
  trimIn,
  trimOut,
  onTrimIn,
  onTrimOut,
  lang = 'ru',
}) {
  const videoRef = useRef(null);
  const filmRef = useRef(null);
  const [loadedDur, setLoadedDur] = useState(Number(durationSec) || 0);
  const [frames, setFrames] = useState([]);
  const [dragging, setDragging] = useState(null);
  const [previewLoop, setPreviewLoop] = useState(false);

  const total = Math.max(MIN_CLIP, loadedDur || Number(durationSec) || 5);
  const start = Math.max(0, Math.min(trimIn, trimOut - MIN_CLIP));
  const end = Math.min(total, Math.max(trimOut, start + MIN_CLIP));
  const genLen = Math.max(MIN_CLIP, end - start);

  const timeFromClientX = useCallback((clientX) => {
    const el = filmRef.current;
    if (!el || !(total > 0)) return 0;
    const rect = el.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.round(ratio * total * 10) / 10;
  }, [total]);

  // Загрузка filmstrip-кадров из видео
  useEffect(() => {
    if (!videoSrc) {
      setFrames([]);
      return undefined;
    }
    let cancelled = false;
    const v = document.createElement('video');
    v.preload = 'auto';
    v.muted = true;
    v.playsInline = true;
    v.crossOrigin = 'anonymous';
    v.src = videoSrc;

    const capture = async () => {
      await new Promise((resolve, reject) => {
        v.onloadedmetadata = () => resolve();
        v.onerror = () => reject(new Error('video load failed'));
      });
      if (cancelled) return;
      const dur = Number(v.duration) || Number(durationSec) || 0;
      if (dur > 0) setLoadedDur(dur);
      const n = Math.min(12, Math.max(6, Math.ceil(dur / 1.2)));
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      canvas.width = 80;
      canvas.height = 120;
      const thumbs = [];
      for (let i = 0; i < n; i += 1) {
        const t = dur > 0 ? (dur * i) / Math.max(1, n - 1) : 0;
        await new Promise((resolve) => {
          const onSeek = () => {
            v.removeEventListener('seeked', onSeek);
            resolve();
          };
          v.addEventListener('seeked', onSeek);
          try {
            v.currentTime = Math.min(t, Math.max(0, dur - 0.05));
          } catch {
            resolve();
          }
        });
        if (cancelled) return;
        ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
        thumbs.push(canvas.toDataURL('image/jpeg', 0.55));
      }
      if (!cancelled) setFrames(thumbs);
    };

    void capture().catch(() => {});
    return () => {
      cancelled = true;
      v.src = '';
    };
  }, [videoSrc, durationSec]);

  useEffect(() => {
    if (Number(durationSec) > 0) setLoadedDur(Number(durationSec));
  }, [durationSec]);

  // Перетаскивание ручек in/out
  useEffect(() => {
    if (!dragging) return undefined;
    const onMove = (e) => {
      const t = timeFromClientX(e.clientX);
      if (dragging === 'in') {
        onTrimIn(Math.max(0, Math.min(t, end - MIN_CLIP)));
      } else {
        onTrimOut(Math.min(total, Math.max(t, start + MIN_CLIP)));
      }
    };
    const onUp = () => setDragging(null);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [dragging, end, start, total, timeFromClientX, onTrimIn, onTrimOut]);

  // Loop preview selected segment
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !previewLoop) return undefined;
    const onTime = () => {
      if (v.currentTime >= end - 0.05) {
        v.currentTime = start;
        void v.play().catch(() => {});
      }
    };
    v.addEventListener('timeupdate', onTime);
    return () => v.removeEventListener('timeupdate', onTime);
  }, [previewLoop, start, end]);

  const seekTo = (sec) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.min(Math.max(0, sec), total);
  };

  const togglePreviewSegment = () => {
    const v = videoRef.current;
    if (!v) return;
    if (previewLoop) {
      setPreviewLoop(false);
      v.pause();
      return;
    }
    v.currentTime = start;
    setPreviewLoop(true);
    void v.play().catch(() => {});
  };

  const handleStyle = (edge) => ({
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 14,
    transform: 'translateX(-7px)',
    cursor: 'ew-resize',
    zIndex: 5,
    left: edge === 'in' ? `${(start / total) * 100}%` : `${(end / total) * 100}%`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  });

  return (
    <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${line.hair}` }}>
      <div style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1.4, color: color.textGhost, marginBottom: 10 }}>
        {lang === 'ru' ? 'ОТРЕЗОК ДЛЯ ГЕНЕРАЦИИ' : 'CLIP FOR GENERATION'}
      </div>

      {videoSrc ? (
        <div
          style={{
            borderRadius: 12,
            overflow: 'hidden',
            border: `1px solid ${line.soft}`,
            background: '#000',
            marginBottom: 10,
            maxHeight: 280,
          }}
        >
          <video
            ref={videoRef}
            src={videoSrc}
            style={{ width: '100%', maxHeight: 280, display: 'block' }}
            preload="metadata"
            controls
            onLoadedMetadata={(e) => {
              const d = Number(e.currentTarget.duration) || 0;
              if (d > 0) setLoadedDur(d);
            }}
          />
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10, alignItems: 'center' }}>
        <Hoverable
          style={{
            fontSize: 11,
            fontWeight: 700,
            borderRadius: 8,
            padding: '7px 12px',
            cursor: videoSrc ? 'pointer' : 'not-allowed',
            opacity: videoSrc ? 1 : 0.5,
            background: previewLoop ? 'rgba(215,244,82,.15)' : color.bgPanel,
            border: `1px solid ${previewLoop ? 'rgba(215,244,82,.45)' : line.soft}`,
            color: previewLoop ? color.lime : color.textDim,
          }}
          hover={videoSrc ? { filter: 'brightness(1.06)' } : {}}
          onClick={videoSrc ? togglePreviewSegment : undefined}
        >
          {previewLoop
            ? (lang === 'ru' ? 'Стоп превью' : 'Stop preview')
            : (lang === 'ru' ? '▶ Превью отрезка' : '▶ Preview clip')}
        </Hoverable>
        <Hoverable
          style={{
            fontSize: 11,
            fontWeight: 700,
            borderRadius: 8,
            padding: '7px 12px',
            cursor: 'pointer',
            background: color.bgPanel,
            border: `1px solid ${line.soft}`,
            color: color.textDim,
          }}
          hover={{ filter: 'brightness(1.06)' }}
          onClick={() => seekTo(start)}
        >
          {lang === 'ru' ? 'К началу' : 'To start'}
        </Hoverable>
        <div style={{ marginLeft: 'auto', fontFamily: font.mono, fontSize: 10, color: color.textDim }}>
          {fmtSec(start)} – {fmtSec(end)} · {genLen.toFixed(2)}s
        </div>
      </div>

      <div
        ref={filmRef}
        style={{
          position: 'relative',
          height: 64,
          borderRadius: 12,
          overflow: 'hidden',
          background: '#0F1013',
          boxShadow: `inset 0 0 0 1px ${line.strong}`,
          userSelect: 'none',
        }}
      >
        <div style={{ position: 'absolute', inset: 0, display: 'flex' }}>
          {(frames.length ? frames : [null]).map((src, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                minWidth: 0,
                height: '100%',
                background: src ? `center/cover url(${src})` : 'rgba(255,255,255,.04)',
                opacity: 0.85,
              }}
            />
          ))}
        </div>

        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: 0,
            width: `${(start / total) * 100}%`,
            background: 'rgba(10,11,13,.72)',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            right: 0,
            width: `${((total - end) / total) * 100}%`,
            background: 'rgba(10,11,13,.72)',
            pointerEvents: 'none',
          }}
        />

        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${(start / total) * 100}%`,
            width: `${((end - start) / total) * 100}%`,
            boxShadow: 'inset 0 0 0 2px #D7F452',
            borderRadius: 4,
            pointerEvents: 'none',
          }}
        />

        <div
          role="presentation"
          style={handleStyle('in')}
          onPointerDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragging('in');
            setPreviewLoop(false);
          }}
        >
          <div style={{ width: 4, height: '70%', borderRadius: 3, background: color.lime, boxShadow: '0 0 6px rgba(215,244,82,.5)' }} />
        </div>
        <div
          role="presentation"
          style={handleStyle('out')}
          onPointerDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragging('out');
            setPreviewLoop(false);
          }}
        >
          <div style={{ width: 4, height: '70%', borderRadius: 3, background: color.lime, boxShadow: '0 0 6px rgba(215,244,82,.5)' }} />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap', marginTop: 10 }}>
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

      <div style={{ fontSize: 10.5, color: color.textDim, lineHeight: 1.45, marginTop: 8 }}>
        {lang === 'ru'
          ? 'Потяните жёлтые ручки по краям выделения. В Seedance уйдёт цветной фрагмент без силуэтной обработки.'
          : 'Drag the yellow handles. The color clip is sent to Seedance without silhouette processing.'}
      </div>
    </div>
  );
}
