import { useEffect, useMemo, useState } from 'react';

import { Fade, Field, NoteBlock, PageTitle, Panel, BackLink, SelectPill } from '../components/ui';
import Hoverable from '../components/Hoverable';
import { color, line, font } from '../styles/tokens';
import { useApp } from '../hooks/useApp';
import { apiFetch } from '../../api';
import {
  approveWizardBatch,
  approveWizardOpening,
  createShotBatchWizard,
  generateWizardOpening,
  planShotBatchWizard,
  renderWizardBatch,
  stitchShotBatchWizard,
  uploadWizardBatchVideo,
  uploadWizardOpening,
} from '../api/actions';
import { FALLBACK_GEN_MODELS } from '../api/studioHelpers';

function shortDur(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(2).replace(/\.00$/, '');
}

function mediaUrlWithCacheBust(src, version) {
  const value = String(src || '').trim();
  if (!value || version == null || value.includes('&v=') || value.includes('?v=')) return value;
  const sep = value.includes('?') ? '&' : '?';
  return `${value}${sep}v=${encodeURIComponent(String(version))}`;
}

function isDirectMediaUrl(src) {
  const value = String(src || '').trim();
  if (!value) return false;
  return value.startsWith('http') || value.startsWith('data:') || value.includes('public-shot-batch-output');
}

function AuthMedia({ src, as = 'video', alt = '', style }) {
  const [resolvedSrc, setResolvedSrc] = useState(() => (isDirectMediaUrl(src) ? src : null));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    if (!src) {
      setResolvedSrc(null);
      return undefined;
    }
    if (isDirectMediaUrl(src)) {
      setResolvedSrc(src);
      return undefined;
    }
    let cancelled = false;
    let objectUrl = null;
    void (async () => {
      try {
        const res = await apiFetch(src);
        if (!res.ok || cancelled) {
          if (!cancelled) setFailed(true);
          return;
        }
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setResolvedSrc(objectUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (!src) return null;
  if (failed) {
    return (
      <div style={{ ...style, display: 'grid', placeItems: 'center', color: color.textMuted, fontSize: 12 }}>
        media load failed
      </div>
    );
  }
  if (!resolvedSrc) {
    return (
      <div style={{ ...style, display: 'grid', placeItems: 'center', color: color.textMuted, fontSize: 12 }}>
        loading…
      </div>
    );
  }
  if (as === 'img') {
    return <img src={resolvedSrc} alt={alt} style={style} />;
  }
  return <video src={resolvedSrc} controls preload="metadata" style={style} />;
}

const STEPS = [
  { id: 'setup', ru: 'Настройка', en: 'Setup' },
  { id: 'plan', ru: 'План', en: 'Plan' },
  { id: 'openings', ru: 'Opening frames', en: 'Opening frames' },
  { id: 'videos', ru: 'Batch videos', en: 'Batch videos' },
  { id: 'stitch', ru: 'Склейка', en: 'Stitch' },
];

function stepIndex(phase) {
  if (phase === 'created') return 0;
  if (phase === 'planned') return 1;
  if (phase === 'openings') return 2;
  if (phase === 'videos') return 3;
  if (phase === 'stitched') return 4;
  return 0;
}

function ActionBtn({ children, onClick, disabled, tone = 'lime' }) {
  const bg = tone === 'lime' ? color.lime : color.bgPanel;
  const fg = tone === 'lime' ? color.limeInk : color.text;
  return (
    <Hoverable
      style={{
        background: bg,
        color: fg,
        fontWeight: 700,
        fontSize: 12,
        borderRadius: 8,
        padding: '8px 12px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        border: tone === 'lime' ? 'none' : `1px solid ${line.soft}`,
      }}
      hover={{ filter: disabled ? 'none' : 'brightness(1.05)' }}
      onClick={disabled ? undefined : onClick}
    >
      {children}
    </Hoverable>
  );
}

export default function ShotBatchWizard() {
  const { lang, cabinet } = useApp();
  const models = cabinet.models || [];
  const t = (ru, en) => (lang === 'ru' ? ru : en);

  const [motionVideo, setMotionVideo] = useState(null);
  const [modelId, setModelId] = useState(cabinet.selectedModelId || models[0]?.id || '');
  const [sceneBrief, setSceneBrief] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('');
  const [motionTimeline, setMotionTimeline] = useState('');
  const [outputAspect, setOutputAspect] = useState('9:16');
  const [seedanceVariant, setSeedanceVariant] = useState('standard');
  const [videoResolution, setVideoResolution] = useState('720p');
  const [generateAudio, setGenerateAudio] = useState(true);
  const [sceneThreshold, setSceneThreshold] = useState('0.35');
  const [maxShotsPerBatch, setMaxShotsPerBatch] = useState('4');
  const [maxBatchDurationSec, setMaxBatchDurationSec] = useState('12');
  const [minShotDurationSec, setMinShotDurationSec] = useState('0.4');
  const [faceSamples, setFaceSamples] = useState('6');
  const [crossfadeMs, setCrossfadeMs] = useState('0');
  const [waveModelId, setWaveModelId] = useState('nano-banana-pro');

  const [busy, setBusy] = useState(false);
  const [busyBatch, setBusyBatch] = useState(null);
  const [wizard, setWizard] = useState(null);
  const [openingUploads, setOpeningUploads] = useState({});
  const [videoUploads, setVideoUploads] = useState({});

  useEffect(() => {
    if (!modelId && models[0]?.id) setModelId(models[0].id);
  }, [modelId, models]);

  const formParams = useMemo(() => ({
    motionVideo,
    modelId,
    sceneBrief,
    negativePrompt,
    motionTimeline,
    outputAspect,
    seedanceVariant,
    videoResolution,
    generateAudio,
    sceneThreshold: Number(sceneThreshold),
    maxShotsPerBatch: Number(maxShotsPerBatch),
    maxBatchDurationSec: Number(maxBatchDurationSec),
    minShotDurationSec: Number(minShotDurationSec),
    faceSamples: Number(faceSamples),
    crossfadeMs: Number(crossfadeMs),
    waveModelId,
  }), [
    motionVideo, modelId, sceneBrief, negativePrompt, motionTimeline, outputAspect,
    seedanceVariant, videoResolution, generateAudio, sceneThreshold, maxShotsPerBatch,
    maxBatchDurationSec, minShotDurationSec, faceSamples, crossfadeMs, waveModelId,
  ]);

  const phase = wizard?.wizard_phase || 'created';
  const activeStep = stepIndex(phase);
  const batchList = useMemo(() => {
    const batches = wizard?.batches || {};
    return Object.keys(batches)
      .map((k) => batches[k])
      .sort((a, b) => Number(a.batch_id) - Number(b.batch_id));
  }, [wizard]);

  const imageModels = cabinet.genModels?.length ? cabinet.genModels : FALLBACK_GEN_MODELS;
  const allOpeningsApproved = batchList.length > 0 && batchList.every((b) => b.opening?.status === 'approved');
  const allVideosApproved = batchList.length > 0 && batchList.every((b) => b.video?.status === 'approved');

  const run = async (fn) => {
    setBusy(true);
    cabinet.setError(null);
    try {
      await fn();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    } finally {
      setBusy(false);
      setBusyBatch(null);
    }
  };

  const onCreate = () => run(async () => {
    if (!motionVideo || !modelId) return;
    const data = await createShotBatchWizard(formParams);
    setWizard(data);
  });

  const onPlan = () => run(async () => {
    if (!wizard?.job_id) return;
    const data = await planShotBatchWizard(wizard.job_id);
    setWizard(data);
  });

  const onOpening = (batchId, approve = false) => run(async () => {
    if (!wizard?.job_id) return;
    setBusyBatch(`opening-${batchId}`);
    const data = approve
      ? await approveWizardOpening(wizard.job_id, batchId)
      : await generateWizardOpening(wizard.job_id, batchId);
    setWizard(data);
  });

  const onUploadOpening = (batchId) => run(async () => {
    if (!wizard?.job_id) return;
    const file = openingUploads[batchId];
    if (!file) return;
    setBusyBatch(`opening-upload-${batchId}`);
    const data = await uploadWizardOpening(wizard.job_id, batchId, file);
    setWizard(data);
    setOpeningUploads((prev) => ({ ...prev, [batchId]: null }));
  });

  const onUploadVideo = (batchId) => run(async () => {
    if (!wizard?.job_id) return;
    const file = videoUploads[batchId];
    if (!file) return;
    setBusyBatch(`video-upload-${batchId}`);
    const data = await uploadWizardBatchVideo(wizard.job_id, batchId, file);
    setWizard(data);
    setVideoUploads((prev) => ({ ...prev, [batchId]: null }));
  });

  const onRender = (batchId, approve = false) => run(async () => {
    if (!wizard?.job_id) return;
    setBusyBatch(`video-${batchId}`);
    const data = approve
      ? await approveWizardBatch(wizard.job_id, batchId)
      : await renderWizardBatch(wizard.job_id, batchId);
    setWizard(data);
  });

  const onStitch = () => run(async () => {
    if (!wizard?.job_id) return;
    const data = await stitchShotBatchWizard(wizard.job_id, Number(crossfadeMs));
    setWizard(data);
  });

  const imgStyle = {
    width: '100%',
    maxWidth: 160,
    aspectRatio: '9 / 16',
    objectFit: 'cover',
    borderRadius: 10,
    border: `1px solid ${line.soft}`,
    background: color.bg,
  };

  const vidStyle = {
    width: '100%',
    borderRadius: 10,
    border: `1px solid ${line.soft}`,
    background: '#000',
  };

  return (
    <Fade data-screen-label="Shot-batch wizard">
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        <BackLink onClick={() => window.location.assign('/workspace/video')}>
          {t('Назад в видео', 'Back to video')}
        </BackLink>

        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 6 }}>Shot-batch wizard</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>
            {t(
              'План → opening (генерация или загрузка) → видео batch (рендер или готовый клип) → Approve хвоста для следующего opening → склейка.',
              'Plan → opening (generate or upload) → batch video (render or upload clip) → Approve tail for next opening → stitch.',
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {STEPS.map((s, i) => (
            <div
              key={s.id}
              style={{
                padding: '6px 12px',
                borderRadius: 999,
                fontSize: 12,
                fontWeight: 700,
                background: i <= activeStep ? color.lime : color.bgPanel,
                color: i <= activeStep ? color.limeInk : color.textMuted,
                border: `1px solid ${line.soft}`,
              }}
            >
              {i + 1}. {t(s.ru, s.en)}
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 380px) 1fr', gap: 16 }}>
          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <NoteBlock>
              {t(
                'Сначала создай wizard job. Затем Build plan — увидишь разбивку. Для каждого batch: сгенерируй opening → approve → render video → approve. В конце Stitch.',
                'Create wizard job, build plan, then per-batch opening/video with approve gates.',
              )}
            </NoteBlock>

            {!wizard?.job_id && (
              <>
                <div>
                  <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>{t('ПЕРСОНАЖ', 'MODEL')}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {models.map((m) => (
                      <SelectPill key={m.id} on={String(modelId) === String(m.id)} onClick={() => setModelId(m.id)}>
                        {m.name}
                      </SelectPill>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>MOTION VIDEO</div>
                  <input type="file" accept="video/*" onChange={(e) => setMotionVideo(e.target.files?.[0] || null)} />
                </div>
                <Field label={t('Scene brief', 'Scene brief')} value={sceneBrief} onChange={(e) => setSceneBrief(e.target.value)} area rows={2} />
                <Field label="negative_prompt" value={negativePrompt} onChange={(e) => setNegativePrompt(e.target.value)} area rows={2} />
                <Field label="motion_timeline" value={motionTimeline} onChange={(e) => setMotionTimeline(e.target.value)} area rows={2} />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <Field label="output_aspect" value={outputAspect} onChange={(e) => setOutputAspect(e.target.value)} />
                  <Field
                    label={t('crossfade_ms (0 = без ghosting)', 'crossfade_ms (0 = no ghosting)')}
                    value={crossfadeMs}
                    onChange={(e) => setCrossfadeMs(e.target.value)}
                  />
                </div>
                <div>
                  <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                    {t('Разрешение видео', 'Video resolution')}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {['480p', '720p'].map((res) => (
                      <SelectPill key={res} on={videoResolution === res} onClick={() => setVideoResolution(res)}>
                        {res}
                      </SelectPill>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>Seedance</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    <SelectPill on={seedanceVariant === 'standard'} onClick={() => setSeedanceVariant('standard')}>
                      2.0
                    </SelectPill>
                    <SelectPill on={seedanceVariant === 'seedance_25'} onClick={() => setSeedanceVariant('seedance_25')}>
                      2.5
                    </SelectPill>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                    {t('Модель картинок (opening)', 'Image model (opening)')}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {imageModels.map((m) => (
                      <SelectPill
                        key={m.id}
                        on={waveModelId === m.id}
                        onClick={() => setWaveModelId(m.id)}
                      >
                        {m.label || m.name || m.id}
                      </SelectPill>
                    ))}
                  </div>
                </div>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
                  <input type="checkbox" checked={generateAudio} onChange={(e) => setGenerateAudio(e.target.checked)} />
                  generate_audio
                </label>
                <ActionBtn disabled={busy || !motionVideo || !modelId} onClick={onCreate}>
                  {busy ? '…' : t('1. Создать wizard job', '1. Create wizard job')}
                </ActionBtn>
              </>
            )}

            {!!wizard?.job_id && (
              <>
                <div style={{ fontSize: 12, color: color.textDim }}>
                  job {wizard.job_id} · phase {phase}
                  <div style={{ marginTop: 4 }}>
                    {videoResolution} · Seedance {seedanceVariant === 'seedance_25' ? '2.5' : '2.0'} ·{' '}
                    {imageModels.find((m) => m.id === waveModelId)?.label
                      || imageModels.find((m) => m.id === waveModelId)?.name
                      || waveModelId}
                  </div>
                </div>
                <ActionBtn disabled={busy || phase !== 'created'} onClick={onPlan}>
                  {busy ? '…' : t('2. Build plan', '2. Build plan')}
                </ActionBtn>
                <ActionBtn
                  disabled={busy || !allVideosApproved}
                  onClick={onStitch}
                >
                  {busy ? '…' : t('5. Stitch (hard cut)', '5. Stitch (hard cut)')}
                </ActionBtn>
              </>
            )}
          </Panel>

          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 520 }}>
            {!wizard?.job_id && (
              <NoteBlock>{t('Загрузи видео и создай wizard job.', 'Upload video and create wizard job.')}</NoteBlock>
            )}

            {!!wizard?.job_id && phase === 'created' && (
              <NoteBlock>{t('Нажми Build plan.', 'Click Build plan.')}</NoteBlock>
            )}

            {batchList.map((item) => {
              const rb = item.resolved || {};
              const opening = item.opening || {};
              const video = item.video || {};
              const bid = item.batch_id;
              const openingBusy = busyBatch === `opening-${bid}`;
              const openingUploadBusy = busyBatch === `opening-upload-${bid}`;
              const videoBusy = busyBatch === `video-${bid}`;
              const videoUploadBusy = busyBatch === `video-upload-${bid}`;
              const openingUploadFile = openingUploads[bid] || null;
              const videoUploadFile = videoUploads[bid] || null;

              return (
                <div
                  key={`batch-${bid}`}
                  style={{
                    border: `1px solid ${line.soft}`,
                    borderRadius: 12,
                    padding: 14,
                    background: color.bgPanel,
                    display: 'grid',
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 800 }}>Batch {bid}</div>
                    <div style={{ fontSize: 12, color: color.textDim, marginTop: 4 }}>
                      {rb.resolution_action} · {shortDur(rb.effective_duration)}s · {rb.reason}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                        {t('Сегмент (исходник)', 'Segment (source)')}
                      </div>
                      <AuthMedia
                        as="img"
                        src={item.segment_preview_url || item.segment_preview_public_url}
                        alt={`seg-${bid}`}
                        style={imgStyle}
                      />
                    </div>

                    <div>
                      <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                        Opening · {opening.status || 'pending'}
                        {opening.mode ? ` · ${opening.mode}` : ''}
                      </div>
                      {!!opening.source_label && (
                        <div style={{ fontSize: 11, color: color.textDim, marginBottom: 6 }}>
                          {t('Источник opening:', 'Opening source:')} {opening.source_label}
                        </div>
                      )}
                      {(opening.preview_url || opening.public_url || opening.evolink_url) && (
                        <AuthMedia
                          as="img"
                          src={opening.evolink_url || opening.preview_url || opening.public_url}
                          alt={`opening-${bid}`}
                          style={imgStyle}
                        />
                      )}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                        <ActionBtn
                          tone="panel"
                          disabled={busy || phase === 'created'}
                          onClick={() => onOpening(bid, false)}
                        >
                          {openingBusy ? '…' : t('Сгенерировать', 'Generate')}
                        </ActionBtn>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null;
                            setOpeningUploads((prev) => ({ ...prev, [bid]: file }));
                          }}
                          style={{ maxWidth: 180, fontSize: 12 }}
                        />
                        <ActionBtn
                          tone="panel"
                          disabled={busy || phase === 'created' || !openingUploadFile}
                          onClick={() => onUploadOpening(bid)}
                        >
                          {openingUploadBusy ? '…' : t('Загрузить opening', 'Upload opening')}
                        </ActionBtn>
                        <ActionBtn
                          disabled={busy || opening.status !== 'ready'}
                          onClick={() => onOpening(bid, true)}
                        >
                          {t('Approve', 'Approve')}
                        </ActionBtn>
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                        Video · {video.status || 'pending'}
                        {video.mode ? ` · ${video.mode}` : ''}
                      </div>
                      {!!video.prefill_next_error && (
                        <div style={{ fontSize: 11, color: '#c45c5c', marginBottom: 6 }}>
                          {t('Prefill следующего opening:', 'Next opening prefill:')} {video.prefill_next_error}
                        </div>
                      )}
                      {!!video.start_frame_label && (
                        <div style={{ fontSize: 11, color: color.textDim, marginBottom: 6 }}>
                          {t('Стартовый кадр видео:', 'Video start frame:')} {video.start_frame_label}
                        </div>
                      )}
                      {video.start_frame_public_url && (
                        <AuthMedia
                          as="img"
                          src={video.start_frame_public_url}
                          alt={`video-start-${bid}`}
                          style={imgStyle}
                        />
                      )}
                      {video.preview_public_url && (
                        <AuthMedia
                          key={`batch-video-${bid}-${video.generation || 0}`}
                          as="video"
                          src={mediaUrlWithCacheBust(video.preview_public_url, video.generation)}
                          style={vidStyle}
                        />
                      )}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                        <ActionBtn
                          tone="panel"
                          disabled={busy || opening.status !== 'approved'}
                          onClick={() => onRender(bid, false)}
                        >
                          {videoBusy ? '…' : t('Render batch', 'Render batch')}
                        </ActionBtn>
                        <input
                          type="file"
                          accept="video/*,.mp4,.mov,.webm"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null;
                            setVideoUploads((prev) => ({ ...prev, [bid]: file }));
                          }}
                          style={{ maxWidth: 180, fontSize: 12 }}
                        />
                        <ActionBtn
                          tone="panel"
                          disabled={busy || phase === 'created' || !videoUploadFile}
                          onClick={() => onUploadVideo(bid)}
                        >
                          {videoUploadBusy ? '…' : t('Загрузить клип', 'Upload clip')}
                        </ActionBtn>
                        <ActionBtn
                          disabled={busy || video.status !== 'ready'}
                          onClick={() => onRender(bid, true)}
                        >
                          {t('Approve', 'Approve')}
                        </ActionBtn>
                      </div>
                      {bid >= 1 && (
                        <div style={{ fontSize: 11, color: color.textDim, marginTop: 6 }}>
                          {t(
                            'Готовый клип: Upload → Approve. Opening следующего batch подтянется с последнего кадра.',
                            'Ready clip: Upload → Approve. Next batch opening is taken from the last frame.',
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {wizard?.stitched?.status === 'ready' && (
              <div style={{ display: 'grid', gap: 8 }}>
                <div style={{ fontSize: 11, color: color.textMuted }}>{t('ИТОГОВАЯ СКЛЕЙКА', 'STITCHED OUTPUT')}</div>
                <AuthMedia
                  key={`stitched-${wizard.stitched.generation || 0}`}
                  as="video"
                  src={mediaUrlWithCacheBust(wizard.stitched.public_url, wizard.stitched.generation)}
                  style={{ ...vidStyle, maxWidth: 420 }}
                />
              </div>
            )}

            {!!wizard && (
              <textarea
                readOnly
                value={JSON.stringify(wizard, null, 2)}
                style={{
                  width: '100%',
                  minHeight: 200,
                  resize: 'vertical',
                  background: color.bgPanel,
                  color: color.text,
                  border: `1px solid ${line.soft}`,
                  borderRadius: 10,
                  padding: 12,
                  fontFamily: font.mono,
                  fontSize: 11,
                  lineHeight: 1.45,
                  boxSizing: 'border-box',
                }}
              />
            )}
          </Panel>
        </div>
      </div>
    </Fade>
  );
}
