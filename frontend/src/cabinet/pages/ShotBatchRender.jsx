import { useEffect, useMemo, useState } from 'react';

import { Fade, Field, NoteBlock, PageTitle, Panel, BackLink, SelectPill } from '../components/ui';
import Hoverable from '../components/Hoverable';
import { color, line, font } from '../styles/tokens';
import { useApp } from '../hooks/useApp';
import { runShotBatchRender } from '../api/actions';
import { FALLBACK_GEN_MODELS } from '../api/studioHelpers';
import { apiFetch } from '../../api';

function shortDur(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(2).replace(/\.00$/, '');
}

function fileLabel(file) {
  return file?.name || '';
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

export default function ShotBatchRender() {
  const { lang, cabinet } = useApp();
  const models = cabinet.models || [];
  const [motionVideo, setMotionVideo] = useState(null);
  const [modelId, setModelId] = useState(cabinet.selectedModelId || models[0]?.id || '');
  const [sceneBrief, setSceneBrief] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('');
  const [motionTimeline, setMotionTimeline] = useState('');
  const [outputAspect, setOutputAspect] = useState('9:16');
  const [seedanceVariant, setSeedanceVariant] = useState('standard');
  const [videoResolution, setVideoResolution] = useState('720p');
  const [generateAudio, setGenerateAudio] = useState(false);
  const [sceneThreshold, setSceneThreshold] = useState('0.35');
  const [maxShotsPerBatch, setMaxShotsPerBatch] = useState('4');
  const [maxBatchDurationSec, setMaxBatchDurationSec] = useState('4');
  const [minShotDurationSec, setMinShotDurationSec] = useState('0.4');
  const [faceSamples, setFaceSamples] = useState('6');
  const [waveModelId, setWaveModelId] = useState('nano-banana-pro');
  const [busy, setBusy] = useState(false);
  const [jobAccepted, setJobAccepted] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!modelId && models[0]?.id) setModelId(models[0].id);
  }, [modelId, models]);

  const canRun = motionVideo && modelId && !busy;
  const batches = result?.batch_outputs || [];
  const plan = result?.plan || null;
  const summary = useMemo(() => {
    if (!plan?.resolved_batches) return [];
    return plan.resolved_batches;
  }, [plan]);

  const onRun = async () => {
    if (!canRun) return;
    setBusy(true);
    setJobAccepted(null);
    setJobStatus(null);
    setResult(null);
    cabinet.setError(null);
    try {
      const data = await runShotBatchRender(
        {
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
          waveModelId,
        },
        {
          onStatus: (status) => setJobStatus(status),
        },
      );
      setJobAccepted(data.accepted || null);
      setResult(data.result || null);
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const buttonStyle = {
    background: color.lime,
    color: color.limeInk,
    fontWeight: 800,
    fontSize: 13,
    borderRadius: 10,
    padding: '11px 16px',
    cursor: canRun ? 'pointer' : 'not-allowed',
    opacity: canRun ? 1 : 0.55,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  return (
    <Fade data-screen-label="Shot-batch render">
      <div style={{ maxWidth: 1240, margin: '0 auto' }}>
        <BackLink onClick={() => window.location.assign('/workspace/video')}>
          {lang === 'ru' ? 'Назад в видео' : 'Back to video'}
        </BackLink>

        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 6 }}>
            {lang === 'ru' ? 'Shot-batch render' : 'Shot-batch render'}
          </PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>
            {lang === 'ru'
              ? 'Скрытый экран полного shot-batch pipeline: планирование, opening-кадры по батчам, batch video results и итоговая склейка.'
              : 'Hidden full shot-batch pipeline screen.'}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 420px) 1fr', gap: 16 }}>
          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <NoteBlock>
              {lang === 'ru'
                ? 'Это скрытый UI для проверки будущего shot-batch motion control. Один запуск строит план, рендерит батчи по отдельности и склеивает итог. Большой prompt вручную не нужен: если scene brief пустой, используется встроенный motion-control шаблон.'
                : 'Hidden UI for future shot-batch motion control.'}
            </NoteBlock>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                {lang === 'ru' ? 'ПЕРСОНАЖ' : 'MODEL'}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {models.map((m) => (
                  <SelectPill
                    key={m.id}
                    on={String(modelId) === String(m.id)}
                    onClick={() => setModelId(m.id)}
                    style={{ maxWidth: '100%' }}
                  >
                    {m.name}
                  </SelectPill>
                ))}
              </div>
              {!models.length && (
                <div style={{ marginTop: 6, fontSize: 12, color: color.textMuted }}>
                  {lang === 'ru' ? 'Нет доступных персонажей.' : 'No models available.'}
                </div>
              )}
            </div>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>MOTION VIDEO</div>
              <input type="file" accept="video/*" onChange={(e) => setMotionVideo(e.target.files?.[0] || null)} />
              {motionVideo && <div style={{ marginTop: 6, fontSize: 12, color: color.textDim }}>{fileLabel(motionVideo)}</div>}
            </div>

            <Field
              label={lang === 'ru' ? 'Scene brief (необязательно)' : 'Scene brief (optional)'}
              value={sceneBrief}
              onChange={(e) => setSceneBrief(e.target.value)}
              area
              rows={3}
              placeholder={
                lang === 'ru'
                  ? 'Можно оставить пустым: тогда используем встроенный шаблон. Если нужно, коротко допишите что должно происходить.'
                  : 'Optional. Leave empty to use the built-in template.'
              }
            />
            <Field
              label="negative_prompt"
              value={negativePrompt}
              onChange={(e) => setNegativePrompt(e.target.value)}
              area
              rows={2}
            />
            <Field
              label="motion_timeline"
              value={motionTimeline}
              onChange={(e) => setMotionTimeline(e.target.value)}
              area
              rows={3}
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <Field label="output_aspect" value={outputAspect} onChange={(e) => setOutputAspect(e.target.value)} />
              <Field label="scene_threshold" value={sceneThreshold} onChange={(e) => setSceneThreshold(e.target.value)} />
              <Field label="max_shots_per_batch" value={maxShotsPerBatch} onChange={(e) => setMaxShotsPerBatch(e.target.value)} />
              <Field label="max_batch_duration_sec" value={maxBatchDurationSec} onChange={(e) => setMaxBatchDurationSec(e.target.value)} />
              <Field label="min_shot_duration_sec" value={minShotDurationSec} onChange={(e) => setMinShotDurationSec(e.target.value)} />
              <Field label="face_samples" value={faceSamples} onChange={(e) => setFaceSamples(e.target.value)} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                {lang === 'ru' ? 'Разрешение видео' : 'Video resolution'}
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
                <SelectPill on={seedanceVariant === 'standard'} onClick={() => setSeedanceVariant('standard')}>2.0</SelectPill>
                <SelectPill on={seedanceVariant === 'seedance_25'} onClick={() => setSeedanceVariant('seedance_25')}>2.5</SelectPill>
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                {lang === 'ru' ? 'Модель картинок (opening)' : 'Image model (opening)'}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {(cabinet.genModels?.length ? cabinet.genModels : FALLBACK_GEN_MODELS).map((m) => (
                  <SelectPill key={m.id} on={waveModelId === m.id} onClick={() => setWaveModelId(m.id)}>
                    {m.label || m.name || m.id}
                  </SelectPill>
                ))}
              </div>
            </div>

            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={generateAudio} onChange={(e) => setGenerateAudio(e.target.checked)} />
              generate_audio
            </label>

            <Hoverable style={buttonStyle} hover={{ filter: canRun ? 'brightness(1.05)' : 'none' }} onClick={onRun}>
              {busy ? (lang === 'ru' ? 'Рендерим батчи…' : 'Rendering…') : lang === 'ru' ? 'Run shot-batch' : 'Run shot-batch'}
            </Hoverable>
          </Panel>

          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 520 }}>
            <div style={{ fontSize: 11, color: color.textMuted }}>RESULT</div>

            {!jobAccepted && !result && (
              <NoteBlock>
                {lang === 'ru'
                  ? 'После запуска здесь появятся job status, план батчей, opening-кадры по каждому батчу, batch video URLs и итоговый stitched MP4.'
                  : 'Run the pipeline to see plan, frames and videos.'}
              </NoteBlock>
            )}

            {jobAccepted && (
              <div
                style={{
                  border: `1px solid ${line.soft}`,
                  borderRadius: 10,
                  padding: '10px 12px',
                  background: color.bgPanel,
                  fontSize: 12,
                }}
              >
                <div style={{ fontWeight: 800 }}>job {jobAccepted.job_id}</div>
                <div style={{ color: color.textDim, marginTop: 3 }}>
                  type {jobAccepted.job_type} · status {jobStatus?.status || (busy ? 'running' : result ? 'completed' : 'pending')}
                </div>
                {!!jobStatus?.error_message && (
                  <div style={{ color: '#fca5a5', marginTop: 4 }}>{jobStatus.error_message}</div>
                )}
              </div>
            )}

            {!!summary.length && (
              <div style={{ display: 'grid', gap: 8 }}>
                {summary.map((rb) => (
                  <div
                    key={`summary-${rb.id}`}
                    style={{
                      border: `1px solid ${line.soft}`,
                      borderRadius: 10,
                      padding: '10px 12px',
                      background: color.bgPanel,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 800, marginBottom: 3 }}>
                      Batch {rb.id} → {rb.resolution_action}
                    </div>
                    <div style={{ color: color.textDim }}>
                      shots {String((rb.effective_shot_ids || []).join(',')) || '—'} · dur {shortDur(rb.effective_duration)}s · object {rb.object_risk_level || '—'}
                    </div>
                    <div style={{ color: color.textMuted, marginTop: 4 }}>{rb.reason}</div>
                  </div>
                ))}
              </div>
            )}

            {!!batches.length && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 12 }}>
                {batches.map((item) => (
                  <div
                    key={`batch-${item.batch_id}`}
                    style={{
                      border: `1px solid ${line.soft}`,
                      borderRadius: 12,
                      padding: 12,
                      background: color.bgPanel,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 10,
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 800 }}>Batch {item.batch_id}</div>
                      <div style={{ fontSize: 12, color: color.textDim, marginTop: 3 }}>
                        {item.resolution_action} · {shortDur(item.effective_duration)}s · object {item.object_risk_level || '—'}
                      </div>
                    </div>

                    {(item.opening_frame_preview_url || item.opening_frame_public_url || item.opening_frame_endpoint) && (
                      <AuthMedia
                        as="img"
                        src={
                          item.opening_frame_preview_url
                          || item.opening_frame_public_url
                          || item.opening_frame_endpoint
                        }
                        alt={`batch-${item.batch_id}-opening`}
                        style={{
                          width: '100%',
                          maxWidth: 180,
                          aspectRatio: '9 / 16',
                          objectFit: 'cover',
                          borderRadius: 10,
                          border: `1px solid ${line.soft}`,
                          background: color.bg,
                        }}
                      />
                    )}

                    {!!item.video_url && (
                      <AuthMedia
                        as="video"
                        src={item.rendered_batch_url || item.rendered_batch_endpoint || item.video_url}
                        style={{
                          width: '100%',
                          borderRadius: 10,
                          border: `1px solid ${line.soft}`,
                          background: '#000',
                        }}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {(result?.stitched_output_url || result?.stitched_output_endpoint) && (
              <div style={{ display: 'grid', gap: 8 }}>
                <div style={{ fontSize: 11, color: color.textMuted }}>
                  {lang === 'ru' ? 'ИТОГОВАЯ СКЛЕЙКА' : 'STITCHED OUTPUT'}
                </div>
                <AuthMedia
                  as="video"
                  src={result.stitched_output_url || result.stitched_output_endpoint}
                  style={{
                    width: '100%',
                    maxWidth: 420,
                    borderRadius: 12,
                    border: `1px solid ${line.soft}`,
                    background: '#000',
                  }}
                />
              </div>
            )}

            {!!result && (
              <textarea
                readOnly
                value={JSON.stringify(result, null, 2)}
                style={{
                  width: '100%',
                  minHeight: 280,
                  resize: 'vertical',
                  background: color.bgPanel,
                  color: color.text,
                  border: `1px solid ${line.soft}`,
                  borderRadius: 10,
                  padding: 12,
                  fontFamily: font.mono,
                  fontSize: 12,
                  lineHeight: 1.5,
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
