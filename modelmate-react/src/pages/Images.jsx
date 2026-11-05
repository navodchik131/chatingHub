import Hoverable from '../components/Hoverable';
import {
  IcoLayers, IcoFace, IcoShirt, IcoPin, IcoText, IcoGrid2,
  IcoSpark, IcoUpload, IcoImage, IcoZoom, IcoDownload,
} from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip, Overlay, CloseButton } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { modeDefs } from '../data/catalog';
import { modelsByMode, ratios, countOptions, charNames } from '../data/mock';

const modeIcons = {
  layers: IcoLayers, face: IcoFace, shirt: IcoShirt, pin: IcoPin, text: IcoText, grid2: IcoGrid2,
};

/** Archive lightbox — shared by the Images page. */
export function Lightbox() {
  const { t, lang, lightbox, setS } = useApp();
  if (lightbox == null) return null;

  const close = () => setS({ lightbox: null });
  const who = lightbox % 3 === 0 ? 'Ruby' : 'Mia';

  return (
    <Overlay onClose={close}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ display: 'flex', flexDirection: 'column', gap: 14, maxHeight: '92vh', maxWidth: 'min(92vw,720px)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15 }}>{who}</div>
            <div style={{ fontSize: 11, color: color.textDim }}>
              {lang === 'ru' ? 'Кадр по промпту' : 'From prompt'} · 9:16 · 12.07 · 14:2{lightbox}
            </div>
          </div>
          <CloseButton onClick={close} label={t.close} />
        </div>

        <div
          style={{
            flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 14, overflow: 'hidden', background: G[lightbox % 6],
          }}
        >
          <span style={{ display: 'flex', width: 48, height: 48, color: 'rgba(255,255,255,.25)' }}><IcoImage /></span>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <Hoverable
            style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              background: color.lime, color: color.limeInk, borderRadius: 11,
              padding: 12, fontSize: 13, fontWeight: 800, cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
          >
            <span style={{ display: 'flex', width: 16, height: 16 }}><IcoDownload /></span>
            {t.download}
          </Hoverable>
          <Hoverable
            style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              background: 'rgba(192,132,252,.12)', border: '1px solid rgba(192,132,252,.4)',
              color: color.purple, borderRadius: 11, padding: 12, fontSize: 13, fontWeight: 800, cursor: 'pointer',
            }}
            hover={{ background: 'rgba(192,132,252,.2)' }}
          >
            <span style={{ display: 'flex', width: 16, height: 16 }}><IcoGrid2 /></span>
            {t.makeCarousel}
          </Hoverable>
        </div>
      </div>
    </Overlay>
  );
}

/** Upload / archive source picker for one slot. */
function Slot({ slot, index }) {
  const { t, s, setS } = useApp();
  const key = `${s.imgMode}:${index}`;
  const src = s.slotSource[key] || 'upload';

  const seg = (on) => ({
    flex: 1, textAlign: 'center', fontFamily: font.mono, fontSize: 9,
    letterSpacing: '.5px', padding: '4px 8px', borderRadius: 6, cursor: 'pointer',
    ...(on ? { background: color.lime, color: color.limeInk, fontWeight: 800 } : { color: color.textDim }),
  });

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div
        style={{
          fontSize: 10.5, fontWeight: 700, color: color.textMid, height: 30,
          lineHeight: 1.3, display: 'flex', alignItems: 'flex-start', overflow: 'hidden',
        }}
      >
        {slot.label}
      </div>

      {slot.archive ? (
        <div style={{ display: 'flex', gap: 3, background: color.bgPanel, border: `1px solid ${line.soft}`, borderRadius: 8, padding: 3 }}>
          <div style={seg(src === 'upload')} onClick={() => setS({ slotSource: { ...s.slotSource, [key]: 'upload' } })}>
            {t.srcUpload}
          </div>
          <div style={seg(src === 'archive')} onClick={() => setS({ slotSource: { ...s.slotSource, [key]: 'archive' } })}>
            {t.srcArchive}
          </div>
        </div>
      ) : (
        <div style={{ height: 32, flex: 'none' }} />
      )}

      {src === 'archive' ? (
        <div
          style={{
            aspectRatio: '3/4', border: '1px solid rgba(215,244,82,.3)', borderRadius: 12,
            background: 'rgba(215,244,82,.04)', display: 'grid', gridTemplateColumns: '1fr 1fr',
            gap: 5, padding: 7, overflowY: 'auto',
          }}
        >
          {[0, 1, 2, 3].map((i) => (
            <Hoverable
              key={i}
              style={{ aspectRatio: '3/4', borderRadius: 7, border: '2px solid transparent', cursor: 'pointer', background: G[i % 6] }}
              hover={{ borderColor: color.lime }}
            />
          ))}
        </div>
      ) : (
        <Hoverable
          style={{
            aspectRatio: '3/4', border: `1.5px dashed ${line.dashed}`, borderRadius: 12,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 6, cursor: 'pointer',
          }}
          hover={{ borderColor: 'rgba(215,244,82,.5)', background: 'rgba(215,244,82,.03)' }}
        >
          <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
          <span style={{ fontSize: 10, fontWeight: 700, color: color.textDim, textAlign: 'center', padding: '0 8px' }}>
            {t.srcUpload}
          </span>
        </Hoverable>
      )}
    </div>
  );
}

export default function Images() {
  const { t, lang, s, setS, isMobile } = useApp();

  const modes = modeDefs(lang, t.cr);
  const curMode = modes.find((m) => m.id === s.imgMode) || modes[0];
  const models = modelsByMode(lang)[s.contentMode];

  const studioGrid = isMobile
    ? { display: 'grid', gridTemplateColumns: '1fr', gap: 14 }
    : { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 16, alignItems: 'start' };

  // Demo validation: clicking Generate without filling anything.
  const imgErrList = [];
  if (curMode.slots.length) imgErrList.push(t.errNoRef);
  if (curMode.id === 'prompt') imgErrList.push(t.errNoPrompt);
  imgErrList.push(t.errNoChar);

  const cmSeg = (on, tone) => ({
    flex: 1, textAlign: 'center', fontSize: 12, fontWeight: 800,
    borderRadius: 8, padding: '8px 10px', cursor: 'pointer',
    ...(on ? tone : { color: color.textDim }),
  });

  return (
    <Fade data-screen-label="Студия — Картинки">
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>{t.navImages}</PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.imagesDesc}</div>
      </div>

      {/* mode cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginBottom: 18 }}>
        {modes.map((m) => {
          const on = s.imgMode === m.id;
          const Icon = modeIcons[m.icon];
          return (
            <Hoverable
              key={m.id}
              style={{
                borderRadius: 16, padding: '14px 16px', cursor: 'pointer',
                ...(on
                  ? { background: 'rgba(215,244,82,.07)', border: '1px solid rgba(215,244,82,.45)' }
                  : { background: color.surface, border: `1px solid ${line.hair}` }),
              }}
              hover={{ borderColor: 'rgba(215,244,82,.5)' }}
              onClick={() => setS({ imgMode: m.id })}
              aria-pressed={on}
            >
              <div
                style={{
                  width: 36, height: 36, borderRadius: 11, display: 'flex',
                  alignItems: 'center', justifyContent: 'center', marginBottom: 10,
                  ...(on
                    ? { background: 'rgba(215,244,82,.15)', color: color.lime }
                    : { background: 'rgba(255,255,255,.06)', color: color.textDim }),
                }}
              >
                <span style={{ display: 'flex', width: 18, height: 18 }}><Icon /></span>
              </div>
              <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 4 }}>{m.title}</div>
              <div style={{ fontSize: 11, color: color.textDim, lineHeight: 1.45, marginBottom: 8 }}>{m.desc}</div>
              <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.lime }}>{m.cost}</div>
            </Hoverable>
          );
        })}
      </div>

      <div style={studioGrid}>
        {/* form */}
        <div
          style={{
            background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
            padding: 18, display: 'flex', flexDirection: 'column', gap: 16, height: 'fit-content',
          }}
        >
          <div>
            <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 3 }}>{curMode.title}</div>
            <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5 }}>{curMode.longDesc}</div>
          </div>

          {/* content type */}
          <div>
            <Eyebrow>{t.contentType}</Eyebrow>
            <div style={{ display: 'flex', gap: 6, background: color.bgPanel, border: `1px solid ${line.soft}`, borderRadius: 11, padding: 4 }}>
              <div
                style={cmSeg(s.contentMode === 'sfw', { background: color.green, color: color.greenInk })}
                onClick={() => setS({ contentMode: 'sfw', aiModel: 'nano' })}
              >
                SFW · {lang === 'ru' ? 'обычный' : 'safe'}
              </div>
              <div
                style={cmSeg(s.contentMode === 'nsfw', { background: color.pink, color: '#2A0A1C' })}
                onClick={() => setS({ contentMode: 'nsfw', aiModel: 'seedream' })}
              >
                NSFW · 18+
              </div>
            </div>
          </div>

          {/* AI model */}
          <div>
            <Eyebrow>{t.aiModel}</Eyebrow>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {models.map((m) => {
                const on = s.aiModel === m.id;
                return (
                  <Hoverable
                    key={m.id}
                    style={{
                      flex: 1, minWidth: 130, borderRadius: 11, padding: '10px 12px', cursor: 'pointer',
                      ...(on
                        ? { background: 'rgba(215,244,82,.08)', border: '1px solid rgba(215,244,82,.45)' }
                        : { background: color.bgPanel, border: `1px solid ${line.soft}` }),
                    }}
                    hover={{ borderColor: line.hover }}
                    onClick={() => setS({ aiModel: m.id })}
                    aria-pressed={on}
                  >
                    <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 2, ...(on ? { color: color.lime } : {}) }}>
                      {m.name}
                    </div>
                    <div style={{ fontSize: 10, color: color.textDim }}>{m.note}</div>
                  </Hoverable>
                );
              })}
            </div>
          </div>

          {/* slots */}
          {curMode.slots.length > 0 && (
            <div style={{ display: 'flex', gap: 10, alignItems: 'stretch' }}>
              {curMode.slots.map((sl, i) => (
                <Slot key={i} slot={sl} index={i} />
              ))}
            </div>
          )}

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

          {/* format */}
          <div>
            <Eyebrow>{t.format}</Eyebrow>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {ratios.map((r, i) => (
                <Chip key={r} on={i === 0}>{r}</Chip>
              ))}
            </div>
          </div>

          {/* frame count (carousel only) */}
          {curMode.showCount && (
            <div>
              <Eyebrow>{t.frames}</Eyebrow>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {countOptions.map((n) => (
                  <Chip key={n} on={s.carouselCount === n} onClick={() => setS({ carouselCount: n })}>
                    {n}
                  </Chip>
                ))}
              </div>
            </div>
          )}

          {/* prompt */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <Eyebrow style={{ marginBottom: 0 }}>{t.prompt}</Eyebrow>
              <span style={{ fontSize: 10.5, color: color.textGhost }}>{t.optional}</span>
            </div>
            <textarea
              rows={3}
              placeholder={curMode.promptHint}
              aria-label={t.prompt}
              style={{
                width: '100%', background: color.bgPanel, border: `1px solid ${line.soft}`,
                borderRadius: 10, padding: '10px 12px', color: color.text,
                fontFamily: font.body, fontSize: 12.5, resize: 'vertical', outline: 'none',
              }}
            />
          </div>

          {/* validation */}
          {s.showGenError && (
            <div
              role="alert"
              style={{
                background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.35)',
                borderRadius: 12, padding: '12px 14px',
              }}
            >
              <div style={{ fontWeight: 800, fontSize: 12, color: color.red, marginBottom: 7 }}>⚠ {t.errImgTitle}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {imgErrList.map((er) => (
                  <div key={er} style={{ fontSize: 11.5, color: color.pink, display: 'flex', gap: 7, alignItems: 'center' }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', background: color.red, flex: 'none' }} />
                    {er}
                  </div>
                ))}
              </div>
            </div>
          )}

          <Hoverable
            style={{
              display: 'flex', alignItems: 'center', gap: 12, background: color.lime,
              borderRadius: 12, padding: '12px 16px', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
            onClick={() => setS({ showGenError: true })}
          >
            <span style={{ display: 'flex', width: 17, height: 17, color: color.limeInk }}><IcoSpark /></span>
            <span style={{ flex: 1, fontWeight: 800, fontSize: 14, color: color.limeInk }}>{t.generate}</span>
            <span style={{ fontFamily: font.mono, fontSize: 11, fontWeight: 600, color: color.limeInkSoft }}>{curMode.cost}</span>
          </Hoverable>
        </div>

        {/* archive */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{t.archive}</span>
            <span
              style={{
                fontSize: 10.5, color: color.orange, background: 'rgba(251,146,60,.08)',
                border: '1px solid rgba(251,146,60,.25)', borderRadius: 8, padding: '4px 10px',
              }}
            >
              ⏳ {t.retention}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(130px,1fr))', gap: 10 }}>
            {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
              <Hoverable
                key={i}
                style={{
                  borderRadius: 12, overflow: 'hidden', background: color.surface,
                  border: `1px solid ${line.hair}`, cursor: 'pointer',
                }}
                hover={{ borderColor: 'rgba(215,244,82,.4)' }}
                onClick={() => setS({ lightbox: i })}
              >
                <div
                  style={{
                    aspectRatio: '9/16', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', position: 'relative', background: G[i % 6],
                  }}
                >
                  <span style={{ display: 'flex', width: 22, height: 22, color: 'rgba(255,255,255,.35)' }}><IcoImage /></span>
                  <span
                    style={{
                      position: 'absolute', top: 7, right: 7, display: 'flex', width: 15, height: 15,
                      color: 'rgba(255,255,255,.7)', background: 'rgba(0,0,0,.4)', borderRadius: 6, padding: 3,
                    }}
                  >
                    <IcoZoom />
                  </span>
                </div>
                <div style={{ padding: '8px 10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{ fontWeight: 700, fontSize: 11 }}>{i % 3 === 0 ? 'Ruby' : 'Mia'}</span>
                    <span style={{ fontFamily: font.mono, fontSize: 8.5, color: color.textGhost }}>9:16</span>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, color: color.purple, cursor: 'pointer' }}>→ {t.toVideo}</span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}>↓</span>
                  </div>
                </div>
              </Hoverable>
            ))}
          </div>
        </div>
      </div>
    </Fade>
  );
}
