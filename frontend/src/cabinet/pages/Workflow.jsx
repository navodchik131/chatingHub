import Hoverable from '../components/Hoverable';
import { IcoFlow } from '../components/Icons';
import { Fade, PageTitle } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';

export default function Workflow() {
  const { t, lang } = useApp();

  return (
    <Fade style={{ height: '100%', display: 'flex', flexDirection: 'column' }} data-screen-label="Workflow">
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 5 }}>
          <PageTitle>Workflow</PageTitle>
          <span
            style={{
              fontFamily: font.mono, fontSize: 9, letterSpacing: '1px',
              background: 'rgba(215,244,82,.12)', color: color.lime,
              border: '1px solid rgba(215,244,82,.3)', padding: '2px 8px', borderRadius: 20,
            }}
          >
            PRO
          </span>
        </div>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.workflowBody}</div>
      </div>

      <div
        style={{
          flex: 1, minHeight: 300, border: `1.5px dashed ${line.strong}`, borderRadius: 18,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 16, background: 'radial-gradient(circle at 50% 40%,rgba(192,132,252,.06),transparent 70%)',
        }}
      >
        <div
          style={{
            width: 64, height: 64, borderRadius: 20, background: 'rgba(192,132,252,.12)',
            color: color.purple, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <span style={{ display: 'flex', width: 30, height: 30 }}><IcoFlow /></span>
        </div>

        <div style={{ textAlign: 'center', maxWidth: 440 }}>
          <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 18, marginBottom: 8 }}>{t.workflowTitle}</div>
          <div style={{ fontSize: 12.5, color: color.textDim, lineHeight: 1.6 }}>{t.workflowBody}</div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <div
            style={{
              background: 'rgba(255,255,255,.06)', border: `1px solid ${line.mid}`,
              borderRadius: 10, padding: '9px 16px', fontSize: 12.5, fontWeight: 700, color: color.textDim,
            }}
          >
            {t.workflowSoon}
          </div>
          <Hoverable
            style={{
              background: 'linear-gradient(120deg,#C084FC,#F0A8C8)', borderRadius: 10,
              padding: '9px 16px', fontSize: 12.5, fontWeight: 800, color: color.purpleInk, cursor: 'pointer',
            }}
            hover={{ filter: 'brightness(1.08)' }}
            onClick={() => { window.location.href = '/workspace/workflow'; }}
          >
            {lang === 'ru' ? 'Открыть Workflow' : 'Open Workflow'}
          </Hoverable>
        </div>
      </div>
    </Fade>
  );
}
