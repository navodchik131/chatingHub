import { useEffect, useMemo, useRef, useState } from 'react';

import { color, line } from '../styles/tokens';
import { apiFetch } from '../../api';
import Hoverable from './Hoverable';

function fmtTime(sec) {
  const n = Number(sec);
  if (!Number.isFinite(n) || n < 0) return '0:00';
  const m = Math.floor(n / 60);
  const s = n - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, '0')}`;
}

function isDirectMediaUrl(src) {
  const value = String(src || '').trim();
  if (!value) return false;
  return value.startsWith('blob:') || value.startsWith('http') || value.startsWith('data:');
}

function batchSegments(duration, cuts) {
  const dur = Number(duration) || 0;
  const pts = [0, ...cuts.filter((t) => t > 0 && t < dur).sort((a, b) => a - b), dur];
  const segs = [];
  for (let i = 0; i < pts.length - 1; i += 1) {
    segs.push({
      id: i + 1,
      tStart: pts[i],
      tEnd: pts[i + 1],
      duration: pts[i + 1] - pts[i],
    });
  }
  return segs;
}

const PALETTE = ['#D7F452', '#38BDF8', '#C084FC', '#FB923C', '#F472B6', '#4ADE80', '#FACC15'];

export default function BatchCutTimeline({
  videoSrc,
  durationHint = 0,
  cuts,
  onCutsChange,
  minBatchSec = 0.4,
  softMaxBatchSec = 4,
  lang = 'ru',
  disabled = false,
}) {
  const t = (ru, en) => (lang === 'ru' ? ru : en);
  const videoRef = useRef(null);
  const trackRef = useRef(null);
  const [resolvedSrc, setResolvedSrc] = useState(() => (isDirectMediaUrl(videoSrc) ? videoSrc : null));
  const [duration, setDuration] = useState(Number(durationHint) || 0);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [dragIdx, setDragIdx] = useState(null);
  const [selectedIdx, setSelectedIdx] = useState(null);

  useEffect(() => {
    if (!videoSrc) {
      setResolvedSrc(null);
      return undefined;
    }
    if (isDirectMediaUrl(videoSrc)) {
      setResolvedSrc(videoSrc);
      return undefined;
    }
    let cancelled = false;
    let objectUrl = null;
    void (async () => {
      try {
        const res = await apiFetch(videoSrc);
        if (!res.ok || cancelled) return;
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setResolvedSrc(objectUrl);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [videoSrc]);

  useEffect(() => {
    if (Number(durationHint) > 0 && !(duration > 0)) {
      setDuration(Number(durationHint));
    }
  }, [durationHint, duration]);

  const sortedCuts = useMemo(
    () => [...(cuts || [])].map(Number).filter((x) => Number.isFinite(x)).sort((a, b) => a - b),
    [cuts],
  );
  const segments = useMemo(
    () => batchSegments(duration, sortedCuts),
    [duration, sortedCuts],
  );

  const setCutsSafe = (next) => {
    if (disabled) return;
    const dur = duration || Number(durationHint) || 0;
    const eps = Math.max(0.05, minBatchSec * 0.25);
    const cleaned = [...next]
      .map(Number)
      .filter((x) => Number.isFinite(x) && x > eps && (!dur || x < dur - eps))
      .sort((a, b) => a - b)
      .filter((x, i, arr) => i === 0 || Math.abs(x - arr[i - 1]) > eps);
    onCutsChange(cleaned);
  };

  const timeFromClientX = (clientX) => {
    const el = trackRef.current;
    if (!el || !(duration > 0)) return 0;
    const rect = el.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return ratio * duration;
  };

  const seekTo = (sec) => {
    const v = videoRef.current;
    if (!v) return;
    const next = Math.min(Math.max(0, sec), duration || v.duration || 0);
    v.currentTime = next;
    setCurrentTime(next);
  };

  const addCutAtPlayhead = () => {
    if (!(duration > 0)) return;
    setCutsSafe([...sortedCuts, currentTime]);
  };

  const removeSelected = () => {
    if (selectedIdx == null) return;
    setCutsSafe(sortedCuts.filter((_, i) => i !== selectedIdx));
    setSelectedIdx(null);
  };

  const clearCuts = () => {
    setCutsSafe([]);
    setSelectedIdx(null);
  };

  useEffect(() => {
    if (dragIdx == null) return undefined;
    const onMove = (e) => {
      const tSec = timeFromClientX(e.clientX);
      const next = sortedCuts.map((c, i) => (i === dragIdx ? tSec : c));
      setCutsSafe(next);
      seekTo(tSec);
    };
    const onUp = () => setDragIdx(null);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [dragIdx, sortedCuts, duration, disabled]);

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div
        style={{
          borderRadius: 12,
          overflow: 'hidden',
          border: `1px solid ${line.soft}`,
          background: '#000',
          maxHeight: 360,
        }}
      >
        {resolvedSrc ? (
          <video
            ref={videoRef}
            src={resolvedSrc}
            style={{ width: '100%', maxHeight: 360, display: 'block', background: '#000' }}
            preload="metadata"
            onLoadedMetadata={(e) => {
              const d = Number(e.currentTarget.duration) || 0;
              if (d > 0) setDuration(d);
            }}
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime || 0)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            controls
          />
        ) : (
          <div style={{ padding: 40, textAlign: 'center', color: color.textMuted, fontSize: 13 }}>
            {t('Загрузка видео…', 'Loading video…')}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <Hoverable
          style={chipStyle(false)}
          hover={{ filter: 'brightness(1.06)' }}
          onClick={() => {
            const v = videoRef.current;
            if (!v) return;
            if (v.paused) void v.play();
            else v.pause();
          }}
        >
          {playing ? t('Пауза', 'Pause') : t('Play', 'Play')}
        </Hoverable>
        <Hoverable
          style={chipStyle(disabled)}
          hover={{ filter: disabled ? 'none' : 'brightness(1.06)' }}
          onClick={disabled ? undefined : addCutAtPlayhead}
        >
          {t('Точка здесь', 'Cut here')} · {fmtTime(currentTime)}
        </Hoverable>
        <Hoverable
          style={chipStyle(disabled || selectedIdx == null)}
          hover={{ filter: disabled || selectedIdx == null ? 'none' : 'brightness(1.06)' }}
          onClick={disabled || selectedIdx == null ? undefined : removeSelected}
        >
          {t('Удалить точку', 'Remove cut')}
        </Hoverable>
        <Hoverable
          style={chipStyle(disabled || sortedCuts.length === 0)}
          hover={{ filter: disabled || !sortedCuts.length ? 'none' : 'brightness(1.06)' }}
          onClick={disabled || !sortedCuts.length ? undefined : clearCuts}
        >
          {t('Очистить', 'Clear')}
        </Hoverable>
        <div style={{ fontSize: 12, color: color.textDim, marginLeft: 'auto' }}>
          {fmtTime(currentTime)} / {fmtTime(duration)} · {segments.length}{' '}
          {t('батч(ей)', 'batch(es)')}
        </div>
      </div>

      <div
        ref={trackRef}
        role="slider"
        aria-valuemin={0}
        aria-valuemax={duration || 0}
        aria-valuenow={currentTime}
        onPointerDown={(e) => {
          if (disabled || !(duration > 0)) return;
          const tSec = timeFromClientX(e.clientX);
          seekTo(tSec);
        }}
        style={{
          position: 'relative',
          height: 44,
          borderRadius: 10,
          border: `1px solid ${line.soft}`,
          background: color.surface,
          cursor: disabled ? 'default' : 'pointer',
          overflow: 'hidden',
          userSelect: 'none',
        }}
      >
        {segments.map((seg, i) => {
          const left = duration > 0 ? (seg.tStart / duration) * 100 : 0;
          const width = duration > 0 ? (seg.duration / duration) * 100 : 0;
          const warnShort = seg.duration + 1e-6 < softMaxBatchSec;
          const warnLong = softMaxBatchSec > 0 && seg.duration > softMaxBatchSec + 0.05;
          return (
            <div
              key={`seg-${seg.id}`}
              title={`Batch ${seg.id}: ${fmtTime(seg.tStart)}–${fmtTime(seg.tEnd)} (${seg.duration.toFixed(2)}s)`}
              style={{
                position: 'absolute',
                left: `${left}%`,
                width: `${width}%`,
                top: 0,
                bottom: 0,
                background: PALETTE[i % PALETTE.length],
                opacity: warnShort || warnLong ? 0.45 : 0.7,
                borderRight: i < segments.length - 1 ? `1px solid ${color.bg}` : 'none',
              }}
            />
          );
        })}
        {duration > 0 && (
          <div
            style={{
              position: 'absolute',
              left: `${(currentTime / duration) * 100}%`,
              top: 0,
              bottom: 0,
              width: 2,
              background: color.text,
              transform: 'translateX(-1px)',
              pointerEvents: 'none',
              zIndex: 3,
            }}
          />
        )}
        {sortedCuts.map((cut, i) => (
          <div
            key={`cut-${i}-${cut}`}
            title={`${t('Разрез', 'Cut')} ${fmtTime(cut)}`}
            onPointerDown={(e) => {
              if (disabled) return;
              e.stopPropagation();
              e.preventDefault();
              setSelectedIdx(i);
              setDragIdx(i);
            }}
            onDoubleClick={(e) => {
              if (disabled) return;
              e.stopPropagation();
              setCutsSafe(sortedCuts.filter((_, j) => j !== i));
              setSelectedIdx(null);
            }}
            style={{
              position: 'absolute',
              left: `${duration > 0 ? (cut / duration) * 100 : 0}%`,
              top: 0,
              bottom: 0,
              width: 10,
              transform: 'translateX(-5px)',
              cursor: disabled ? 'default' : 'ew-resize',
              zIndex: 4,
            }}
          >
            <div
              style={{
                position: 'absolute',
                left: 4,
                top: 0,
                bottom: 0,
                width: 2,
                background: selectedIdx === i ? color.limeHi : '#fff',
                boxShadow: '0 0 0 1px rgba(0,0,0,0.45)',
              }}
            />
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        {segments.map((seg) => {
          const short = seg.duration + 1e-6 < softMaxBatchSec;
          const long = softMaxBatchSec > 0 && seg.duration > softMaxBatchSec + 0.05;
          return (
            <div
              key={`row-${seg.id}`}
              style={{
                display: 'flex',
                gap: 10,
                alignItems: 'center',
                fontSize: 12.5,
                color: color.textMid,
              }}
            >
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 3,
                  background: PALETTE[(seg.id - 1) % PALETTE.length],
                  flexShrink: 0,
                }}
              />
              <strong style={{ color: color.text }}>Batch {seg.id}</strong>
              <span>
                {fmtTime(seg.tStart)} → {fmtTime(seg.tEnd)}
              </span>
              <span style={{ color: color.textDim }}>{seg.duration.toFixed(2)}s</span>
              {short && (
                <span style={{ color: color.orange }}>
                  {t('<4с → Seedance дотянет до 4с', '<4s → Seedance pads to 4s')}
                </span>
              )}
              {long && (
                <span style={{ color: color.orange }}>
                  {t(`длиннее ${softMaxBatchSec}с`, `over ${softMaxBatchSec}s`)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ fontSize: 12, color: color.textDim, lineHeight: 1.45 }}>
        {t(
          'Кликни таймлайн чтобы перемотать. «Точка здесь» — разрез на текущем кадре. Перетащи маркер; двойной клик — удалить.',
          'Click timeline to scrub. “Cut here” adds a marker at the playhead. Drag markers; double-click to remove.',
        )}
      </div>
    </div>
  );
}

function chipStyle(disabled) {
  return {
    background: color.bgPanel,
    color: color.text,
    fontWeight: 700,
    fontSize: 12,
    borderRadius: 8,
    padding: '7px 11px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1,
    border: `1px solid ${line.soft}`,
  };
}
