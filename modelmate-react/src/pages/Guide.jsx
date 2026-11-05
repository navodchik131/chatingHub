import Hoverable from '../components/Hoverable';
import { IcoPlay } from '../components/Icons';
import { Fade, PageTitle, BackLink, Overlay, CloseButton } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, gGrad } from '../styles/tokens';
import { guideDefs } from '../data/catalog';

/** Full-screen media preview for a guide step. */
export function MediaModal() {
  const { t, lang, mediaStep, setS } = useApp();
  if (mediaStep == null) return null;

  const step = guideDefs(lang)[mediaStep];
  const close = () => setS({ mediaStep: null });

  return (
    <Overlay onClose={close}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 'min(92vw,720px)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 26, height: 26, flex: 'none', borderRadius: 8,
                background: 'linear-gradient(120deg,#C084FC,#F0A8C8)', color: color.purpleInk,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: font.display, fontWeight: 600, fontSize: 13,
              }}
            >
              {mediaStep + 1}
            </div>
            <div style={{ fontWeight: 800, fontSize: 15 }}>{step.title}</div>
          </div>
          <CloseButton onClick={close} label={t.close} />
        </div>

        <div
          style={{
            aspectRatio: '16/9', borderRadius: 14, overflow: 'hidden', position: 'relative',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: gGrad[mediaStep % 5],
          }}
        >
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,.35)' }} />
          <Hoverable
            style={{
              width: 64, height: 64, borderRadius: '50%', background: 'rgba(0,0,0,.55)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              position: 'relative', cursor: 'pointer',
            }}
            hover={{ background: 'rgba(0,0,0,.75)' }}
          >
            <span style={{ display: 'flex', width: 26, height: 26, color: '#fff', marginLeft: 3 }}><IcoPlay /></span>
          </Hoverable>
          <span
            style={{
              position: 'absolute', bottom: 12, left: 14, fontFamily: font.mono,
              fontSize: 9, letterSpacing: '1px', color: 'rgba(255,255,255,.7)',
            }}
          >
            GIF / VIDEO · {t.guidePlaceholder}
          </span>
        </div>

        <div style={{ fontSize: 12.5, color: color.textDim, lineHeight: 1.6 }}>{step.desc}</div>
      </div>
    </Overlay>
  );
}

export default function Guide() {
  const { t, lang, go, setS } = useApp();
  const steps = guideDefs(lang);

  return (
    <Fade style={{ maxWidth: 860 }} data-screen-label="Инструкция">
      <BackLink onClick={go('overview')}>{t.navOverview}</BackLink>
      <PageTitle size={22} style={{ marginBottom: 6 }}>{t.startTitle}</PageTitle>
      <div style={{ fontSize: 13, color: color.textDim, marginBottom: 22, maxWidth: 600, lineHeight: 1.55 }}>
        {t.guideIntro}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {steps.map((g, i) => (
          <div
            key={g.title}
            style={{
              display: 'flex', gap: 16, alignItems: 'stretch', background: color.surface,
              border: `1px solid ${line.hair}`, borderRadius: 16, padding: 16, flexWrap: 'wrap',
            }}
          >
            <Hoverable
              style={{
                width: 200, flex: 'none', aspectRatio: '16/10', borderRadius: 12,
                border: `1px dashed ${line.dashed}`, background: color.bgPanel,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                gap: 6, overflow: 'hidden', position: 'relative', cursor: 'pointer',
              }}
              hover={{ borderColor: 'rgba(215,244,82,.5)' }}
              onClick={() => setS({ mediaStep: i })}
              aria-label={`${g.title} — ${t.guidePlaceholder}`}
            >
              <div style={{ position: 'absolute', inset: 0, opacity: 0.35, background: gGrad[i % 5] }} />
              <div
                style={{
                  width: 38, height: 38, borderRadius: '50%', background: 'rgba(0,0,0,.5)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
                }}
              >
                <span style={{ display: 'flex', width: 16, height: 16, color: '#fff', marginLeft: 2 }}><IcoPlay /></span>
              </div>
              <span style={{ fontFamily: font.mono, fontSize: 8.5, letterSpacing: '1px', color: color.textFaint, position: 'relative' }}>
                GIF / VIDEO
              </span>
            </Hoverable>

            <div style={{ flex: 1, minWidth: 220, display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <div
                  style={{
                    width: 28, height: 28, flex: 'none', borderRadius: 9,
                    background: 'linear-gradient(120deg,#C084FC,#F0A8C8)', color: color.purpleInk,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: font.display, fontWeight: 600, fontSize: 14,
                  }}
                >
                  {i + 1}
                </div>
                <div style={{ fontWeight: 800, fontSize: 15 }}>{g.title}</div>
              </div>
              <div style={{ fontSize: 12.5, color: color.textDim, lineHeight: 1.6, marginBottom: 12 }}>{g.desc}</div>
              <Hoverable
                style={{
                  alignSelf: 'flex-start', marginTop: 'auto', display: 'flex', alignItems: 'center',
                  gap: 7, fontSize: 12, fontWeight: 800, color: color.lime, cursor: 'pointer',
                }}
                hover={{ color: color.limeHi }}
                onClick={go(g.page)}
              >
                {g.cta} →
              </Hoverable>
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 16, background: 'rgba(215,244,82,.06)', border: '1px solid rgba(215,244,82,.2)',
          borderRadius: 12, padding: '14px 16px', fontSize: 12, color: color.textMid, lineHeight: 1.55,
        }}
      >
        {t.guideOutro} <a href="#wiki">Wiki →</a>
      </div>
    </Fade>
  );
}
