import { useEffect, useRef, useState } from 'react';
import Hoverable from './Hoverable';
import { IcoDownload, IcoVideoNote, IcoSendArrow, IcoChevronRight, IcoPlay } from './Icons';
import { Overlay, CloseButton } from './ui';
import { color, line, font } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';
import { mapDialogRow } from '../api/mappers';

function aspectCss(ratio) {
  const r = String(ratio || '9:16').trim();
  if (r === '16:9') return '16 / 9';
  if (r === '1:1') return '1 / 1';
  if (r === '4:3') return '4 / 3';
  if (r === '3:4') return '3 / 4';
  return '9 / 16';
}

function fmtDuration(sec) {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  if (s <= 0) return '';
  return `${s}s`;
}

function ActionBtn({
  tone = 'lime',
  icon,
  label,
  hint,
  onClick,
  disabled,
}) {
  const tones = {
    lime: {
      base: {
        background: color.lime,
        color: color.limeInk,
        border: '1px solid transparent',
      },
      hover: { background: color.limeHi },
      hint: { color: color.limeInkSoft, fontFamily: font.mono },
    },
    purple: {
      base: {
        background: 'rgba(192,132,252,.06)',
        color: color.purple,
        border: `1px solid rgba(192,132,252,.45)`,
      },
      hover: { background: 'rgba(192,132,252,.12)', borderColor: 'rgba(192,132,252,.65)' },
      hint: { color: 'rgba(192,132,252,.75)', fontFamily: font.mono },
    },
    cyan: {
      base: {
        background: 'rgba(56,189,248,.06)',
        color: color.blue,
        border: `1px solid rgba(56,189,248,.45)`,
      },
      hover: { background: 'rgba(56,189,248,.12)', borderColor: 'rgba(56,189,248,.65)' },
      hint: { color: 'rgba(56,189,248,.75)' },
    },
  };
  const t = tones[tone] || tones.lime;
  return (
    <Hoverable
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        width: '100%',
        borderRadius: 12,
        padding: '12px 14px',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        boxSizing: 'border-box',
        ...t.base,
      }}
      hover={disabled ? {} : t.hover}
      onClick={disabled ? undefined : onClick}
    >
      <span style={{ display: 'flex', width: 18, height: 18, flex: 'none' }}>{icon}</span>
      <span style={{ flex: 1, fontWeight: 800, fontSize: 13, lineHeight: 1.25 }}>{label}</span>
      {hint ? (
        <span style={{ fontSize: 11, fontWeight: 700, ...t.hint }}>{hint}</span>
      ) : null}
      {tone === 'cyan' ? (
        <span style={{ display: 'flex', width: 14, height: 14, opacity: 0.85 }}>
          <IcoChevronRight />
        </span>
      ) : null}
    </Hoverable>
  );
}

export default function VideoPreviewModal({
  open,
  onClose,
  who,
  metaLine,
  ratio = '9:16',
  videoUrl,
  posterUrl,
  mp4Hint,
  downloadUrl,
  videoNotePath,
  videoNotePayload,
  tgConversations = [],
  onDownloadMp4,
  onDownloadVideoNote,
  onSendVideoNote,
  t,
  lang,
}) {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [durationSec, setDurationSec] = useState(0);
  const [vidNotePick, setVidNotePick] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!open) {
      setPlaying(false);
      setDurationSec(0);
      setVidNotePick(false);
      setSending(false);
    }
  }, [open]);

  if (!open || !videoUrl) return null;

  const canVideoNote = Boolean(videoNotePath);
  const canSend = Boolean(videoNotePayload) && tgConversations.length > 0;
  const durationLabel = fmtDuration(durationSec);

  const sendToConv = async (convId) => {
    if (!convId || !videoNotePayload || sending) return;
    setSending(true);
    try {
      await onSendVideoNote(convId, videoNotePayload);
      setVidNotePick(false);
      onClose?.();
    } finally {
      setSending(false);
    }
  };

  const openSend = () => {
    if (!videoNotePayload || !canSend) return;
    if (tgConversations.length === 1) {
      void sendToConv(tgConversations[0].id);
      return;
    }
    setVidNotePick(true);
  };

  const togglePlay = () => {
    const el = videoRef.current;
    if (!el) return;
    if (el.paused) {
      void el.play().then(() => setPlaying(true)).catch(() => {});
    } else {
      el.pause();
      setPlaying(false);
    }
  };

  return (
    <>
      <Overlay onClose={onClose}>
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            width: 'min(96vw, 440px)',
            maxHeight: '94vh',
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <div style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-.2px' }}>{who || '—'}</div>
              {metaLine ? (
                <div style={{ marginTop: 4, fontSize: 11.5, color: color.textDim }}>{metaLine}</div>
              ) : null}
            </div>
            <CloseButton onClick={onClose} label={t.close} />
          </div>

          <div
            style={{
              position: 'relative',
              width: '100%',
              aspectRatio: aspectCss(ratio),
              maxHeight: 'min(58vh, 520px)',
              borderRadius: 20,
              overflow: 'hidden',
              background: '#000',
              border: `1px solid ${line.hair}`,
            }}
          >
            <video
              ref={videoRef}
              src={videoUrl}
              poster={posterUrl || undefined}
              playsInline
              preload="metadata"
              onLoadedMetadata={(e) => {
                try {
                  const d = e.currentTarget.duration;
                  if (Number.isFinite(d) && d > 0) setDurationSec(d);
                } catch { /* ignore */ }
              }}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setPlaying(false)}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: 'block',
                background: '#000',
              }}
            />
            {!playing ? (
              <button
                type="button"
                onClick={togglePlay}
                aria-label="Play"
                style={{
                  position: 'absolute',
                  inset: 0,
                  border: 'none',
                  background: 'rgba(0,0,0,.28)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <span
                  style={{
                    width: 54,
                    height: 54,
                    borderRadius: '50%',
                    background: 'rgba(0,0,0,.45)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    paddingLeft: 3,
                  }}
                >
                  <span style={{ display: 'flex', width: 18, height: 18 }}><IcoPlay /></span>
                </span>
              </button>
            ) : null}
            {durationLabel ? (
              <div
                style={{
                  position: 'absolute',
                  right: 10,
                  bottom: 10,
                  borderRadius: 8,
                  padding: '4px 8px',
                  background: 'rgba(0,0,0,.55)',
                  fontFamily: font.mono,
                  fontSize: 10,
                  fontWeight: 700,
                  color: '#fff',
                }}
              >
                {durationLabel}
              </div>
            ) : null}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {downloadUrl ? (
              <ActionBtn
                tone="lime"
                icon={<IcoDownload />}
                label={lang === 'ru' ? 'Скачать MP4' : 'Download MP4'}
                hint={mp4Hint || 'MP4'}
                onClick={onDownloadMp4}
              />
            ) : null}
            {canVideoNote ? (
              <ActionBtn
                tone="purple"
                icon={<IcoVideoNote />}
                label={t.vidVideoNoteDownload}
                hint="1:1"
                onClick={onDownloadVideoNote}
              />
            ) : null}
            {videoNotePayload ? (
              <ActionBtn
                tone="cyan"
                icon={<IcoSendArrow />}
                label={t.vidVideoNoteSendLong}
                onClick={openSend}
                disabled={!canSend || sending}
              />
            ) : null}
            {videoNotePayload && !canSend ? (
              <div style={{ fontSize: 11, color: color.textDim, textAlign: 'center' }}>
                {t.vidVideoNoteNoChat}
              </div>
            ) : null}
          </div>

          {canVideoNote ? (
            <div
              style={{
                fontSize: 11,
                lineHeight: 1.55,
                color: color.textDim,
                textAlign: 'center',
                padding: '0 6px 4px',
              }}
            >
              {t.vidVideoNoteHint}
            </div>
          ) : null}
        </div>
      </Overlay>

      {vidNotePick ? (
        <Overlay onClose={() => !sending && setVidNotePick(false)} z={70}>
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(96vw, 420px)',
              maxHeight: '70vh',
              overflow: 'auto',
              background: color.surface,
              borderRadius: 14,
              border: `1px solid ${line.hair}`,
              padding: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
              <div style={{ fontWeight: 800, fontSize: 14 }}>{t.vidVideoNotePick}</div>
              <CloseButton onClick={() => !sending && setVidNotePick(false)} label={t.close} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tgConversations.map((c, i) => {
                const row = mapDialogRow(c, i);
                return (
                  <Hoverable
                    key={c.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 10,
                      padding: '10px 12px',
                      borderRadius: 10,
                      cursor: sending ? 'default' : 'pointer',
                      border: `1px solid ${line.hair}`,
                      opacity: sending ? 0.6 : 1,
                    }}
                    hover={sending ? {} : { borderColor: borderHoverOff, background: color.bgPanel }}
                    onClick={() => void sendToConv(c.id)}
                  >
                    <span style={{ fontWeight: 700, fontSize: 13 }}>{row.name}</span>
                    <span style={{ fontFamily: font.mono, fontSize: 9, color: color.textDim }}>{row.platform}</span>
                  </Hoverable>
                );
              })}
            </div>
          </div>
        </Overlay>
      ) : null}
    </>
  );
}
