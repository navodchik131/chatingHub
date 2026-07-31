import { useEffect, useMemo, useRef, useState } from 'react';
import Hoverable from './Hoverable';
import { IcoPlay, IcoSendArrow, IcoUpload, IcoVideoNote } from './Icons';
import { CloseButton } from './ui';
import { archiveThumbUrl, archiveVideoUrl, isArchivePending } from '../api/actions';
import { videoNoteSendPayload } from '../../studioArchive';
import { color, font, G, line } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';

function fmtDuration(sec) {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  if (s <= 0) return '';
  return `${s}s`;
}

function ArchivePickTile({ item, index, selected, onSelect }) {
  const videoUrl = archiveVideoUrl(item);
  const poster = archiveThumbUrl(item);
  const [duration, setDuration] = useState('');

  return (
    <Hoverable
      style={{
        flex: '0 0 88px',
        width: 88,
        borderRadius: 12,
        overflow: 'hidden',
        border: selected ? '2px solid rgba(192,132,252,.85)' : `1px solid ${line.hair}`,
        boxShadow: selected ? '0 0 0 2px rgba(192,132,252,.2)' : 'none',
        cursor: 'pointer',
        position: 'relative',
        background: poster ? `url(${poster}) center/cover` : G[(index + 1) % G.length],
      }}
      hover={{ borderColor: selected ? 'rgba(192,132,252,.85)' : borderHoverOff }}
      onClick={() => onSelect(item)}
    >
      {videoUrl ? (
        <video
          src={videoUrl}
          muted
          playsInline
          preload="metadata"
          style={{
            position: 'absolute', inset: 0, width: '100%', height: '100%',
            objectFit: 'cover', pointerEvents: 'none',
          }}
          onLoadedMetadata={(e) => {
            const d = e.currentTarget.duration;
            if (Number.isFinite(d) && d > 0) setDuration(fmtDuration(d));
            try { e.currentTarget.currentTime = 0.05; } catch { /* ignore */ }
          }}
        />
      ) : null}
      <div
        style={{
          aspectRatio: '1 / 1',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
        }}
      >
        <span
          style={{
            width: 28, height: 28, borderRadius: '50%',
            background: 'rgba(0,0,0,.45)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', color: '#fff',
          }}
        >
          <span style={{ display: 'flex', width: 12, height: 12, marginLeft: 2 }}><IcoPlay /></span>
        </span>
        {duration ? (
          <span
            style={{
              position: 'absolute', right: 6, bottom: 6, fontFamily: font.mono,
              fontSize: 9, fontWeight: 700, color: '#fff',
              background: 'rgba(0,0,0,.55)', borderRadius: 6, padding: '2px 5px',
            }}
          >
            {duration}
          </span>
        ) : null}
      </div>
    </Hoverable>
  );
}

export default function DialogVideoNoteModal({
  open,
  onClose,
  archiveVideos = [],
  onSendArchive,
  onSendUpload,
  sending = false,
  t,
}) {
  const uploadRef = useRef(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadPreview, setUploadPreview] = useState(null);

  const readyItems = useMemo(
    () => (archiveVideos || []).filter((item) => {
      if (isArchivePending(item)) return false;
      if ((item.status || '').trim() === 'failed') return false;
      if (!archiveVideoUrl(item)) return false;
      return Boolean(videoNoteSendPayload(item));
    }),
    [archiveVideos],
  );

  useEffect(() => {
    if (!open) {
      setSelectedItem(null);
      setUploadFile(null);
      if (uploadPreview) URL.revokeObjectURL(uploadPreview);
      setUploadPreview(null);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  }, [open, uploadPreview]);

  if (!open) return null;

  const canSend = Boolean(selectedItem || uploadFile) && !sending;

  const clearUpload = () => {
    if (uploadPreview) URL.revokeObjectURL(uploadPreview);
    setUploadFile(null);
    setUploadPreview(null);
    if (uploadRef.current) uploadRef.current.value = '';
  };

  const pickUpload = (file) => {
    if (!file) return;
    clearUpload();
    setSelectedItem(null);
    setUploadFile(file);
    if (file.type.startsWith('image/')) {
      setUploadPreview(URL.createObjectURL(file));
    } else if (file.type.startsWith('video/')) {
      setUploadPreview(URL.createObjectURL(file));
    }
  };

  const handleSend = () => {
    if (!canSend) return;
    if (uploadFile) {
      void onSendUpload(uploadFile);
      return;
    }
    if (selectedItem) {
      void onSendArchive(selectedItem);
    }
  };

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      style={{
        position: 'absolute',
        left: 12,
        right: 12,
        bottom: 66,
        zIndex: 7,
        background: color.raised,
        border: '1px solid rgba(192,132,252,.35)',
        borderRadius: 16,
        padding: 14,
        boxShadow: '0 16px 40px rgba(0,0,0,.55)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <span
          style={{
            width: 32, height: 32, borderRadius: 10, flex: 'none',
            background: 'rgba(192,132,252,.14)', border: '1px solid rgba(192,132,252,.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: color.purple,
          }}
        >
          <span style={{ display: 'flex', width: 18, height: 18 }}><IcoVideoNote /></span>
        </span>
        <div style={{ flex: 1, fontWeight: 800, fontSize: 14 }}>{t.dlgVideoNoteTitle}</div>
        <CloseButton onClick={onClose} />
      </div>

      <div
        style={{
          fontFamily: font.mono, fontSize: 9, letterSpacing: '1.2px',
          color: color.textGhost, marginBottom: 8,
        }}
      >
        {t.dlgVideoNoteArchive}
      </div>

      {readyItems.length ? (
        <div
          style={{
            display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4,
            marginBottom: 12, scrollbarWidth: 'thin',
          }}
        >
          {readyItems.slice(0, 12).map((item, i) => (
            <ArchivePickTile
              key={item.id || i}
              item={item}
              index={i}
              selected={selectedItem?.id === item.id && !uploadFile}
              onSelect={(it) => {
                clearUpload();
                setSelectedItem(it);
              }}
            />
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: color.textDim, marginBottom: 12 }}>
          {t.dlgVideoNoteArchiveEmpty}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '4px 0 12px' }}>
        <div style={{ flex: 1, height: 1, background: line.hair }} />
        <span style={{ fontSize: 11, color: color.textGhost }}>{t.dlgVideoNoteOr}</span>
        <div style={{ flex: 1, height: 1, background: line.hair }} />
      </div>

      <input
        ref={uploadRef}
        type="file"
        accept="video/*,image/*"
        style={{ display: 'none' }}
        onChange={(e) => pickUpload(e.target.files?.[0])}
      />

      <Hoverable
        style={{
          border: `1px dashed ${uploadFile ? 'rgba(192,132,252,.55)' : line.mid}`,
          borderRadius: 12,
          padding: '14px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          cursor: 'pointer',
          background: uploadFile ? 'rgba(192,132,252,.06)' : 'rgba(255,255,255,.02)',
          marginBottom: 8,
        }}
        hover={{ borderColor: 'rgba(192,132,252,.45)' }}
        onClick={() => uploadRef.current?.click()}
      >
        {uploadPreview ? (
          uploadFile?.type?.startsWith('video/') ? (
            <video
              src={uploadPreview}
              muted
              playsInline
              style={{ width: 44, height: 44, borderRadius: 10, objectFit: 'cover', flex: 'none' }}
            />
          ) : (
            <img src={uploadPreview} alt="" style={{ width: 44, height: 44, borderRadius: 10, objectFit: 'cover', flex: 'none' }} />
          )
        ) : (
          <span style={{ display: 'flex', width: 20, height: 20, color: color.textDim, flex: 'none' }}><IcoUpload /></span>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            {uploadFile ? uploadFile.name : t.dlgVideoNoteUpload}
          </div>
        </div>
        {uploadFile ? (
          <Hoverable
            as="span"
            style={{ fontSize: 11, color: color.red, fontWeight: 700, cursor: 'pointer' }}
            hover={{ opacity: 0.8 }}
            onClick={(e) => {
              e.stopPropagation();
              clearUpload();
            }}
          >
            ✕
          </Hoverable>
        ) : null}
      </Hoverable>

      <div style={{ fontSize: 11, color: color.textGhost, lineHeight: 1.45, marginBottom: 12 }}>
        {t.dlgVideoNoteUploadHint}
      </div>

      <Hoverable
        style={{
          width: '100%',
          borderRadius: 12,
          padding: '12px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          fontWeight: 800,
          fontSize: 14,
          cursor: canSend ? 'pointer' : 'not-allowed',
          opacity: canSend ? 1 : 0.45,
          background: canSend ? color.surface : color.bgPanel,
          border: `1px solid ${canSend ? line.mid : line.hair}`,
          color: color.text,
        }}
        hover={canSend ? { borderColor: borderHoverOff } : {}}
        onClick={handleSend}
      >
        <span style={{ display: 'flex', width: 16, height: 16, color: color.purple }}><IcoSendArrow /></span>
        {sending ? t.dlgVideoNoteSending : t.vidVideoNoteSend}
      </Hoverable>
    </div>
  );
}
