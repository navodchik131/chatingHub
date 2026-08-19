import { useMemo, useState } from 'react';

import { Fade, Field, NoteBlock, PageTitle, Panel, BackLink } from '../components/ui';
import Hoverable from '../components/Hoverable';
import { color, line, font } from '../styles/tokens';
import { useApp } from '../hooks/useApp';
import { runShotBatchPlan } from '../api/actions';

export default function ShotBatchPlan() {
  const { lang, cabinet } = useApp();
  const [motionVideo, setMotionVideo] = useState(null);
  const [sceneThreshold, setSceneThreshold] = useState('0.35');
  const [maxShotsPerBatch, setMaxShotsPerBatch] = useState('4');
  const [maxBatchDurationSec, setMaxBatchDurationSec] = useState('12');
  const [minShotDurationSec, setMinShotDurationSec] = useState('0.4');
  const [faceSamples, setFaceSamples] = useState('6');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const canRun = motionVideo && !busy;

  const brief = useMemo(() => {
    if (!result?.batches) return [];
    return result.batches.map((b) => ({
      id: b.id,
      shots: (b.shot_ids || []).length,
      dur: b.duration,
      hasSubject: b.has_subject,
      anchorOk: b.identity_anchor_visible,
      risky: b.risky,
    }));
  }, [result]);

  const onRun = async () => {
    if (!canRun) return;
    setBusy(true);
    cabinet.setError(null);
    try {
      const data = await runShotBatchPlan({
        motionVideo,
        sceneThreshold: Number(sceneThreshold),
        maxShotsPerBatch: Number(maxShotsPerBatch),
        maxBatchDurationSec: Number(maxBatchDurationSec),
        minShotDurationSec: Number(minShotDurationSec),
        faceSamples: Number(faceSamples),
      });
      setResult(data);
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
    <Fade data-screen-label="Shot-batch plan">
      <div style={{ maxWidth: 1120, margin: '0 auto' }}>
        <BackLink onClick={() => window.location.assign('/workspace/video')}>
          {lang === 'ru' ? 'Назад в видео' : 'Back to video'}
        </BackLink>

        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 6 }}>
            {lang === 'ru' ? 'Shot-batch план' : 'Shot-batch plan'}
          </PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>
            {lang === 'ru'
              ? 'Заливаете motion reference видео — получаете JSON с найденными шотами и батчами (subject_visible через face-detect).'
              : 'Upload a motion reference video — get JSON with shots and batches (subject_visible via face-detect).'}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) 1fr', gap: 16 }}>
          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <NoteBlock>
              {lang === 'ru'
                ? 'Это отладка шага “планировщик” перед реальным рендером. JSON можно использовать, чтобы проверить, что split rules попали в спеку.'
                : 'Debug step before actual rendering. JSON helps validate split rules.'}
            </NoteBlock>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>MOTION VIDEO</div>
              <input type="file" accept="video/*" onChange={(e) => setMotionVideo(e.target.files?.[0] || null)} />
              {motionVideo && <div style={{ marginTop: 6, fontSize: 12, color: color.textDim }}>{motionVideo.name}</div>}
            </div>

            <Field label="scene_threshold" value={sceneThreshold} onChange={(e) => setSceneThreshold(e.target.value)} />
            <Field label="max_shots_per_batch" value={maxShotsPerBatch} onChange={(e) => setMaxShotsPerBatch(e.target.value)} />
            <Field label="max_batch_duration_sec" value={maxBatchDurationSec} onChange={(e) => setMaxBatchDurationSec(e.target.value)} />
            <Field label="min_shot_duration_sec" value={minShotDurationSec} onChange={(e) => setMinShotDurationSec(e.target.value)} />
            <Field label="face_samples" value={faceSamples} onChange={(e) => setFaceSamples(e.target.value)} />

            <Hoverable style={buttonStyle} hover={{ filter: canRun ? 'brightness(1.05)' : 'none' }} onClick={onRun}>
              {busy ? (lang === 'ru' ? 'Считаем…' : 'Calculating…') : lang === 'ru' ? 'Build plan' : 'Build plan'}
            </Hoverable>
          </Panel>

          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 520 }}>
            <div style={{ fontSize: 11, color: color.textMuted }}>RESULT</div>
            {!result ? (
              <NoteBlock>
                {lang === 'ru'
                  ? 'Жмём Build plan — получаем JSON с shots[] и batches[].'
                  : 'Click Build plan — you get JSON with shots[] and batches[].'}
              </NoteBlock>
            ) : (
              <>
                {!!brief.length && (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {brief.map((b) => (
                      <div
                        key={b.id}
                        style={{
                          border: `1px solid ${line.soft}`,
                          borderRadius: 10,
                          padding: '10px 12px',
                          background: color.bgPanel,
                          fontSize: 12,
                        }}
                      >
                        <div style={{ fontWeight: 800, marginBottom: 3 }}>Batch {b.id}</div>
                        <div style={{ color: color.textDim }}>
                          shots {b.shots} · dur {String(b.dur).slice(0, 6)}s · subject {String(b.hasSubject)} · anchor {String(b.anchorOk)}
                          {b.risky ? ' · risky' : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <textarea
                  readOnly
                  value={JSON.stringify(result, null, 2)}
                  style={{
                    width: '100%',
                    minHeight: 360,
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
              </>
            )}
          </Panel>
        </div>
      </div>
    </Fade>
  );
}

