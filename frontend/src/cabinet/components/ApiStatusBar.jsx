import Hoverable from './Hoverable';
import { color, font } from '../styles/tokens';

export default function ApiStatusBar({ error, busy, onDismiss }) {
  if (!error && !busy) return null;
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 99998,
        maxWidth: 'min(92vw, 520px)',
        padding: '10px 16px',
        fontSize: 12,
        borderRadius: 8,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        boxShadow: '0 8px 28px rgba(0,0,0,.35)',
        ...(busy && !error
          ? {
              background: 'rgba(215,244,82,.15)',
              color: color.lime,
              border: '1px solid rgba(215,244,82,.35)',
              justifyContent: 'center',
            }
          : {
              background: '#b00020',
              color: '#fff',
            }),
      }}
      role={error ? 'alert' : 'status'}
    >
      <span style={{ flex: 1, lineHeight: 1.45 }}>
        {error || 'Загрузка…'}
      </span>
      {error && onDismiss ? (
        <Hoverable
          as="button"
          type="button"
          style={{
            flex: 'none',
            border: 'none',
            background: 'rgba(255,255,255,.14)',
            color: 'inherit',
            width: 24,
            height: 24,
            borderRadius: 7,
            cursor: 'pointer',
            fontFamily: font.body,
          }}
          onClick={onDismiss}
          aria-label="Close"
        >
          ×
        </Hoverable>
      ) : null}
    </div>
  );
}
