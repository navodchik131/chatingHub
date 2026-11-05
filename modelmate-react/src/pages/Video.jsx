import { useEffect, useRef } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoFilm, IcoSpark, IcoUpload, IcoPlay } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { charNames } from '../data/mock';

export default function Video() {
  const { t, lang, s, setS, isMobile } = useApp();
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const genFirstFrame = () => {
    setS({ ffState: 'loading' });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setS({ ffState: 'done' }), 2200);
  };

  const studioGrid = isMobile
    ? { display: 'grid', gridTemplateColumns: '1fr', gap: 14 }
    : { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 16, alignItems: 'start' };

  const ffSeg = (on) => ({
    flex: 1, textAlign: 'center', fontSize: 12.5, fontWeight: 800,
    borderRadius: 9, padding: 9, cursor: 'pointer',
    ...(on ? { background: color.lime, color: color.limeInk } : { border: `1px solid ${line.mid}`, color: color.textDim }),
  });

  const vidCost = (s.vidQuality === '4k' ? 80 : s.vidQuality === '1080' ? 40 : 25) * (s.vidTime === '10' ? 2 : 1);
  const ffImgStyle = { width: 70, aspectRatio: '9/16', borderRadius: 10, flex: 'none', background: G[3] };

  const qualityOpts = [{ l: '720p', v: '720' }, { l: '1080p', v: '1080' }, { l: '4K', v: '4k' }];
  const vfmtOpts = ['9:16', '16:9', '1:1'];
  const vtimeOpts = [
    { l: lang === 'ru' ? '5 с' : '5s', v: '5' },
    { l: lang === 'ru' ? '10 с' : '10s', v: '10' },
  ];

  return (
    <Fade data-screen-label="Студия — Видео">
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>{t.navVideo}</PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.videoDesc}</div>
      </div>

      <div style={studioGrid}>
        {/* form */}
        <div
          style={{
            background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
            padding: 18, display: 'flex', flexDirection: 'column', gap: 16, height: 'fit-content',
          }}
        >
          {/* character */}
          <div>
            <Eyebrow>{t.character}</Eyebrow>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {charNames.map((name, i) => (
                <Hoverable
                  as="span"
                  key={name}
                  style={
                    i === 0
                      ? {
                          fontSize: 12, fontWeight: 800, background: 'rgba(240,168,200,.12)',
                          color: color.pink, border: '1px solid rgba(240,168,200,.4)',
                          padding: '6px 14px', borderRadius: 9, cursor: 'pointer',
                        }
                      : {
                          fontSize: 12, fontWeight: 700, border: `1px solid ${line.mid}`,
                          color: color.textDim, padding: '6px 14px', borderRadius: 9, cursor: 'pointer',
                        }
                  }
                  hover={{ borderColor: line.hover }}
                >
                  {name}
                </Hoverable>
              ))}
            </div>
          </div>

          <div>
            <Eyebrow size={9} spacing="1.4px" style={{ marginBottom: 7 }}>{t.format}</Eyebrow>
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {vfmtOpts.map((v) => (
                <Chip key={v} on={s.vidFormat === v} onClick={() => setS({ vidFormat: v })}>{v}</Chip>
              ))}
            </div>
          </div>

          {/* reference video */}
          <div>
            <Eyebrow>{t.refVideo}</Eyebrow>
            <Hoverable
              style={{
                border: `1.5px dashed ${line.dashed}`, borderRadius: 12, padding: 20,
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, cursor: 'pointer',
              }}
              hover={{ borderColor: 'rgba(215,244,82,.5)', background: 'rgba(215,244,82,.03)' }}
            >
              <span style={{ display: 'flex', width: 22, height: 22, color: color.textMuted }}><IcoFilm /></span>
              <span style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, textAlign: 'center' }}>{t.dropVideo}</span>
            </Hoverable>
          </div>

          {/* has first frame? */}
          <div>
            <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>{t.hasFirstFrame}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={ffSeg(s.hasFirstFrame === 'yes')} onClick={() => setS({ hasFirstFrame: 'yes' })}>
                {lang === 'ru' ? 'Да, есть' : 'Yes, I have'}
              </div>
              <div style={ffSeg(s.hasFirstFrame === 'no')} onClick={() => setS({ hasFirstFrame: 'no' })}>
                {lang === 'ru' ? 'Нет — сгенерировать' : 'No — generate it'}
              </div>
            </div>
          </div>

          {/* upload first frame */}
          {s.hasFirstFrame === 'yes' && (
            <div>
              <Eyebrow>{t.sourceFrame}</Eyebrow>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Hoverable
                  style={{
                    flex: 1, border: `1.5px dashed ${line.dashed}`, borderRadius: 12, padding: '16px 12px',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer',
                  }}
                  hover={{ borderColor: 'rgba(215,244,82,.5)', background: 'rgba(215,244,82,.03)' }}
                >
                  <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: color.textDim, textAlign: 'center' }}>{t.uploadFirst}</span>
                </Hoverable>
              </div>
              <div style={{ fontSize: 10.5, color: color.textGhost, marginTop: 6 }}>{t.pickFromArchive}</div>
            </div>
          )}

          {/* generate first frame */}
          {s.hasFirstFrame === 'no' && (
            <div>
              {s.ffState === 'idle' && (
                <Hoverable
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(192,132,252,.1)',
                    border: '1px solid rgba(192,132,252,.35)', borderRadius: 12, padding: '12px 16px', cursor: 'pointer',
                  }}
                  hover={{ background: 'rgba(192,132,252,.18)' }}
                  onClick={genFirstFrame}
                >
                  <span style={{ display: 'flex', width: 17, height: 17, color: color.purple }}><IcoSpark /></span>
                  <span style={{ flex: 1, fontWeight: 800, fontSize: 13, color: color.purple }}>{t.genFirstFrame}</span>
                  <span style={{ fontFamily: font.mono, fontSize: 11, color: color.purple }}>−10 {t.cr}</span>
                </Hoverable>
              )}

              {s.ffState === 'loading' && (
                <div
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14, background: color.bgPanel,
                    border: '1px solid rgba(192,132,252,.3)', borderRadius: 12, padding: '14px 16px',
                  }}
                >
                  <div
                    style={{
                      ...ffImgStyle, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      animation: 'mmPulse 1.2s ease-in-out infinite',
                    }}
                  >
                    <div
                      style={{
                        width: 22, height: 22, borderRadius: '50%',
                        border: '2.5px solid rgba(192,132,252,.25)', borderTopColor: color.purple,
                        animation: 'mmSpin .8s linear infinite',
                      }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 800, fontSize: 13, color: color.purple, marginBottom: 3 }}>{t.genFirstFrame2}</div>
                    <div style={{ fontSize: 11, color: color.textDim }}>Seedream 5 Pro · ~15 c</div>
                  </div>
                </div>
              )}

              {s.ffState === 'done' && (
                <div
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14, background: color.bgPanel,
                    border: '1px solid rgba(74,222,128,.3)', borderRadius: 12, padding: '14px 16px',
                  }}
                >
                  <div style={{ ...ffImgStyle, display: 'flex', alignItems: 'flex-end', padding: 6 }}>
                    <span
                      style={{
                        fontFamily: font.mono, fontSize: 7.5, background: 'rgba(0,0,0,.6)',
                        color: '#fff', padding: '2px 6px', borderRadius: 4,
                      }}
                    >
                      Mia · 9:16
                    </span>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 800, fontSize: 13, color: color.green, marginBottom: 6 }}>✓ {t.ffDone}</div>
                    <Hoverable
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        fontSize: 11.5, fontWeight: 700, color: color.purple, cursor: 'pointer',
                      }}
                      hover={{ color: color.purpleHi }}
                      onClick={genFirstFrame}
                    >
                      ↻ {t.regen}
                    </Hoverable>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* motion prompt */}
          <div>
            <Eyebrow>{t.motionPrompt}</Eyebrow>
            <textarea
              rows={2}
              placeholder={t.motionHint}
              aria-label={t.motionPrompt}
              style={{
                width: '100%', background: color.bgPanel, border: `1px solid ${line.soft}`,
                borderRadius: 10, padding: '10px 12px', color: color.text,
                fontFamily: font.body, fontSize: 12.5, resize: 'vertical', outline: 'none',
              }}
            />
          </div>

          {/* quality / duration */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <Eyebrow size={9} spacing="1.4px" style={{ marginBottom: 7 }}>{t.vidQuality}</Eyebrow>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {qualityOpts.map((q) => (
                  <Chip key={q.v} on={s.vidQuality === q.v} onClick={() => setS({ vidQuality: q.v })}>{q.l}</Chip>
                ))}
              </div>
            </div>
            <div>
              <Eyebrow size={9} spacing="1.4px" style={{ marginBottom: 7 }}>{t.duration}</Eyebrow>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {vtimeOpts.map((v) => (
                  <Chip key={v.v} on={s.vidTime === v.v} onClick={() => setS({ vidTime: v.v })}>{v.l}</Chip>
                ))}
              </div>
            </div>
          </div>

          <Hoverable
            style={{
              display: 'flex', alignItems: 'center', gap: 12, background: color.lime,
              borderRadius: 12, padding: '12px 16px', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
          >
            <span style={{ display: 'flex', width: 17, height: 17, color: color.limeInk }}><IcoFilm /></span>
            <span style={{ flex: 1, fontWeight: 800, fontSize: 14, color: color.limeInk }}>{t.generateVideo}</span>
            <span style={{ fontFamily: font.mono, fontSize: 11, fontWeight: 600, color: color.limeInkSoft }}>
              −{vidCost} {t.cr}
            </span>
          </Hoverable>
        </div>

        {/* archive */}
        <div>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 10 }}>{t.archive}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10 }}>
            {[0, 1, 2, 3].map((i) => (
              <Hoverable
                key={i}
                style={{
                  borderRadius: 12, overflow: 'hidden', background: color.surface,
                  border: `1px solid ${line.hair}`, cursor: 'pointer',
                }}
                hover={{ borderColor: 'rgba(255,255,255,.2)' }}
              >
                <div
                  style={{
                    aspectRatio: '9/16', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    position: 'relative', background: G[(i + 2) % 6],
                  }}
                >
                  <div
                    style={{
                      width: 36, height: 36, borderRadius: '50%', background: 'rgba(0,0,0,.45)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    <span style={{ display: 'flex', width: 14, height: 14, color: '#fff', marginLeft: 2 }}><IcoPlay /></span>
                  </div>
                  <span
                    style={{
                      position: 'absolute', bottom: 8, right: 8, fontFamily: font.mono, fontSize: 9,
                      background: 'rgba(0,0,0,.55)', color: '#fff', padding: '2px 6px', borderRadius: 5,
                    }}
                  >
                    {i % 2 ? '10s' : '5s'}
                  </span>
                </div>
                <div style={{ padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontSize: 11 }}>{i % 2 ? 'Ruby' : 'Mia'}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}>↓ MP4</span>
                </div>
              </Hoverable>
            ))}
          </div>
        </div>
      </div>
    </Fade>
  );
}
