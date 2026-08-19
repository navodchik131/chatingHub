import { useMemo, useState } from 'react';

import { Fade, Field, NoteBlock, PageTitle, Panel, BackLink } from '../components/ui';
import Hoverable from '../components/Hoverable';
import { color, line, font } from '../styles/tokens';
import { useApp } from '../hooks/useApp';
import { runSeedanceProbe } from '../api/actions';

function fileNameList(files) {
  return Array.from(files || []).map((f) => f?.name).filter(Boolean).join(', ');
}

export default function SeedanceProbe() {
  const { lang, cabinet } = useApp();
  const [openingFrame, setOpeningFrame] = useState(null);
  const [motionVideo, setMotionVideo] = useState(null);
  const [identityImages, setIdentityImages] = useState([]);
  const [duration, setDuration] = useState('5');
  const [quality, setQuality] = useState('720p');
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [generateAudio, setGenerateAudio] = useState(false);
  const [ablate, setAblate] = useState(true);
  const [waitUntilDone, setWaitUntilDone] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const canRun = openingFrame && motionVideo && identityImages.length > 0 && !busy;
  const summary = useMemo(() => {
    if (!result?.cases) return [];
    return result.cases.map((it) => {
      const resp = it?.response || {};
      const completed = Boolean(it?.completed_url);
      const completedError = it?.completed_error ? String(it.completed_error) : '';
      return {
        name: it.case || 'case',
        statusCode: it.status_code,
        taskId: resp.id || '—',
        status: completed
          ? lang === 'ru'
            ? 'готово'
            : 'done'
          : completedError
            ? lang === 'ru'
              ? 'ошибка поллинга'
              : 'poll error'
            : (resp.status || '—'),
        completedUrl: it.completed_url || null,
      };
    });
  }, [result, lang]);

  const onRun = async () => {
    if (!canRun) return;
    setBusy(true);
    cabinet.setError(null);
    try {
      const data = await runSeedanceProbe({
        openingFrame,
        identityImages,
        motionVideo,
        duration: Number(duration) || 5,
        quality,
        aspectRatio,
        generateAudio,
        ablate,
        waitUntilDone,
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
    <Fade data-screen-label="Seedance Probe">
      <div style={{ maxWidth: 1120, margin: '0 auto' }}>
        <BackLink onClick={() => window.location.assign('/workspace/video')}>
          {lang === 'ru' ? 'Назад в видео' : 'Back to video'}
        </BackLink>
        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 6 }}>Seedance Probe</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>
            {lang === 'ru'
              ? 'Скрытый debug-экран: проверка комбинации opening frame + identity refs + motion video у текущего провайдера.'
              : 'Hidden debug screen: test opening frame + identity refs + motion video on the current provider.'}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) 1fr', gap: 16 }}>
          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <NoteBlock>
              {lang === 'ru'
                ? 'Загрузи opening frame, 1-3 identity image и motion video. Бэкенд сам отправит их в EvoLink files API и покажет сырой ответ по всем кейсам.'
                : 'Upload an opening frame, 1-3 identity images and a motion video. Backend will upload them to EvoLink files API and show raw provider responses.'}
            </NoteBlock>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>OPENING FRAME</div>
              <input type="file" accept="image/*" onChange={(e) => setOpeningFrame(e.target.files?.[0] || null)} />
              {openingFrame && <div style={{ marginTop: 6, fontSize: 12, color: color.textDim }}>{openingFrame.name}</div>}
            </div>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>IDENTITY IMAGES</div>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setIdentityImages(Array.from(e.target.files || []).slice(0, 3))}
              />
              {!!identityImages.length && (
                <div style={{ marginTop: 6, fontSize: 12, color: color.textDim }}>{fileNameList(identityImages)}</div>
              )}
            </div>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>MOTION VIDEO</div>
              <input type="file" accept="video/*" onChange={(e) => setMotionVideo(e.target.files?.[0] || null)} />
              {motionVideo && <div style={{ marginTop: 6, fontSize: 12, color: color.textDim }}>{motionVideo.name}</div>}
            </div>

            <Field label="Duration" value={duration} onChange={(e) => setDuration(e.target.value)} />
            <Field label="Quality" value={quality} onChange={(e) => setQuality(e.target.value)} />
            <Field label="Aspect ratio" value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} />

            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={generateAudio} onChange={(e) => setGenerateAudio(e.target.checked)} />
              generate_audio
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={ablate} onChange={(e) => setAblate(e.target.checked)} />
              run ablation cases
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={waitUntilDone} onChange={(e) => setWaitUntilDone(e.target.checked)} />
              {lang === 'ru' ? 'дождаться завершения' : 'wait until done'}
            </label>

            <Hoverable style={buttonStyle} hover={{ filter: canRun ? 'brightness(1.05)' : 'none' }} onClick={onRun}>
              {busy ? (lang === 'ru' ? 'Отправляем…' : 'Submitting...') : 'Run probe'}
            </Hoverable>
          </Panel>

          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 520 }}>
            <div style={{ fontSize: 11, color: color.textMuted }}>RESULT</div>
            {!result ? (
              <NoteBlock>
                {lang === 'ru'
                  ? 'После запуска здесь появятся uploaded URLs, status codes, task ids и сырой ответ провайдера.'
                  : 'Uploaded URLs, status codes, task ids and raw provider responses will appear here after running.'}
              </NoteBlock>
            ) : (
              <>
                <div style={{ display: 'grid', gap: 8 }}>
                  {summary.map((item) => (
                    <div
                      key={item.name}
                      style={{
                        border: `1px solid ${line.soft}`,
                        borderRadius: 10,
                        padding: '10px 12px',
                        background: color.bgPanel,
                        fontSize: 12,
                      }}
                    >
                      <div style={{ fontWeight: 700 }}>{item.name}</div>
                      <div style={{ color: color.textDim }}>
                        http {item.statusCode} · task {item.taskId} · status {item.status}
                        {item.completedUrl ? ` · url ok` : ''}
                      </div>
                    </div>
                  ))}
                </div>
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
