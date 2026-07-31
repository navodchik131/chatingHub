import { color } from '../styles/tokens';

const VIDEO_NOTE_SIZE = 200;

export function ChatMessageMedia({
  url,
  mime,
  kind,
  onMediaLoaded,
}) {
  if (!url) return null;

  const isVideoNote = kind === 'video_note';
  const isVideo = isVideoNote || String(mime || '').startsWith('video/');

  if (isVideo) {
    return (
      <video
        src={url}
        autoPlay
        loop
        muted
        playsInline
        onLoadedData={onMediaLoaded}
        style={{
          display: 'block',
          width: isVideoNote ? VIDEO_NOTE_SIZE : '100%',
          height: isVideoNote ? VIDEO_NOTE_SIZE : undefined,
          maxWidth: isVideoNote ? VIDEO_NOTE_SIZE : 240,
          maxHeight: isVideoNote ? VIDEO_NOTE_SIZE : 280,
          borderRadius: isVideoNote ? '50%' : 10,
          objectFit: 'cover',
          background: color.bgPanel,
        }}
      />
    );
  }

  return (
    <img
      src={url}
      alt=""
      onLoad={onMediaLoaded}
      style={{
        display: 'block',
        width: '100%',
        maxWidth: 240,
        maxHeight: 280,
        borderRadius: 10,
        objectFit: 'cover',
        background: color.bgPanel,
      }}
    />
  );
}
