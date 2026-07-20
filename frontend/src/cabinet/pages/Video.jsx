import { useEffect, useRef, useMemo } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoFilm, IcoSpark, IcoUpload, IcoPlay, IcoText } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip, SelectPill } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { modeCardStyle, refUploadStyle, borderHoverOff } from '../styles/mixins';
import { videoModeDefs } from '../data/catalog';
import { archiveThumbUrl, archiveDownloadUrl, isArchivePending } from '../api/actions';
import { sameStudioModelId } from '../api/studioHelpers';
import { computeMotionVideoCreditCost } from '../../studioMotionPricing';

const vidModeIcons = { film: IcoFilm, text: IcoText };

/** Как на бэкенде: 720/1080/4k → Seedance resolution (4k в API уходит как 1080p). */
function vidQualityToResolution(vidQuality) {
  const v = String(vidQuality || '1080').toLowerCase();
  if (v === '1080' || v === '1080p' || v === '4k') return '1080p';
  if (v === '480' || v === '480p') return '480p';
  return '720p';
}

export default function Video() {
  const { t, lang, s, setS, isMobile, go, cabinet } = useApp();
  const videoRef = useRef(null);
  const frameRef = useRef(null);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const genFirstFrame = () => {
    setS({ ffState: 'loading' });
    void cabinet
      .generateFirstFrame(s, '')
      .then(() => setS({ ffState: 'done' }))
      .catch(() => setS({ ffState: 'idle' }));
  };

  const handleGenerateVideo = () => {
    void cabinet.generateVideo(s);
  };

  const vidModes = videoModeDefs(lang);
  const curVidMode = vidModes.find((m) => m.id === s.vidMode) || vidModes[0];
  const motionControl = s.vidMode === 'motion-control';

  const studioGrid = isMobile
    ? { display: 'grid', gridTemplateColumns: '1fr', gap: 14 }
    : { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 16, alignItems: 'start' };

  const ffSeg = (on) => ({
    flex: 1, textAlign: 'center', fontSize: 12, fontWeight: 800, lineHeight: 1.35,
    borderRadius: 9, padding: '9px 10px', cursor: 'pointer', boxSizing: 'border-box',
    border: `1px solid ${on ? 'transparent' : line.strong}`,
    ...(on ? { background: color.lime, color: color.limeInk } : { color: color.textDim }),
  });

  const vidCost = useMemo(() => {
    const duration = Number(s.vidTime) || 5;
    const hasReferenceVideo = Boolean(cabinet.motionVideoFileId);
    const pricing = cabinet.health?.studio_motion_video_pricing;
    return computeMotionVideoCreditCost(duration, hasReferenceVideo, pricing, {
      variant: 'standard',
      resolution: vidQualityToResolution(s.vidQuality),
    });
  }, [cabinet.health, cabinet.motionVideoFileId, s.vidTime, s.vidQuality]);
  const ffImgStyle = { width: 70, aspectRatio: '9/16', borderRadius: 10, flex: 'none', background: G[3] };

  const qualityOpts = [{ l: '720p', v: '720' }, { l: '1080p', v: '1080' }, { l: '4K', v: '4k' }];
  const vfmtOpts = ['9:16', '16:9', '1:1', '4:3', '3:4'];
  const vtimeOpts = Array.from({ length: 12 }, (_, i) => {
    const sec = i + 4;
    return { l: lang === 'ru' ? `${sec} с` : `${sec}s`, v: String(sec) };
  });

  return (
    <Fade data-screen-label="Студия — Видео">
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>{t.navVideo}</PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.videoDesc}</div>
      </div>

      {/* mode cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginBottom: 18 }}>
        {vidModes.map((m) => {
          const on = s.vidMode === m.id;
          const Icon = vidModeIcons[m.icon];
          const modeSt = modeCardStyle(on);
          const disabled = Boolean(m.disabled);
          return (
            <Hoverable
              key={m.id}
              style={{
                ...modeSt.base,
                ...(disabled ? { opacity: 0.55, cursor: 'not-allowed' } : {}),
              }}
              hover={disabled ? {} : modeSt.hover}
              onClick={() => {
                if (!disabled) setS({ vidMode: m.id });
              }}
              aria-pressed={on}
              aria-disabled={disabled}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                <div
                  style={{
                    width: 36, height: 36, borderRadius: 11, display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    ...(on
                      ? { background: 'rgba(215,244,82,.15)', color: color.lime }
                      : { background: 'rgba(255,255,255,.06)', color: color.textDim }),
                  }}
                >
                  <span style={{ display: 'flex', width: 18, height: 18 }}><Icon /></span>
                </div>
                {m.badge && (
                  <span
                    style={{
                      fontFamily: font.mono, fontSize: 8.5, letterSpacing: '0.6px', fontWeight: 700,
                      background: 'rgba(255,255,255,.06)', border: `1px solid ${line.strong}`,
                      borderRadius: 6, padding: '3px 7px', color: color.textDim, whiteSpace: 'nowrap',
                    }}
                  >
                    {m.badge}
                  </span>
                )}
              </div>
              <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 4 }}>{m.title}</div>
              <div style={{ fontSize: 11, color: color.textDim, lineHeight: 1.45 }}>{m.desc}</div>
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
            <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 3 }}>{curVidMode.title}</div>
            <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5 }}>{curVidMode.longDesc}</div>
          </div>

          {motionControl && (
          <>
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
              <div style={{ fontSize: 12, color: color.textDim, marginTop: 4 }}>
                {cabinet.modelsLoadError || (
                  <>
                    {lang === 'ru' ? 'Нет персонажей — ' : 'No characters — '}
                    <span style={{ color: color.lime, fontWeight: 700, cursor: 'pointer' }} onClick={go('characters')}>
                      {lang === 'ru' ? 'создайте в «Персонажи»' : 'create in Characters'}
                    </span>
                  </>
                )}
              </div>
            )}
          </div>

          {/* reference video */}
          <div>
            <Eyebrow>{t.refVideo}</Eyebrow>
            <input
              ref={videoRef}
              type="file"
              accept="video/mp4,video/*"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void cabinet.uploadDrivingVideo(file);
                e.target.value = '';
              }}
            />
            <Hoverable
              style={{
                borderRadius: 12, padding: 20,
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, cursor: 'pointer',
                ...refUploadStyle(Boolean(cabinet.motionVideoFileId)).base,
                ...(cabinet.motionVideoFileId ? { background: 'rgba(74,222,128,.06)' } : {}),
              }}
              hover={{
                ...refUploadStyle(Boolean(cabinet.motionVideoFileId)).hover,
                background: cabinet.motionVideoFileId ? 'rgba(74,222,128,.06)' : 'rgba(215,244,82,.03)',
              }}
              onClick={() => videoRef.current?.click()}
            >
              <span style={{ display: 'flex', width: 22, height: 22, color: color.textMuted }}><IcoFilm /></span>
              <span style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, textAlign: 'center' }}>
                {cabinet.uploadFiles['motion-video']?.name || t.dropVideo}
              </span>
            </Hoverable>
          </div>

          {/* has first frame? */}
          <div>
            <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>{t.hasFirstFrame}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={ffSeg(s.hasFirstFrame === 'yes')} onClick={() => setS({ hasFirstFrame: 'yes' })}>
                {t.ffYes}
              </div>
              <div style={ffSeg(s.hasFirstFrame === 'no')} onClick={() => setS({ hasFirstFrame: 'no' })}>
                {t.ffNo}
              </div>
            </div>
          </div>

          {/* upload first frame */}
          {s.hasFirstFrame === 'yes' && (
            <div>
              <Eyebrow>{t.sourceFrame}</Eyebrow>
              <input
                ref={frameRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) cabinet.setUploadFile('motion-frame', file);
                  e.target.value = '';
                }}
              />
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Hoverable
                  style={{
                    flex: 1, borderRadius: 12, padding: '16px 12px',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer',
                    ...refUploadStyle(Boolean(cabinet.uploadFiles['motion-frame'])).base,
                  }}
                  hover={{
                    ...refUploadStyle(Boolean(cabinet.uploadFiles['motion-frame'])).hover,
                    background: 'rgba(215,244,82,.03)',
                  }}
                  onClick={() => frameRef.current?.click()}
                >
                  <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: color.textDim, textAlign: 'center' }}>
                    {cabinet.uploadFiles['motion-frame']?.name || t.uploadFirst}
                  </span>
                </Hoverable>
              </div>
              <div style={{ fontSize: 10.5, color: color.textGhost, marginTop: 6 }}>{t.pickFromArchive}</div>
              {(cabinet.archiveImages || []).slice(0, 8).length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 5, marginTop: 8 }}>
                  {(cabinet.archiveImages || []).slice(0, 8).map((item, i) => {
                    const thumb = archiveThumbUrl(item);
                    const picked = s.carouselPickId === item.id;
                    return (
                      <Hoverable
                        key={item.id || i}
                        style={{
                          aspectRatio: '9/16', borderRadius: 8, cursor: 'pointer',
                          border: picked ? '2px solid rgba(215,244,82,.7)' : '1px solid rgba(255,255,255,.12)',
                          background: thumb ? `url(${thumb}) center/cover` : G[i % 6],
                        }}
                        hover={{ borderColor: 'rgba(215,244,82,.5)' }}
                        onClick={() => {
                          setS({ carouselPickId: item.id });
                          cabinet.setUploadFile('motion-frame', null);
                        }}
                      />
                    );
                  })}
                </div>
              )}
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
                      className="mm-spin"
                      style={{
                        width: 22, height: 22, borderRadius: '50%',
                        border: '2.5px solid rgba(192,132,252,.25)', borderTopColor: color.purple,
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
                  <div
                    style={{
                      ...ffImgStyle,
                      ...(cabinet.firstFrameUrl ? { background: `center/cover url(${cabinet.firstFrameUrl})` } : {}),
                      display: 'flex', alignItems: 'flex-end', padding: 6,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: font.mono, fontSize: 7.5, background: 'rgba(0,0,0,.6)',
                        color: '#fff', padding: '2px 6px', borderRadius: 4,
                      }}
                    >
                      {(cabinet.models.find((m) => m.id === cabinet.selectedModelId)?.name || '—')} · {cabinet.selectedAspect || '9:16'}
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

          </>
          )}

          {!motionControl && (
            <div
              style={{
                border: `1px dashed ${line.strong}`, borderRadius: 12, padding: '24px 16px',
                textAlign: 'center', color: color.textDim, fontSize: 12.5, lineHeight: 1.5,
              }}
            >
              {t.inDevelopment}
            </div>
          )}

          {motionControl && (
          <>
          {/* motion prompt — скрыто: промпт генерируется на сервере из референс-видео */}
          {/* quality / format / duration */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <Eyebrow size={9} spacing="1.4px" style={{ marginBottom: 7 }}>{t.vidQuality}</Eyebrow>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {qualityOpts.map((q) => (
                  <Chip key={q.v} on={s.vidQuality === q.v} onClick={() => setS({ vidQuality: q.v })}>{q.l}</Chip>
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
            onClick={handleGenerateVideo}
          >
            <span style={{ display: 'flex', width: 17, height: 17, color: color.limeInk }}><IcoFilm /></span>
            <span style={{ flex: 1, fontWeight: 800, fontSize: 14, color: color.limeInk }}>{t.generateVideo}</span>
            <span style={{ fontFamily: font.mono, fontSize: 11, fontWeight: 600, color: color.limeInkSoft }}>
              −{vidCost} {t.cr}
            </span>
          </Hoverable>
          </>
          )}
        </div>

        {/* archive */}
        <div>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 10 }}>{t.archive}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10 }}>
            {(cabinet.archiveVideos || []).slice(0, 8).map((item, i) => {
              const thumb = archiveThumbUrl(item);
              const downloadUrl = archiveDownloadUrl(item);
              const pending = isArchivePending(item);
              const failed = (item.status || '').trim() === 'failed';
              const model = (cabinet.models || []).find((m) => m.id === item.studio_model_id);
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
              >
                <div
                  style={{
                    aspectRatio: '9/16', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    position: 'relative', background: thumb ? `url(${thumb}) center/cover` : G[(i + 2) % 6],
                  }}
                >
                  {pending && (
                    <div
                      style={{
                        position: 'absolute', inset: 0, background: 'rgba(0,0,0,.45)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: font.mono, fontSize: 9, fontWeight: 700, color: color.orange,
                      }}
                    >
                      {lang === 'ru' ? 'ГЕНЕРАЦИЯ…' : 'GENERATING…'}
                    </div>
                  )}
                  {failed && (
                    <div
                      style={{
                        position: 'absolute', inset: 0, background: 'rgba(248,113,113,.25)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: font.mono, fontSize: 9, fontWeight: 700, color: color.red,
                      }}
                    >
                      {lang === 'ru' ? 'ОШИБКА' : 'FAILED'}
                    </div>
                  )}
                  {!pending && !failed && (
                  <div
                    style={{
                      width: 36, height: 36, borderRadius: '50%', background: 'rgba(0,0,0,.45)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    <span style={{ display: 'flex', width: 14, height: 14, color: '#fff', marginLeft: 2 }}><IcoPlay /></span>
                  </div>
                  )}
                </div>
                <div style={{ padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontSize: 11 }}>{model?.name || '—'}</span>
                  {downloadUrl && !pending && (
                    <a href={downloadUrl} download style={{ fontSize: 10, fontWeight: 700, color: color.textDim, textDecoration: 'none' }}>↓ MP4</a>
                  )}
                </div>
              </Hoverable>
            );})}
          </div>
        </div>
      </div>
    </Fade>
  );
}
