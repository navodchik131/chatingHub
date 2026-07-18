import { useRef } from 'react';
import Hoverable from '../components/Hoverable';
import {
  IcoLayers, IcoFace, IcoShirt, IcoPin, IcoText, IcoGrid2,
  IcoSpark, IcoUpload, IcoImage, IcoZoom, IcoDownload,
} from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip, SelectPill, Overlay, CloseButton } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { cardPickStyle, modeCardStyle, refThumbStyle, refUploadStyle, borderHoverOff } from '../styles/mixins';
import { modeDefs } from '../data/catalog';
import { resolveSlotSource, archiveThumbUrl, archiveDownloadUrl, isArchivePending } from '../api/actions';
import { validateStudioForm, syncRefArchivePicks, enginesForNsfw, sameStudioModelId } from '../api/studioHelpers';

const ratios = ['9:16', '16:9', '1:1', '4:3', '3:4'];
const countOptions = [2, 3, 4, 6, 8];

const modeIcons = {
  layers: IcoLayers, face: IcoFace, shirt: IcoShirt, pin: IcoPin, text: IcoText, grid2: IcoGrid2,
};

/** Archive lightbox — shared by the Images page. */
export function Lightbox() {
  const { t, lang, lightbox, setS, go, cabinet } = useApp();
  if (lightbox == null) return null;

  const item = typeof lightbox === 'object'
    ? lightbox
    : (cabinet.archiveImages || []).find((x) => x.id === lightbox)
      ?? (cabinet.archiveImages || [])[lightbox];
  const close = () => setS({ lightbox: null });
  const model = item ? cabinet.models.find((m) => m.id === item.studio_model_id) : null;
  const thumb = item ? archiveThumbUrl(item) : '';
  const downloadUrl = item ? archiveDownloadUrl(item) || thumb : '';
  const who = model?.name || '—';
  const when = item?.created_at
    ? new Date(item.created_at).toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-GB')
    : '—';

  const handleDownload = () => {
    if (!downloadUrl) return;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `modelmate-${item?.id || 'frame'}.jpg`;
    a.target = '_blank';
    a.rel = 'noreferrer';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleCarousel = () => {
    if (!item?.id) return;
    cabinet.setSlotArchivePicks((prev) => ({ ...prev, 'carousel:0': item.id }));
    setS({ lightbox: null, imgMode: 'carousel', slotSource: { 'carousel:0': 'archive' } });
    go('images')();
  };

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
              {item?.prompt || (lang === 'ru' ? 'Кадр студии' : 'Studio frame')} · {item?.aspect_ratio || '9:16'} · {when}
            </div>
          </div>
          <CloseButton onClick={close} label={t.close} />
        </div>

        <div
          style={{
            flex: 1, minHeight: 280, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 14, overflow: 'hidden',
            background: thumb ? `center/contain no-repeat url(${thumb}) ${color.bgPanel}` : G[(item?.id || 0) % 6],
          }}
        >
          {!thumb && (
            <span style={{ display: 'flex', width: 48, height: 48, color: 'rgba(255,255,255,.25)' }}><IcoImage /></span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <Hoverable
            style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              background: color.lime, color: color.limeInk, borderRadius: 11,
              padding: 12, fontSize: 13, fontWeight: 800, cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
            onClick={handleDownload}
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
            onClick={handleCarousel}
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
  const { t, s, setS, cabinet } = useApp();
  const fileRef = useRef(null);
  const mode = s.imgMode;
  const key = `${mode}:${index}`;
  const src = s.slotSource?.[key] || 'upload';
  const { uploadKey, archiveId } = resolveSlotSource(mode, index, cabinet.uploadFiles, cabinet.slotArchivePicks);
  const hasFile = Boolean(cabinet.uploadFiles[uploadKey]);
  const previewUrl = cabinet.uploadPreviewUrls?.[uploadKey] || '';
  const archiveItems = (cabinet.archiveImages || []).slice(0, 12);

  const seg = (on) => ({
    flex: 1, textAlign: 'center', fontFamily: font.mono, fontSize: 9,
    letterSpacing: '.5px', padding: '4px 8px', borderRadius: 6, cursor: 'pointer',
    boxSizing: 'border-box', border: '1px solid transparent',
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
          {[0, 1, 2, 3].map((i) => {
            const item = archiveItems[i];
            if (!item) {
              return <div key={i} style={{ aspectRatio: '3/4', borderRadius: 7, background: G[i % 6], opacity: 0.35 }} />;
            }
            const thumb = archiveThumbUrl(item);
            const picked = archiveId === item.id;
            const thumbSt = refThumbStyle(picked);
            return (
            <Hoverable
              key={item.id}
              style={{
                ...thumbSt.base,
                background: thumb ? `url(${thumb}) center/cover` : G[i % 6],
              }}
              hover={thumbSt.hover}
              onClick={() => cabinet.setSlotArchivePicks((prev) => syncRefArchivePicks(prev, mode, index, item.id))}
            />
          );})}
        </div>
      ) : (
        <>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) cabinet.setUploadFile(uploadKey, file);
              e.target.value = '';
            }}
          />
          <Hoverable
            style={{
              aspectRatio: '3/4', borderRadius: 12,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 6, cursor: 'pointer', overflow: 'hidden', position: 'relative',
              ...refUploadStyle(hasFile).base,
              ...(hasFile ? { background: 'rgba(74,222,128,.06)' } : {}),
              ...(previewUrl ? { background: `center/cover no-repeat url(${previewUrl})`, borderStyle: 'solid' } : {}),
            }}
            hover={{
              ...refUploadStyle(hasFile).hover,
              ...(previewUrl ? { background: `center/cover no-repeat url(${previewUrl})` } : { background: hasFile ? 'rgba(74,222,128,.06)' : 'rgba(215,244,82,.03)' }),
            }}
            onClick={() => fileRef.current?.click()}
          >
            {!previewUrl && (
              <>
                <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
                <span style={{ fontSize: 10, fontWeight: 700, color: color.textDim, textAlign: 'center', padding: '0 8px' }}>
                  {t.srcUpload}
                </span>
              </>
            )}
            {previewUrl && (
              <span style={{
                position: 'absolute', left: 0, right: 0, bottom: 0,
                background: 'linear-gradient(transparent,rgba(0,0,0,.75))',
                fontSize: 9.5, fontWeight: 700, color: '#fff', padding: '18px 8px 8px',
                textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {cabinet.uploadFiles[uploadKey]?.name || t.srcUpload}
              </span>
            )}
          </Hoverable>
        </>
      )}
    </div>
  );
}

export default function Images() {
  const { t, lang, s, setS, isMobile, go, cabinet } = useApp();

  const modes = modeDefs(lang, t.cr);
  const curMode = modes.find((m) => m.id === s.imgMode) || modes[0];
  const models = enginesForNsfw(s.contentMode === 'nsfw', cabinet.genModels);
  const charNames = (cabinet.models || []).map((m) => m.name).filter(Boolean);

  const handleGenerate = () => {
    const studioStore = {
      selectedModelId: cabinet.selectedModelId,
      uploadFiles: cabinet.uploadFiles,
      slotArchivePicks: cabinet.slotArchivePicks,
    };
    const errs = validateStudioForm(s, studioStore, t);
    if (errs.length) {
      setS({ showGenError: true, genErrors: errs });
      return;
    }
    setS({ showGenError: false, genErrors: [] });
    void cabinet.generateImages(s, s.studioPrompt || '');
  };

  const imgErrList = s.showGenError && Array.isArray(s.genErrors) && s.genErrors.length
    ? s.genErrors
    : [t.errNoRef, t.errNoPrompt, t.errNoChar];

  const studioGrid = isMobile
    ? { display: 'grid', gridTemplateColumns: '1fr', gap: 14 }
    : { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 16, alignItems: 'start' };

  const pickContentMode = (contentMode) => {
    const list = enginesForNsfw(contentMode === 'nsfw', cabinet.genModels);
    setS({ contentMode, aiModel: list[0]?.id || (contentMode === 'nsfw' ? 'wan-2.7' : 'nano-banana-pro') });
  };

  const cmSeg = (on, tone) => ({
    flex: 1, textAlign: 'center', fontSize: 12, fontWeight: 800,
    borderRadius: 8, padding: '8px 10px', cursor: 'pointer', boxSizing: 'border-box',
    border: '1px solid transparent',
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
          const modeSt = modeCardStyle(on);
          return (
            <Hoverable
              key={m.id}
              style={modeSt.base}
              hover={modeSt.hover}
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
                onClick={() => pickContentMode('sfw')}
              >
                SFW · {lang === 'ru' ? 'обычный' : 'safe'}
              </div>
              <div
                style={cmSeg(s.contentMode === 'nsfw', { background: color.pink, color: '#2A0A1C' })}
                onClick={() => pickContentMode('nsfw')}
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
                const pickSt = cardPickStyle(on);
                return (
                  <Hoverable
                    key={m.id}
                    style={pickSt.base}
                    hover={pickSt.hover}
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
              {(cabinet.models || []).map((m) => (
                <SelectPill
                  key={m.id}
                  accent="pink"
                  on={sameStudioModelId(cabinet.selectedModelId, m.id)}
                  onClick={() => cabinet.setSelectedModelId(m.id)}
                >
                  {m.name || `#${m.id}`}
                </SelectPill>
              ))}
            </div>
            {!(cabinet.models || []).length && (
              <div style={{ fontSize: 12, color: color.textDim, lineHeight: 1.55, marginTop: 4 }}>
                {cabinet.modelsLoadError ? (
                  <span style={{ color: color.orange }}>{cabinet.modelsLoadError}</span>
                ) : (
                  <>
                    {lang === 'ru' ? 'Нет персонажей — ' : 'No characters — '}
                    <Hoverable
                      as="span"
                      style={{ color: color.lime, fontWeight: 700, cursor: 'pointer' }}
                      hover={{ color: color.limeHi }}
                      onClick={go('characters')}
                    >
                      {lang === 'ru' ? 'создайте в «Персонажи»' : 'create in Characters'}
                    </Hoverable>
                  </>
                )}
              </div>
            )}
          </div>

          {/* format */}
          <div>
            <Eyebrow>{t.format}</Eyebrow>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {ratios.map((r) => (
                <Chip key={r} on={cabinet.selectedAspect === r} onClick={() => cabinet.setSelectedAspect(r)}>{r}</Chip>
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
              value={s.studioPrompt || ''}
              onChange={(e) => setS({ studioPrompt: e.target.value })}
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
            onClick={handleGenerate}
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
            {(cabinet.archiveImages.length ? cabinet.archiveImages : []).slice(0, 8).map((item, i) => {
              const thumb = archiveThumbUrl(item);
              const pending = isArchivePending(item);
              const failed = (item.status || '').trim() === 'failed';
              const model = cabinet.models.find((m) => m.id === item.studio_model_id);
              return (
              <Hoverable
                key={item.id || i}
                style={{
                  borderRadius: 12, overflow: 'hidden', background: color.surface,
                  border: `1px solid ${failed ? 'rgba(248,113,113,.45)' : line.hair}`,
                  cursor: pending || failed ? 'default' : 'pointer',
                  opacity: pending ? 0.88 : 1,
                }}
                hover={pending || failed ? {} : { borderColor: borderHoverOff }}
                onClick={() => {
                  if (!pending && !failed) setS({ lightbox: item.id ?? i });
                }}
              >
                <div
                  style={{
                    aspectRatio: '9/16', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', position: 'relative',
                    background: thumb ? `center/cover no-repeat url(${thumb})` : G[i % 6],
                  }}
                >
                  {!thumb && !pending && !failed && (
                    <span style={{ display: 'flex', width: 22, height: 22, color: 'rgba(255,255,255,.35)' }}><IcoImage /></span>
                  )}
                  {pending && (
                    <div
                      style={{
                        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', background: 'rgba(6,7,9,.55)',
                      }}
                    >
                      <div
                        style={{
                          width: 22, height: 22, borderRadius: '50%',
                          border: '2.5px solid rgba(215,244,82,.25)', borderTopColor: color.lime,
                          animation: 'mmSpin .8s linear infinite',
                        }}
                      />
                    </div>
                  )}
                  {failed && (
                    <div
                      style={{
                        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', gap: 6,
                        background: 'rgba(40,10,12,.82)', padding: '10px 8px',
                      }}
                    >
                      <span
                        style={{
                          fontFamily: font.mono, fontSize: 8, letterSpacing: '.8px', fontWeight: 800,
                          color: color.red, background: 'rgba(248,113,113,.12)',
                          border: '1px solid rgba(248,113,113,.35)', borderRadius: 6, padding: '3px 7px',
                        }}
                      >
                        {lang === 'ru' ? 'ОШИБКА' : 'FAILED'}
                      </span>
                      <span
                        style={{
                          fontSize: 10, fontWeight: 600, color: '#FECACA', textAlign: 'center',
                          lineHeight: 1.35, maxHeight: '4.2em', overflow: 'hidden', wordBreak: 'break-word',
                        }}
                      >
                        {(item.error_message || '').trim().slice(0, 140) || (lang === 'ru' ? 'Ошибка генерации' : 'Generation failed')}
                      </span>
                    </div>
                  )}
                  {!pending && !failed && (
                    <span
                      style={{
                        position: 'absolute', top: 7, right: 7, display: 'flex', width: 15, height: 15,
                        color: 'rgba(255,255,255,.7)', background: 'rgba(0,0,0,.4)', borderRadius: 6, padding: 3,
                      }}
                    >
                      <IcoZoom />
                    </span>
                  )}
                </div>
                <div style={{ padding: '8px 10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{ fontWeight: 700, fontSize: 11 }}>{model?.name || '—'}</span>
                    <span style={{ fontFamily: font.mono, fontSize: 8.5, color: failed ? color.red : color.textGhost }}>
                      {failed ? (lang === 'ru' ? 'ошибка' : 'failed') : (item.aspect_ratio || item.output_aspect || '9:16')}
                    </span>
                  </div>
                </div>
              </Hoverable>
            );})}
            {!cabinet.archiveImages.length && (
              <div style={{ gridColumn: '1 / -1', fontSize: 12, color: color.textGhost, padding: 16 }}>
                {lang === 'ru' ? 'Архив пуст — сгенерируйте первый кадр' : 'Archive is empty — generate your first frame'}
              </div>
            )}
          </div>
        </div>
      </div>
    </Fade>
  );
}
