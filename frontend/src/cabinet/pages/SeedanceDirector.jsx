import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Fade } from '../components/ui';
import Hoverable from '../components/Hoverable';
import { useApp } from '../hooks/useApp';
import { composeSeedanceDirector, generateSeedanceDirectorVideo } from '../api/actions';
import { mergeEvolinkVideoPricing } from '../../studioMotionPricing';
import {
  computeDirectorComposeCreditCost,
  computeDirectorPieceCreditCost,
  estimateDirectorTotalCredits,
  formatDirectorCreditLabel,
} from '../../seedanceDirectorPricing';
import { color, font, line } from '../styles/tokens';
import SeedanceDirectorPicker from './SeedanceDirectorPicker';
import {
  BRIEF_HINTS,
  CAMERA_MODES,
  GROK_WRITE_STEPS,
  ROLE_SUGGESTIONS,
  cycleRole,
  clampDuration,
  DURATION_MAX,
  DURATION_MIN,
  parseAssumedTags,
  splitNote,
  uid,
} from './seedanceDirectorConstants';

const MAX_REFS = 10;

/** Стили pill для формата/разрешения — как в .dc.html */
function pillStyle(active) {
  return {
    flex: 1,
    textAlign: 'center',
    fontFamily: font.mono,
    fontSize: 11,
    fontWeight: 600,
    borderRadius: 9,
    padding: '8px 0',
    cursor: 'pointer',
    background: active ? 'rgba(215,244,82,.13)' : color.raised,
    border: `1px solid ${active ? 'rgba(215,244,82,.4)' : line.soft}`,
    color: active ? color.lime : color.textDim,
  };
}

function rolePillStyle(role) {
  const isFirst = role === 'first frame';
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    fontFamily: font.mono,
    fontSize: 10,
    letterSpacing: 0.4,
    padding: '3px 9px',
    borderRadius: 20,
    cursor: 'pointer',
    background: isFirst ? 'rgba(215,244,82,.12)' : 'rgba(255,255,255,.05)',
    border: `1px solid ${isFirst ? 'rgba(215,244,82,.34)' : line.mid}`,
    color: isFirst ? color.lime : color.textMid,
  };
}

function cardBorder(version, { genBusy, hasVideo }) {
  if (hasVideo) return 'rgba(215,244,82,.28)';
  if (genBusy) return 'rgba(192,132,252,.3)';
  return line.soft;
}

export default function SeedanceDirector({ embedded = false, backend = 'wavespeed' } = {}) {
  const { lang, go, isNarrow, cabinet } = useApp();
  const models = cabinet.models || [];
  const isEvolink = backend === 'evolink';
  const motionPricing = cabinet.health?.studio_motion_video_pricing;
  const evolinkPricing = mergeEvolinkVideoPricing(cabinet.health?.studio_evolink_video_pricing);
  const directorPricing = cabinet.health?.studio_seedance_director_pricing;
  const pricingOpts = useMemo(() => ({
    backend: isEvolink ? 'evolink' : 'wavespeed',
    motionPricing,
    evolinkPricing,
    directorPricing,
  }), [isEvolink, motionPricing, evolinkPricing, directorPricing]);

  const [refs, setRefs] = useState([]);
  const [brief, setBrief] = useState('');
  const [cameraMode, setCameraMode] = useState('A');
  const [duration, setDuration] = useState(15);
  const [aspect, setAspect] = useState('9:16');
  const [resolution, setResolution] = useState('720p');
  const [generateAudio, setGenerateAudio] = useState(true);
  const [modelId, setModelId] = useState(cabinet.selectedModelId || models[0]?.id || '');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busyCompose, setBusyCompose] = useState(false);
  const [busyGen, setBusyGen] = useState(null);
  const [compose, setCompose] = useState(null);
  const [rawOpen, setRawOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [editingRoleId, setEditingRoleId] = useState(null);

  const uploadRef = useRef(null);
  const toastTimer = useRef(null);

  const selectedModel = useMemo(
    () => models.find((m) => Number(m.id) === Number(modelId)) || null,
    [models, modelId],
  );

  const pieces20 = (compose?.pieces || []).filter((p) => p.version === '2.0');
  const pieces25 = (compose?.pieces || []).filter((p) => p.version === '2.5');
  const pieceCount = pieces20.length + pieces25.length;

  const canCompose = refs.length > 0 && brief.trim() && !busyCompose && !busyGen;
  const phase = busyCompose ? 'writing' : compose ? 'ready' : 'idle';
  // В embedded (Video / Sale) на десктопе сохраняем две колонки; стек только на узком экране.
  const stacked = isNarrow;

  const composeCreditCost = useMemo(
    () => computeDirectorComposeCreditCost(refs.length || 1, directorPricing),
    [refs.length, directorPricing],
  );

  const headerEstimate = useMemo(
    () => estimateDirectorTotalCredits(duration, refs.length || 1, pieceCount, {
      ...pricingOpts,
      resolution: resolution === '480p' || resolution === '720p' ? resolution : '720p',
    }),
    [duration, refs.length, pieceCount, resolution, pricingOpts, directorPricing],
  );

  const pieceDuration = useCallback((piece) => {
    const span = String(piece?.span || '');
    let dur = clampDuration(duration);
    const m = span.replace(/[–—]/g, '-').match(/([\d.]+)\s*-\s*([\d.]+)/);
    if (m) dur = Math.max(DURATION_MIN, Math.round(Number(m[2]) - Number(m[1])));
    if (piece?.version === '2.5') dur = Math.min(DURATION_MAX, Math.max(DURATION_MIN, dur));
    else dur = Math.min(15, Math.max(DURATION_MIN, dur));
    return dur;
  }, [duration]);

  const pieceCreditCost = useCallback((piece) => {
    const ver = piece?.version === '2.5' ? '2.5' : '2.0';
    const res = resolution === '480p' || resolution === '720p' ? resolution : '720p';
    return computeDirectorPieceCreditCost(pieceDuration(piece), ver, {
      ...pricingOpts,
      resolution: res,
    });
  }, [pieceDuration, pricingOpts, resolution]);

  const flash = useCallback((msg) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
  }, []);

  // EvoLink Sale: только 480p / 720p.
  useEffect(() => {
    if (!isEvolink) return;
    if (resolution !== '480p' && resolution !== '720p') setResolution('720p');
  }, [isEvolink, resolution]);

  const addUploadFiles = useCallback((fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setRefs((prev) => {
      const room = MAX_REFS - prev.length;
      if (room <= 0) return prev;
      return [
        ...prev,
        ...files.slice(0, room).map((file) => ({
          id: uid(),
          file,
          role: '',
          preview: URL.createObjectURL(file),
          source: 'upload',
        })),
      ];
    });
  }, []);

  const addModelItems = useCallback((items) => {
    setRefs((prev) => {
      const room = MAX_REFS - prev.length;
      if (room <= 0) return prev;
      return [
        ...prev,
        ...items.slice(0, room).map((item) => ({
          id: uid(),
          file: item.file,
          role: item.role,
          preview: item.preview,
          source: 'model',
          modelImageId: item.modelImageId,
        })),
      ];
    });
    setPickerOpen(false);
    flash(lang === 'ru' ? `Добавлено ${items.length} фото` : `Added ${items.length} photos`);
  }, [flash, lang]);

  const removeRef = (id) => {
    setRefs((prev) => {
      const gone = prev.find((r) => r.id === id);
      if (gone?.preview && gone.source === 'upload') {
        try {
          URL.revokeObjectURL(gone.preview);
        } catch {
          /* ignore */
        }
      }
      return prev.filter((r) => r.id !== id);
    });
  };

  const setRole = (id, role) => {
    setRefs((prev) => prev.map((r) => (r.id === id ? { ...r, role } : r)));
  };

  const onCompose = async () => {
    if (!canCompose) return;
    setBusyCompose(true);
    cabinet.setError(null);
    try {
      const data = await composeSeedanceDirector({
        images: refs.map((r) => r.file),
        roles: refs.map((r, i) => (r.role || '').trim() || `reference ${i + 1}`),
        brief: brief.trim(),
        durationSeconds: clampDuration(duration),
        aspectRatio: aspect,
        cameraMode,
      });
      setCompose(data);
      setRawOpen(false);
      flash(
        lang === 'ru'
          ? `Промпты собраны: ${(data.pieces || []).length} кусков`
          : `Prompts ready: ${(data.pieces || []).length} pieces`,
      );
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    } finally {
      setBusyCompose(false);
    }
  };

  const onGenerate = async (piece) => {
    if (!piece?.prompt || !refs.length) return;
    const key = `${piece.version}_${piece.piece_id}`;
    setBusyGen(key);
    cabinet.setError(null);
    try {
      const span = String(piece.span || '');
      let dur = clampDuration(duration);
      const m = span.replace(/[–—]/g, '-').match(/([\d.]+)\s*-\s*([\d.]+)/);
      if (m) dur = Math.max(DURATION_MIN, Math.round(Number(m[2]) - Number(m[1])));
      if (piece.version === '2.5') dur = Math.min(DURATION_MAX, Math.max(DURATION_MIN, dur));
      else dur = Math.min(15, Math.max(DURATION_MIN, dur));

      // Задача уходит в фон — карточка в архиве появится сразу, результат подтянется poll'ом.
      void cabinet.refreshArchivePending?.();
      const data = await generateSeedanceDirectorVideo({
        images: refs.map((r) => r.file),
        roles: refs.map((r, i) => (r.role || '').trim() || `reference ${i + 1}`),
        prompt: piece.prompt,
        version: piece.version,
        durationSeconds: dur,
        aspectRatio: aspect,
        resolution,
        generateAudio,
        videoBackend: isEvolink ? 'evolink' : 'wavespeed',
        pieceId: piece.piece_id,
      });
      setCompose((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          pieces: (prev.pieces || []).map((p) =>
            p.version === piece.version && p.piece_id === piece.piece_id
              ? {
                ...p,
                video_url: data.video_url,
                last_generate: data,
                job_id: data.accepted?.job_id ?? data.job_id ?? p.job_id,
                generation_id: data.generation_id ?? data.accepted?.generation_id ?? p.generation_id,
              }
              : p,
          ),
        };
      });
      void cabinet.refreshArchivePending?.();
      void cabinet.refreshArchiveFull?.();
      flash(lang === 'ru' ? 'Видео готово' : 'Video ready');
    } catch (e) {
      // При таймауте poll видео могло уже сохраниться на сервере.
      void cabinet.refreshArchivePending?.();
      void cabinet.refreshArchiveFull?.();
      const msg = e?.message || String(e);
      if (/превышено время ожидания|timeout|504|gateway/i.test(msg)) {
        cabinet.setError(
          lang === 'ru'
            ? 'Генерация заняла слишком много времени, но видео могло уже сохраниться — проверьте «Последние видео».'
            : 'Generation took too long, but the video may already be saved — check Latest videos.',
        );
      } else {
        cabinet.setError(msg);
      }
    } finally {
      setBusyGen(null);
    }
  };

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text || '');
      flash(lang === 'ru' ? 'Скопировано' : 'Copied');
    } catch {
      cabinet.setError(lang === 'ru' ? 'Не удалось скопировать' : 'Copy failed');
    }
  };

  const stepDefs = [
    {
      label: lang === 'ru' ? 'Референсы' : 'References',
      meta: `${refs.length} ${lang === 'ru' ? 'фото' : 'photos'}`,
      done: refs.length > 0,
    },
    {
      label: lang === 'ru' ? 'Бриф' : 'Brief',
      meta: brief.trim() ? (lang === 'ru' ? 'заполнен' : 'filled') : (lang === 'ru' ? 'пусто' : 'empty'),
      done: brief.trim().length > 0,
    },
    {
      label: lang === 'ru' ? 'Промпты' : 'Prompts',
      meta:
        phase === 'ready'
          ? `${pieceCount} ${lang === 'ru' ? 'куска' : 'pieces'}`
          : phase === 'writing'
            ? 'Grok…'
            : lang === 'ru'
              ? 'ожидание'
              : 'waiting',
      done: phase === 'ready',
    },
  ];
  const activeStep = stepDefs.findIndex((s) => !s.done);

  const assumedTags = parseAssumedTags(compose?.assumed);

  const renderPieceCard = (p, idx, total, version) => {
    const key = `${p.version}_${p.piece_id}`;
    const genBusy = busyGen === key;
    const hasVideo = !!p.video_url;
    const limit = version === '2.5' ? 30 : 15;

    return (
      <div
        key={key}
        style={{
          borderRadius: 18,
          overflow: 'hidden',
          background: '#101114',
          border: `1px solid ${cardBorder(version, { genBusy, hasVideo })}`,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
            padding: '14px 16px',
            borderBottom: `1px solid ${line.hair}`,
          }}
        >
          <div
            style={{
              width: 30,
              height: 30,
              flex: 'none',
              borderRadius: 10,
              display: 'grid',
              placeItems: 'center',
              fontFamily: font.mono,
              fontSize: 12,
              fontWeight: 600,
              background: hasVideo
                ? 'rgba(215,244,82,.14)'
                : genBusy
                  ? 'rgba(192,132,252,.14)'
                  : 'rgba(255,255,255,.05)',
              color: hasVideo ? color.lime : genBusy ? color.purple : color.textDim,
            }}
          >
            {p.piece_id}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>
              Seedance {version} · {lang === 'ru' ? 'кусок' : 'piece'} {idx + 1}/{total}
            </div>
            <div style={{ fontFamily: font.mono, fontSize: 10, color: color.textMuted, marginTop: 2 }}>
              {p.span || '—'} · {aspect} · {resolution}
            </div>
          </div>
          <div style={{ flex: 1 }} />
          <div
            style={{
              fontFamily: font.mono,
              fontSize: 9,
              letterSpacing: 0.8,
              padding: '2px 8px',
              borderRadius: 20,
              whiteSpace: 'nowrap',
              color: hasVideo ? color.lime : genBusy ? color.purple : color.textMuted,
              background: hasVideo
                ? 'rgba(215,244,82,.12)'
                : genBusy
                  ? 'rgba(192,132,252,.12)'
                  : 'rgba(255,255,255,.05)',
              border: `1px solid ${
                hasVideo
                  ? 'rgba(215,244,82,.32)'
                  : genBusy
                    ? 'rgba(192,132,252,.32)'
                    : line.soft
              }`,
            }}
          >
            {hasVideo
              ? lang === 'ru'
                ? 'готово'
                : 'done'
              : genBusy
                ? lang === 'ru'
                  ? 'рендер'
                  : 'rendering'
                : lang === 'ru'
                  ? 'промпт готов'
                  : 'prompt ready'}
          </div>
        </div>

        {p.start_frame ? (
          <div style={{ padding: '8px 16px 0', fontSize: 12, color: color.textDim }}>
            Start frame: {p.start_frame}
          </div>
        ) : null}

        <div style={{ position: 'relative' }}>
          <pre
            style={{
              margin: 0,
              padding: '15px 16px 16px',
              fontFamily: font.mono,
              fontSize: 11,
              lineHeight: 1.75,
              color: '#BFCF9B',
              whiteSpace: 'pre-wrap',
              maxHeight: 250,
              overflow: 'auto',
              background: '#0C0D10',
            }}
          >
            {p.prompt || ''}
          </pre>
          <Hoverable
            onClick={() => copyText(p.prompt)}
            style={{
              position: 'absolute',
              top: 10,
              right: 12,
              fontFamily: font.mono,
              fontSize: 9.5,
              letterSpacing: 0.6,
              padding: '5px 10px',
              borderRadius: 8,
              background: 'rgba(10,11,13,.82)',
              border: `1px solid ${line.mid}`,
              color: color.textDim,
              cursor: 'pointer',
            }}
          >
            COPY
          </Hoverable>
        </div>

        {genBusy ? (
          <div
            style={{
              padding: '14px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              borderTop: `1px solid ${line.hair}`,
            }}
          >
            <div
              style={{
                flex: 1,
                height: 5,
                borderRadius: 3,
                background: 'rgba(192,132,252,.14)',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: '45%',
                  borderRadius: 3,
                  background: 'linear-gradient(90deg,rgba(192,132,252,0),#C084FC,rgba(192,132,252,0))',
                  animation: 'sdSweep 1.5s ease-in-out infinite',
                }}
              />
            </div>
            <div style={{ fontFamily: font.mono, fontSize: 10, color: color.purple }}>
              {lang === 'ru' ? 'рендер · ~90 c' : 'render · ~90s'}
            </div>
          </div>
        ) : null}

        {hasVideo ? (
          <div
            style={{
              padding: '14px 16px 16px',
              borderTop: `1px solid ${line.hair}`,
              display: 'flex',
              gap: 14,
              flexWrap: 'wrap',
            }}
          >
            <video
              src={p.video_url}
              controls
              style={{
                width: 132,
                height: 196,
                flex: 'none',
                borderRadius: 12,
                objectFit: 'cover',
                background: '#15171B',
              }}
            />
            <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 9 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: color.lime }}>
                ✓ {lang === 'ru' ? 'Видео готово' : 'Video ready'}
              </div>
              <div style={{ fontFamily: font.mono, fontSize: 10, color: color.textMuted, lineHeight: 1.6 }}>
                seedance {version} · {resolution} · {aspect} ·{' '}
                {generateAudio ? (lang === 'ru' ? 'со звуком' : 'with audio') : lang === 'ru' ? 'без звука' : 'silent'}
              </div>
              <a
                href={p.video_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontFamily: font.mono,
                  fontSize: 10,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  display: 'block',
                  color: color.lime,
                }}
              >
                {p.video_url}
              </a>
              <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 2 }}>
                <Hoverable
                  onClick={() => {
                    const a = document.createElement('a');
                    a.href = p.video_url;
                    a.download = `seedance-${version}-${p.piece_id}.mp4`;
                    a.click();
                  }}
                  style={ghostBtn()}
                >
                  {lang === 'ru' ? 'Скачать' : 'Download'}
                </Hoverable>
                <Hoverable onClick={() => onGenerate(p)} style={purpleBtn()}>
                  {lang === 'ru' ? 'Ещё дубль' : 'Another take'}
                </Hoverable>
              </div>
            </div>
          </div>
        ) : (
          <div
            style={{
              padding: '12px 16px',
              borderTop: `1px solid ${line.hair}`,
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              flexWrap: 'wrap',
            }}
          >
            <Hoverable
              onClick={() => onGenerate(p)}
              style={{
                fontSize: 11.5,
                fontWeight: 800,
                borderRadius: 9,
                padding: '9px 16px',
                background: color.lime,
                border: `1px solid ${color.lime}`,
                color: color.limeInk,
                cursor: genBusy || busyCompose ? 'not-allowed' : 'pointer',
                opacity: genBusy || busyCompose ? 0.55 : 1,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span>{lang === 'ru' ? 'Сгенерировать видео' : 'Generate video'}</span>
              <span style={{ fontFamily: font.mono, fontSize: 10, fontWeight: 600, opacity: 0.85 }}>
                {formatDirectorCreditLabel(pieceCreditCost(p), lang === 'ru' ? 'ru' : 'en')}
              </span>
            </Hoverable>
            <Hoverable onClick={() => copyText(p.prompt)} style={ghostBtn()}>
              {lang === 'ru' ? 'Копировать' : 'Copy'}
            </Hoverable>
            <div style={{ flex: 1 }} />
            <div style={{ fontFamily: font.mono, fontSize: 10, color: color.textMuted }}>
              {version === '2.0'
                ? isEvolink
                  ? lang === 'ru'
                    ? 'Fast I2V · EvoLink'
                    : 'Fast I2V · EvoLink'
                  : lang === 'ru'
                    ? 'Fast · WaveSpeed'
                    : 'Fast · WaveSpeed'
                : isEvolink
                  ? lang === 'ru'
                    ? '2.5 I2V · EvoLink'
                    : '2.5 I2V · EvoLink'
                  : lang === 'ru'
                    ? '2.5 T2V · WaveSpeed'
                    : '2.5 T2V · WaveSpeed'}{' '}
              · {lang === 'ru' ? 'лимит' : 'limit'} {limit}s
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderVersionSection = (version, list, tone) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <div
          style={{
            fontFamily: font.mono,
            fontSize: 10,
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 9,
            background: version === '2.0' ? 'rgba(215,244,82,.12)' : 'rgba(192,132,252,.12)',
            color: tone,
            border: `1px solid ${version === '2.0' ? 'rgba(215,244,82,.3)' : 'rgba(192,132,252,.3)'}`,
          }}
        >
          {version}
        </div>
        <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 15 }}>
          Seedance {version}
        </div>
        <div style={{ fontFamily: font.mono, fontSize: 10, color: color.textMuted }}>
          {list.length
            ? `${list.length} ${lang === 'ru' ? (list.length === 1 ? 'кусок' : 'куска') : list.length === 1 ? 'piece' : 'pieces'} · ${lang === 'ru' ? 'лимит' : 'limit'} ${version === '2.5' ? 30 : 15} c`
            : lang === 'ru'
              ? 'нет промптов'
              : 'no prompts'}
        </div>
        <div style={{ flex: 1, height: 1, background: line.hair }} />
      </div>
      {!list.length ? (
        <div style={{ fontSize: 13, color: color.textDim }}>
          {lang === 'ru'
            ? 'Grok не вернул промпты для этой версии. Нажмите «Собрать промпты» ещё раз.'
            : 'Grok did not return prompts for this version. Run compose again.'}
        </div>
      ) : (
        list.map((p, i) => renderPieceCard(p, i, list.length, version))
      )}
    </div>
  );

  return (
    <Fade data-screen-label="Seedance Director">
      <style>{`
        @keyframes sdSpin { to { transform: rotate(360deg); } }
        @keyframes sdPulse { 0%,100%{opacity:.35} 50%{opacity:1} }
        @keyframes sdSweep { 0%{transform:translateX(-110%)} 100%{transform:translateX(240%)} }
      `}</style>

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: embedded ? (stacked ? 'auto' : 'min(72vh, 780px)') : 'calc(100vh - 48px)',
          margin: embedded ? 0 : stacked ? 0 : '-24px -28px 0',
        }}
      >
        {/* Верхняя шапка страницы — скрыта при встраивании в Video / Seedance Sale */}
        {!embedded && (
        <div
          style={{
            flex: 'none',
            borderBottom: `1px solid ${line.hair}`,
            background: 'rgba(13,14,17,.86)',
            backdropFilter: 'blur(12px)',
            padding: stacked ? '14px 16px 12px' : '16px 28px 14px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
            <Hoverable
              onClick={go('video')}
              style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}
              hover={{ color: color.text }}
            >
              ← {lang === 'ru' ? 'Видео' : 'Video'}
            </Hoverable>
            <div style={{ width: 1, height: 16, background: line.mid }} />
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 20, letterSpacing: -0.4 }}>
              Seedance Director
            </div>
            <span
              style={{
                fontFamily: font.mono,
                fontSize: 9,
                letterSpacing: 1,
                background: 'rgba(192,132,252,.14)',
                color: color.purple,
                border: '1px solid rgba(192,132,252,.32)',
                padding: '3px 8px',
                borderRadius: 20,
              }}
            >
              BETA
            </span>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: font.mono, fontSize: 10.5, color: color.textGhost }}>
              <span>grok · seedance 2.0 / 2.5</span>
              <span style={{ color: color.textGhost }}>·</span>
              <span style={{ color: color.textDim }}>
                {phase === 'ready'
                  ? lang === 'ru'
                    ? 'промпты собраны'
                    : 'prompts ready'
                  : phase === 'writing'
                    ? lang === 'ru'
                      ? 'grok пишет…'
                      : 'grok writing…'
                    : lang === 'ru'
                      ? 'черновик'
                      : 'draft'}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                background: '#15171B',
                border: `1px solid ${line.soft}`,
                borderRadius: 10,
                padding: '7px 12px',
              }}
            >
              <span style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1.4, color: color.textGhost }}>
                {lang === 'ru' ? 'ОЦЕНКА' : 'EST.'}
              </span>
              <span style={{ fontFamily: font.display, fontWeight: 600, fontSize: 13, color: color.lime }}>
              {formatDirectorCreditLabel(headerEstimate, lang === 'ru' ? 'ru' : 'en')}
              </span>
              <span style={{ fontSize: 10.5, color: color.textGhost }}>{lang === 'ru' ? 'кр.' : 'cr.'}</span>
            </div>
          </div>
          <div style={{ fontSize: 12.5, color: color.textFaint, marginTop: 8, maxWidth: 760, lineHeight: 1.5 }}>
            {lang === 'ru'
              ? 'Опишите сцену и приложите фото. AI соберёт промпты для Seedance 2.0 / 2.5 и сгенерирует ролик.'
              : 'Describe the scene and attach photos. AI builds Seedance 2.0 / 2.5 prompts and generates video.'}
          </div>

          {/* Степпер */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginTop: 14, overflowX: 'auto' }}>
            {stepDefs.map((st, i) => {
              const isActive = i === activeStep;
              const isDone = st.done;
              return (
                <div key={st.label} style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 'none' }}>
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      flex: 'none',
                      borderRadius: 8,
                      display: 'grid',
                      placeItems: 'center',
                      fontFamily: font.mono,
                      fontSize: 10,
                      fontWeight: 600,
                      background: isDone
                        ? 'rgba(215,244,82,.14)'
                        : isActive
                          ? 'rgba(255,255,255,.07)'
                          : 'rgba(255,255,255,.03)',
                      color: isDone ? color.lime : isActive ? color.text : color.textGhost,
                      border: `1px solid ${
                        isDone
                          ? 'rgba(215,244,82,.34)'
                          : isActive
                            ? line.mid
                            : line.hair
                      }`,
                    }}
                  >
                    {isDone ? '✓' : i + 1}
                  </div>
                  <div>
                    <div
                      style={{
                        fontSize: 12.5,
                        fontWeight: isActive ? 800 : 600,
                        color: isDone ? color.lime : isActive ? color.text : color.textGhost,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {st.label}
                    </div>
                    <div
                      style={{
                        fontFamily: font.mono,
                        fontSize: 9,
                        letterSpacing: 0.8,
                        color: color.textGhost,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {st.meta}
                    </div>
                  </div>
                  {i < stepDefs.length - 1 ? (
                    <div
                      style={{
                        width: 36,
                        height: 1.5,
                        borderRadius: 2,
                        margin: '0 12px 0 6px',
                        background: isDone ? 'rgba(215,244,82,.35)' : line.hair,
                        flex: 'none',
                      }}
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
        )}

        {/* Две колонки */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: stacked ? 'column' : 'row',
            overflow: stacked ? 'auto' : 'hidden',
          }}
        >
          {/* Левая колонка — настройка */}
          <div
            style={{
              width: stacked ? '100%' : 372,
              flex: 'none',
              borderRight: stacked ? 'none' : `1px solid ${line.hair}`,
              borderBottom: stacked ? `1px solid ${line.hair}` : 'none',
              background: color.bg,
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
            }}
          >
            <div
              style={{
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                padding: stacked ? '16px 16px 8px' : '20px 20px 8px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              <div style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 2, color: color.textMuted }}>
                {lang === 'ru' ? 'НАСТРОЙКА СЪЁМКИ' : 'SHOOT SETUP'}
              </div>

              {/* Фото-референсы */}
              <div style={{ background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 1.8, color: color.textMuted }}>
                    {lang === 'ru' ? 'ФОТО-РЕФЕРЕНСЫ' : 'PHOTO REFERENCES'}
                  </div>
                  <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.lime }}>
                    {refs.length} / {MAX_REFS}
                  </div>
                </div>

                <input
                  ref={uploadRef}
                  type="file"
                  accept="image/*"
                  multiple
                  hidden
                  onChange={(e) => {
                    addUploadFiles(e.target.files);
                    e.target.value = '';
                  }}
                />
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    addUploadFiles(e.dataTransfer.files);
                  }}
                  onClick={() => uploadRef.current?.click()}
                  style={{
                    border: `1px dashed ${line.dashed}`,
                    borderRadius: 13,
                    padding: 14,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    cursor: 'pointer',
                    background: 'rgba(255,255,255,.015)',
                  }}
                >
                  <span style={{ fontSize: 20, color: color.textDim }}>↑</span>
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 700 }}>
                      {lang === 'ru' ? 'Перетащите фото сюда' : 'Drop photos here'}
                    </div>
                    <div style={{ fontSize: 11, color: color.textMuted, marginTop: 2 }}>
                      {lang === 'ru' ? 'или выберите файлы · jpg, png · до 10 шт.' : 'or pick files · jpg, png · up to 10'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <Hoverable
                    onClick={() => setPickerOpen(true)}
                    style={{
                      flex: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 7,
                      background: color.raised,
                      border: `1px solid ${line.soft}`,
                      borderRadius: 10,
                      padding: 9,
                      fontSize: 11.5,
                      fontWeight: 700,
                      color: color.textMid,
                      cursor: 'pointer',
                    }}
                    hover={{ borderColor: 'rgba(215,244,82,.4)', color: color.text }}
                  >
                    + {lang === 'ru' ? 'Из карточки персонажа' : 'From character card'}
                  </Hoverable>
                  {selectedModel ? (
                    <Hoverable
                      onClick={() => setPickerOpen(true)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        background: color.raised,
                        border: `1px solid ${line.soft}`,
                        borderRadius: 10,
                        padding: '8px 11px',
                        cursor: 'pointer',
                        flex: 'none',
                      }}
                    >
                      {(selectedModel.images || selectedModel.raw?.images || [])[0]?.url ? (
                        <img
                          src={(selectedModel.images || selectedModel.raw?.images || [])[0].url}
                          alt=""
                          style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover' }}
                        />
                      ) : null}
                      <span style={{ fontSize: 11.5, fontWeight: 700 }}>{selectedModel.name}</span>
                      <span style={{ fontSize: 9, color: color.textMuted }}>▾</span>
                    </Hoverable>
                  ) : null}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
                  {refs.map((r, idx) => (
                    <div
                      key={r.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 11,
                        background: '#17191D',
                        border: `1px solid ${line.hair}`,
                        borderRadius: 13,
                        padding: 9,
                      }}
                    >
                      <img
                        src={r.preview}
                        alt=""
                        style={{ width: 44, height: 56, flex: 'none', borderRadius: 9, objectFit: 'cover' }}
                      />
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        {editingRoleId === r.id ? (
                          <input
                            list="sd-roles"
                            autoFocus
                            value={r.role}
                            onChange={(e) => setRole(r.id, e.target.value)}
                            onBlur={() => setEditingRoleId(null)}
                            onKeyDown={(e) => e.key === 'Enter' && setEditingRoleId(null)}
                            style={{
                              width: '100%',
                              background: color.bg,
                              border: `1px solid ${line.mid}`,
                              borderRadius: 8,
                              padding: '4px 8px',
                              fontSize: 11,
                              color: color.text,
                            }}
                          />
                        ) : (
                          <Hoverable
                            onClick={() => setRole(r.id, cycleRole(r.role))}
                            onDoubleClick={() => setEditingRoleId(r.id)}
                            style={rolePillStyle(r.role || `ref ${idx + 1}`)}
                            title={lang === 'ru' ? 'Клик — сменить роль, двойной — редактировать' : 'Click cycle role, double-click edit'}
                          >
                            <span>{r.role || `reference ${idx + 1}`}</span>
                            <span style={{ opacity: 0.55, fontSize: 8 }}>▾</span>
                          </Hoverable>
                        )}
                        <div
                          style={{
                            fontFamily: font.mono,
                            fontSize: 9.5,
                            color: color.textMuted,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {r.file?.name}
                        </div>
                      </div>
                      <Hoverable
                        onClick={() => removeRef(r.id)}
                        style={{
                          width: 22,
                          height: 22,
                          flex: 'none',
                          borderRadius: 7,
                          display: 'grid',
                          placeItems: 'center',
                          fontSize: 11,
                          color: color.textMuted,
                          cursor: 'pointer',
                        }}
                        hover={{ background: 'rgba(248,113,113,.14)', color: color.red }}
                      >
                        ✕
                      </Hoverable>
                    </div>
                  ))}
                </div>
                <datalist id="sd-roles">
                  {ROLE_SUGGESTIONS.map((s) => (
                    <option key={s} value={s} />
                  ))}
                </datalist>
              </div>

              {/* Бриф */}
              <div style={{ background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 1.8, color: color.textMuted }}>
                    {lang === 'ru' ? 'БРИФ · ЧТО ПРОИСХОДИТ' : 'BRIEF · WHAT HAPPENS'}
                  </div>
                  <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>
                    {brief.trim().length} {lang === 'ru' ? 'симв.' : 'chars'}
                  </div>
                </div>
                <textarea
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  placeholder={
                    lang === 'ru'
                      ? 'Своими словами: что происходит, как двигается, как снято…'
                      : 'Plain language: what happens, how she moves, how it is filmed…'
                  }
                  style={{
                    width: '100%',
                    minHeight: 118,
                    resize: 'vertical',
                    background: '#0E0F12',
                    border: `1px solid ${line.soft}`,
                    borderRadius: 12,
                    padding: 12,
                    color: color.text,
                    fontSize: 12.5,
                    lineHeight: 1.6,
                    outline: 'none',
                    fontFamily: font.body,
                  }}
                />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 9 }}>
                  {BRIEF_HINTS.map((h) => (
                    <Hoverable
                      key={h.key}
                      onClick={() => setBrief((b) => b + (lang === 'ru' ? h.ruText : h.enText))}
                      style={{
                        fontSize: 10.5,
                        fontWeight: 600,
                        color: color.textDim,
                        background: 'rgba(255,255,255,.045)',
                        border: `1px solid ${line.soft}`,
                        borderRadius: 20,
                        padding: '4px 10px',
                        cursor: 'pointer',
                      }}
                      hover={{ color: color.lime, borderColor: 'rgba(215,244,82,.35)' }}
                    >
                      + {lang === 'ru' ? h.ru : h.en}
                    </Hoverable>
                  ))}
                </div>
              </div>

              {/* Тип съёмки */}
              <div style={{ background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16, padding: 16 }}>
                <div style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 1.8, color: color.textMuted, marginBottom: 11 }}>
                  {lang === 'ru' ? 'ТИП СЪЁМКИ' : 'CAMERA MODE'}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {CAMERA_MODES.map((m) => {
                    const on = cameraMode === m.id;
                    return (
                      <Hoverable
                        key={m.id}
                        onClick={() => setCameraMode(m.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 11,
                          padding: '10px 11px',
                          borderRadius: 12,
                          cursor: 'pointer',
                          background: on ? 'rgba(215,244,82,.07)' : 'rgba(255,255,255,.02)',
                          border: `1px solid ${on ? 'rgba(215,244,82,.32)' : line.hair}`,
                        }}
                      >
                        <div
                          style={{
                            width: 22,
                            height: 22,
                            flex: 'none',
                            borderRadius: 7,
                            display: 'grid',
                            placeItems: 'center',
                            fontFamily: font.mono,
                            fontSize: 10,
                            fontWeight: 600,
                            background: on ? 'rgba(215,244,82,.16)' : 'rgba(255,255,255,.05)',
                            color: on ? color.lime : color.textMuted,
                          }}
                        >
                          {m.id}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 12, fontWeight: on ? 800 : 600, color: on ? color.text : color.textMid }}>
                            {lang === 'ru' ? m.ru : m.en}
                          </div>
                          <div style={{ fontSize: 10.5, color: color.textMuted, marginTop: 2, lineHeight: 1.4 }}>
                            {lang === 'ru' ? m.descRu : m.descEn}
                          </div>
                        </div>
                        <div
                          style={{
                            width: 14,
                            height: 14,
                            flex: 'none',
                            borderRadius: '50%',
                            border: `1.5px solid ${on ? color.lime : 'rgba(255,255,255,.18)'}`,
                            boxShadow: on ? `inset 0 0 0 3px ${color.bg}, inset 0 0 0 10px ${color.lime}` : 'none',
                          }}
                        />
                      </Hoverable>
                    );
                  })}
                </div>
              </div>

              {/* Параметры */}
              <div
                style={{
                  background: color.surface,
                  border: `1px solid ${line.hair}`,
                  borderRadius: 16,
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 14,
                }}
              >
                <div style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 1.8, color: color.textMuted }}>
                  {lang === 'ru' ? 'ПАРАМЕТРЫ' : 'PARAMETERS'}
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim }}>
                      {lang === 'ru' ? 'Длительность' : 'Duration'}
                    </div>
                    <div style={{ fontFamily: font.display, fontSize: 14, fontWeight: 600, color: color.lime }}>
                      {duration} c
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <Hoverable
                      onClick={() => setDuration((d) => clampDuration(d - 1))}
                      style={{
                        ...stepBtn(),
                        opacity: duration <= DURATION_MIN ? 0.35 : 1,
                        pointerEvents: duration <= DURATION_MIN ? 'none' : 'auto',
                      }}
                    >
                      −
                    </Hoverable>
                    <div style={{ flex: 1, height: 6, borderRadius: 4, background: 'rgba(255,255,255,.07)', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          borderRadius: 4,
                          background: `linear-gradient(90deg, ${color.lime}, ${color.limeOlive})`,
                          width: `${Math.round(((clampDuration(duration) - DURATION_MIN) / (DURATION_MAX - DURATION_MIN)) * 100)}%`,
                          transition: 'width .25s ease',
                        }}
                      />
                    </div>
                    <Hoverable
                      onClick={() => setDuration((d) => clampDuration(d + 1))}
                      style={{
                        ...stepBtn(),
                        opacity: duration >= DURATION_MAX ? 0.35 : 1,
                        pointerEvents: duration >= DURATION_MAX ? 'none' : 'auto',
                      }}
                    >
                      +
                    </Hoverable>
                  </div>
                  <div style={{ fontSize: 10.5, color: color.textMuted, marginTop: 7, lineHeight: 1.45 }}>
                    {splitNote(duration, lang)}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, marginBottom: 7 }}>
                    {lang === 'ru' ? 'Формат' : 'Aspect'}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {['9:16', '16:9', '1:1'].map((a) => (
                      <Hoverable key={a} onClick={() => setAspect(a)} style={pillStyle(aspect === a)}>
                        {a}
                      </Hoverable>
                    ))}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, marginBottom: 7 }}>
                    {lang === 'ru' ? 'Разрешение' : 'Resolution'}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {['480p', '720p', ...(isEvolink ? [] : ['1080p'])].map((r) => (
                      <Hoverable key={r} onClick={() => setResolution(r)} style={pillStyle(resolution === r)}>
                        {r}
                      </Hoverable>
                    ))}
                  </div>
                </div>

                <Hoverable
                  onClick={() => setGenerateAudio((v) => !v)}
                  style={{ display: 'flex', alignItems: 'center', gap: 11, cursor: 'pointer', paddingTop: 2 }}
                >
                  <div
                    style={{
                      width: 38,
                      height: 22,
                      flex: 'none',
                      borderRadius: 14,
                      padding: 3,
                      display: 'flex',
                      background: generateAudio ? color.lime : 'rgba(255,255,255,.10)',
                      justifyContent: generateAudio ? 'flex-end' : 'flex-start',
                      transition: 'background .2s ease',
                    }}
                  >
                    <div
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: '50%',
                        background: generateAudio ? color.limeInk : color.textMuted,
                      }}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700 }}>
                      {lang === 'ru' ? 'Звук в кадре' : 'In-frame audio'}
                    </div>
                    <div style={{ fontSize: 10.5, color: color.textMuted, marginTop: 1 }}>
                      {lang === 'ru' ? 'микрофон телефона, room tone' : 'phone mic, room tone'}
                    </div>
                  </div>
                </Hoverable>
              </div>
            </div>

            {/* CTA снизу слева */}
            <div
              style={{
                flex: 'none',
                borderTop: `1px solid ${line.hair}`,
                background: '#0E0F12',
                padding: stacked ? '14px 16px 18px' : '14px 20px 18px',
              }}
            >
              <Hoverable
                onClick={onCompose}
                style={{
                  textAlign: 'center',
                  fontSize: 13,
                  fontWeight: 800,
                  borderRadius: 12,
                  padding: '14px 16px',
                  cursor: !canCompose ? 'not-allowed' : busyCompose ? 'progress' : 'pointer',
                  background: !canCompose
                    ? 'rgba(255,255,255,.03)'
                    : busyCompose
                      ? 'rgba(192,132,252,.12)'
                      : color.lime,
                  border: `1px solid ${
                    !canCompose ? line.hair : busyCompose ? 'rgba(192,132,252,.34)' : color.lime
                  }`,
                  color: !canCompose ? color.textGhost : busyCompose ? color.purple : color.limeInk,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                {busyCompose
                  ? lang === 'ru'
                    ? 'Grok пишет…'
                    : 'Grok writing…'
                  : compose
                    ? lang === 'ru'
                      ? 'Пересобрать промпты'
                      : 'Recompose prompts'
                    : lang === 'ru'
                      ? 'Собрать промпты'
                      : 'Compose prompts'}
                {!busyCompose && canCompose && (
                  <span style={{ marginLeft: 8, fontFamily: font.mono, fontSize: 10.5, fontWeight: 600, opacity: 0.85 }}>
                    {formatDirectorCreditLabel(composeCreditCost, lang === 'ru' ? 'ru' : 'en')}
                  </span>
                )}
              </Hoverable>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 9 }}>
                <div style={{ fontSize: 10.5, color: color.textMuted }}>
                  {canCompose
                    ? busyCompose
                      ? lang === 'ru'
                        ? 'Обычно 10–20 секунд'
                        : 'Usually 10–20 seconds'
                      : lang === 'ru'
                        ? 'Grok распишет камеру, движение и звук'
                        : 'Grok writes camera, motion and audio'
                    : lang === 'ru'
                      ? 'Нужны фото и бриф'
                      : 'Need photos and brief'}
                </div>
                {canCompose ? (
                  <div style={{ fontFamily: font.mono, fontSize: 10, color: color.textMuted }}>
                    {lang === 'ru' ? '≈ 2 кр. за сборку' : '≈ 2 cr. compose'}
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          {/* Правая колонка — результат */}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              padding: stacked ? '16px 16px 32px' : '22px 28px 40px',
              overflowY: stacked ? 'visible' : 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
              <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16, letterSpacing: -0.2 }}>
                {lang === 'ru' ? 'Результат режиссёра' : 'Director result'}
              </div>
              {compose ? (
                <span
                  style={{
                    fontFamily: font.mono,
                    fontSize: 9.5,
                    letterSpacing: 0.6,
                    color: color.textDim,
                    background: 'rgba(255,255,255,.05)',
                    border: `1px solid ${line.soft}`,
                    padding: '3px 9px',
                    borderRadius: 20,
                  }}
                >
                  grok · 2 {lang === 'ru' ? 'версии' : 'versions'} · {pieceCount} {lang === 'ru' ? 'куска' : 'pieces'}
                </span>
              ) : null}
              <div style={{ flex: 1 }} />
              {compose ? (
                <Hoverable onClick={onCompose} style={ghostBtn()} disabled={!canCompose}>
                  {lang === 'ru' ? 'Пересобрать' : 'Recompose'}
                </Hoverable>
              ) : null}
            </div>

            {phase === 'idle' && !compose ? (
              <div
                style={{
                  border: `1px dashed ${line.mid}`,
                  borderRadius: 20,
                  padding: '64px 32px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  gap: 14,
                  background: 'rgba(255,255,255,.012)',
                }}
              >
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: 16,
                    background: 'rgba(192,132,252,.10)',
                    border: '1px solid rgba(192,132,252,.24)',
                    display: 'grid',
                    placeItems: 'center',
                    color: color.purple,
                    fontSize: 22,
                  }}
                >
                  📄
                </div>
                <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16 }}>
                  {lang === 'ru'
                    ? 'Здесь появятся промпты Seedance 2.0 и 2.5'
                    : 'Seedance 2.0 and 2.5 prompts appear here'}
                </div>
                <div style={{ fontSize: 12.5, color: color.textFaint, maxWidth: 420, lineHeight: 1.6 }}>
                  {lang === 'ru'
                    ? 'Добавьте фото и опишите сцену — AI разберёт бриф по кадрам, распишет камеру, движение и звук.'
                    : 'Add photos and describe the scene — AI breaks down beats, camera, motion and sound.'}
                </div>
              </div>
            ) : null}

            {phase === 'writing' ? (
              <div
                style={{
                  border: '1px solid rgba(192,132,252,.26)',
                  borderRadius: 20,
                  padding: 28,
                  background: 'linear-gradient(120deg,rgba(192,132,252,.07),rgba(192,132,252,.015))',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 16,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 18,
                      height: 18,
                      flex: 'none',
                      borderRadius: '50%',
                      border: '2px solid rgba(192,132,252,.28)',
                      borderTopColor: color.purple,
                      animation: 'sdSpin .8s linear infinite',
                    }}
                  />
                  <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 15, color: color.purple }}>
                    {lang === 'ru' ? 'Grok пишет промпты…' : 'Grok writing prompts…'}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                  {GROK_WRITE_STEPS.map((label, i) => (
                    <div key={label.ru} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div
                        style={{
                          width: 7,
                          height: 7,
                          flex: 'none',
                          borderRadius: '50%',
                          background: color.purple,
                          opacity: i > 1 ? 0.3 : 1,
                          animation: i <= 1 ? 'sdPulse 1.3s ease-in-out infinite' : 'none',
                        }}
                      />
                      <div style={{ fontSize: 12, color: i > 1 ? color.textMuted : color.textMid }}>
                        {lang === 'ru' ? label.ru : label.en}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {compose ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {assumedTags.length ? (
                  <div
                    style={{
                      border: '1px solid rgba(56,189,248,.22)',
                      background: 'rgba(56,189,248,.05)',
                      borderRadius: 16,
                      padding: '14px 16px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
                      <span style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1.4, color: color.blue }}>
                        ASSUMED
                      </span>
                      <span style={{ fontSize: 11, color: color.textMuted }}>
                        {lang === 'ru' ? '— что AI додумал сам' : '— AI filled in gaps'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {assumedTags.map((a) => (
                        <div
                          key={a}
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            color: '#BAE6FD',
                            background: 'rgba(56,189,248,.10)',
                            border: '1px solid rgba(56,189,248,.2)',
                            borderRadius: 20,
                            padding: '4px 11px',
                          }}
                        >
                          {a}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {renderVersionSection('2.0', pieces20, color.lime)}
                {renderVersionSection('2.5', pieces25, color.purple)}

                <Hoverable
                  onClick={() => setRawOpen((v) => !v)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 9,
                    background: '#101114',
                    border: `1px solid ${line.hair}`,
                    borderRadius: 14,
                    padding: '13px 16px',
                    cursor: 'pointer',
                  }}
                  hover={{ borderColor: line.mid }}
                >
                  <span style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 1.4, color: color.textMuted }}>
                    RAW
                  </span>
                  <div style={{ flex: 1, fontSize: 12, color: color.textDim }}>
                    {lang === 'ru'
                      ? 'Сырой ответ Grok — если разбор на куски не сошёлся'
                      : 'Raw Grok reply — if piece parsing failed'}
                  </div>
                  <span style={{ fontSize: 10, color: color.textMuted }}>{rawOpen ? '▴' : '▾'}</span>
                </Hoverable>
                {rawOpen ? (
                  <pre
                    style={{
                      margin: 0,
                      background: '#0C0D10',
                      border: `1px solid ${line.hair}`,
                      borderRadius: 14,
                      padding: 16,
                      fontFamily: font.mono,
                      fontSize: 11,
                      lineHeight: 1.7,
                      color: color.textFaint,
                      whiteSpace: 'pre-wrap',
                      maxHeight: 220,
                      overflow: 'auto',
                    }}
                  >
                    {compose.raw_text || ''}
                  </pre>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {pickerOpen ? (
        <SeedanceDirectorPicker
          lang={lang}
          models={models}
          initialModelId={modelId}
          onClose={() => setPickerOpen(false)}
          onConfirm={(items, confirmedModelId) => {
            if (confirmedModelId) setModelId(confirmedModelId);
            addModelItems(items);
          }}
          onUploadDisk={addUploadFiles}
          onError={(msg) => (msg ? cabinet.setError(msg) : cabinet.setError(null))}
        />
      ) : null}

      {toast ? (
        <div
          style={{
            position: 'fixed',
            left: '50%',
            bottom: 26,
            transform: 'translateX(-50%)',
            display: 'flex',
            alignItems: 'center',
            gap: 11,
            background: '#15171B',
            border: '1px solid rgba(215,244,82,.3)',
            borderRadius: 14,
            padding: '12px 18px',
            boxShadow: '0 18px 44px rgba(0,0,0,.55)',
            zIndex: 90,
          }}
        >
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: color.lime, flex: 'none' }} />
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>{toast}</span>
        </div>
      ) : null}
    </Fade>
  );
}

function stepBtn() {
  return {
    width: 30,
    height: 30,
    flex: 'none',
    borderRadius: 9,
    background: color.raised,
    border: `1px solid ${line.soft}`,
    display: 'grid',
    placeItems: 'center',
    fontSize: 14,
    color: color.textMid,
    cursor: 'pointer',
  };
}

function ghostBtn() {
  return {
    fontSize: 11.5,
    fontWeight: 700,
    borderRadius: 9,
    padding: '8px 14px',
    background: color.raised,
    border: `1px solid ${line.soft}`,
    color: color.textMid,
    cursor: 'pointer',
  };
}

function purpleBtn() {
  return {
    fontSize: 11.5,
    fontWeight: 700,
    borderRadius: 9,
    padding: '8px 14px',
    background: 'rgba(192,132,252,.14)',
    border: '1px solid rgba(192,132,252,.34)',
    color: color.purple,
    cursor: 'pointer',
  };
}
