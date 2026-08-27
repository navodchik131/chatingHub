import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Hoverable from './Hoverable';
import { IcoFilm, IcoPlay, IcoUpload } from './Icons';
import { Eyebrow, Chip, SelectPill } from './ui';
import MotionTrimTimeline from './MotionTrimTimeline';
import { color, line, font } from '../styles/tokens';
import { refUploadStyle, cardPickStyle } from '../styles/mixins';
import { sameStudioModelId, enginesForNsfw, isUiSimplified, normalizeWaveModel } from '../api/studioHelpers';
import { photoKindShortLabel, normalizePhotoKind } from '../api/helpers';
import { quoteStudioImageCredits, formatImageCostBadge } from '../../studioImagePricing';
import {
  computeEvolinkVideoCreditCost,
  computeMotionVideoCreditCost,
  formatMotionCreditCost,
  mergeEvolinkVideoPricing,
} from '../../studioMotionPricing';
import SeedanceSaleLabel from './SeedanceSaleLabel';

function vidQualityToResolution(vidQuality) {
  const v = String(vidQuality || '1080').toLowerCase();
  if (v === '1080' || v === '1080p' || v === '4k') return '1080p';
  if (v === '480' || v === '480p') return '480p';
  return '720p';
}

function photoPickStyle(on) {
  const w = 78;
  const h = 112;
  return {
    width: w,
    height: h,
    flex: 'none',
    borderRadius: 11,
    overflow: 'hidden',
    position: 'relative',
    cursor: 'pointer',
    border: on ? '2px solid rgba(215,244,82,.75)' : `1px solid ${line.strong}`,
    boxShadow: on ? '0 0 0 1px rgba(215,244,82,.25)' : 'none',
  };
}

/** Wizard Motion Control по макету desktop/mobile Video. */
export default function MotionControlWizard({
  t,
  lang,
  s,
  setS,
  isMobile,
  cabinet,
  isEvolink = false,
  onGenerate,
}) {
  const simplifiedUi = isUiSimplified(cabinet.me);
  const videoRef = useRef(null);
  const clothingRef = useRef(null);
  const outfitUploadRef = useRef(null);
  const turnaroundUploadRef = useRef(null);

  const model = (cabinet.models || []).find((m) => sameStudioModelId(m.id, cabinet.selectedModelId));
  const modelImages = model?.images || [];
  const faceImages = modelImages.filter((im) => normalizePhotoKind(im.kind) === 'face');
  const bodyImages = modelImages.filter((im) => {
    const k = normalizePhotoKind(im.kind);
    return k === 'body' || k === 'other' || k === 'turnaround';
  });
  const basePhotos = bodyImages.length ? bodyImages : modelImages;

  const [baseImageId, setBaseImageId] = useState(null);
  const [faceImageId, setFaceImageId] = useState(null);
  const [outfitRoute, setOutfitRoute] = useState('video');
  const [outfitSource, setOutfitSource] = useState('generate');
  const [turnSource, setTurnSource] = useState('generate');
  const [dressModelId, setDressModelId] = useState(s.aiModel || 'wan-2.7');
  const [turnModelId, setTurnModelId] = useState('gpt-image-2');
  const [outfitState, setOutfitState] = useState('idle');
  const [turnState, setTurnState] = useState('idle');
  const [outfitGenId, setOutfitGenId] = useState(null);
  const [outfitPreviewUrl, setOutfitPreviewUrl] = useState('');
  const [turnaroundGenId, setTurnaroundGenId] = useState(null);
  const [turnaroundPreviewUrl, setTurnaroundPreviewUrl] = useState('');
  const [trimMode, setTrimMode] = useState('full');
  const [trimIn, setTrimIn] = useState(0);
  const [trimOut, setTrimOut] = useState(5);
  const motionVideoPreviewUrl = cabinet.uploadPreviewUrls?.['motion-video'] || '';

  const durationSec = cabinet.motionVideoDurationSec || 5;
  const imagePricing = cabinet.health?.studio_image_pricing;
  const evolinkPricing = mergeEvolinkVideoPricing(cabinet.health?.studio_evolink_video_pricing);

  useEffect(() => {
    setTrimOut(durationSec);
    if (trimIn >= durationSec) setTrimIn(0);
  }, [durationSec]);

  useEffect(() => {
    if (baseImageId == null && basePhotos[0]?.id != null) setBaseImageId(Number(basePhotos[0].id));
    if (faceImageId == null && faceImages[0]?.id != null) setFaceImageId(Number(faceImages[0].id));
  }, [cabinet.selectedModelId, basePhotos, faceImages, baseImageId, faceImageId]);

  useEffect(() => {
    setOutfitGenId(null);
    setOutfitPreviewUrl('');
    setOutfitState('idle');
    setTurnaroundGenId(null);
    setTurnaroundPreviewUrl('');
    setTurnState('idle');
  }, [cabinet.selectedModelId, cabinet.motionVideoFileId, outfitRoute, baseImageId]);

  useEffect(() => {
    setOutfitGenId(null);
    setOutfitPreviewUrl('');
    setOutfitState('idle');
    cabinet.setUploadFile('mc-outfit-upload', null);
  }, [outfitSource, cabinet.setUploadFile]);

  useEffect(() => {
    setTurnaroundGenId(null);
    setTurnaroundPreviewUrl('');
    setTurnState('idle');
    cabinet.setUploadFile('mc-turnaround-upload', null);
  }, [turnSource, cabinet.setUploadFile]);

  const dressWaveProfile = s.contentMode === 'sfw' ? 'regular' : 'nsfw';
  const dressWave = useMemo(
    () => normalizeWaveModel(dressModelId, s.contentMode === 'nsfw'),
    [dressModelId, s.contentMode],
  );
  const dressCredits = useMemo(
    () => quoteStudioImageCredits({
      waveModelId: dressWave.apiId,
      waveProfile: dressWaveProfile,
      wanEditTier: dressWave.tier,
      grokPipeline: 'none',
      studioMode: 'photo_edit',
      workflow: false,
    }, imagePricing),
    [dressWave, dressWaveProfile, imagePricing],
  );
  const turnWave = useMemo(
    () => normalizeWaveModel(turnModelId, s.contentMode === 'nsfw'),
    [turnModelId, s.contentMode],
  );
  const turnCredits = useMemo(
    () => quoteStudioImageCredits({
      waveModelId: turnWave.apiId,
      waveProfile: dressWaveProfile,
      wanEditTier: turnWave.tier,
      grokPipeline: 'none',
      studioMode: 'photo_edit',
      workflow: false,
    }, imagePricing),
    [turnWave, dressWaveProfile, imagePricing],
  );

  const clipDuration = trimMode === 'part'
    ? Math.max(0.5, trimOut - trimIn)
    : durationSec;

  const videoCredits = useMemo(() => {
    const variant = s.vidSeedanceVariant || 'standard';
    const resolution = vidQualityToResolution(s.vidQuality);
    const refDur = cabinet.motionVideoFileId ? Math.ceil(clipDuration) : null;
    if (isEvolink) {
      return computeEvolinkVideoCreditCost(clipDuration, Boolean(cabinet.motionVideoFileId), evolinkPricing, {
        variant,
        resolution,
        referenceVideoDuration: refDur,
      });
    }
    return computeMotionVideoCreditCost(clipDuration, Boolean(cabinet.motionVideoFileId), cabinet.health?.studio_motion_video_pricing, {
      variant,
      resolution,
      referenceVideoDuration: refDur,
    });
  }, [isEvolink, evolinkPricing, cabinet.health, cabinet.motionVideoFileId, clipDuration, s.vidQuality, s.vidSeedanceVariant]);

  const totalCredits = (outfitSource === 'generate' && outfitState !== 'done' ? dressCredits : 0)
    + (turnSource === 'generate' && turnState !== 'done' ? turnCredits : 0)
    + videoCredits;

  const engineModels = enginesForNsfw(s.contentMode === 'nsfw', cabinet.genModels);
  const dressModels = engineModels;
  const turnModels = engineModels;

  useEffect(() => {
    if (!dressModels.some((m) => m.id === dressModelId) && dressModels[0]?.id) {
      setDressModelId(dressModels[0].id);
    }
    if (!turnModels.some((m) => m.id === turnModelId) && turnModels[0]?.id) {
      setTurnModelId(turnModels[0].id);
    }
  }, [dressModels, turnModels, dressModelId, turnModelId]);

  const onDrivingVideoPicked = (file) => {
    void cabinet.uploadDrivingVideo(file);
  };

  const runDress = useCallback(async () => {
    if (outfitSource !== 'generate') return;
    if (!cabinet.selectedModelId || !baseImageId) {
      cabinet.setError(lang === 'ru' ? 'Выберите персонажа и фото для образа' : 'Pick character and base photo');
      return;
    }
    if (outfitRoute === 'video' && !cabinet.motionVideoFileId) {
      cabinet.setError(lang === 'ru' ? 'Загрузите референс-видео' : 'Upload reference video');
      return;
    }
    const clothFile = cabinet.uploadFiles['mc-clothing'];
    if (outfitRoute === 'own' && !clothFile) {
      cabinet.setError(lang === 'ru' ? 'Загрузите фото одежды' : 'Upload clothing photo');
      return;
    }
    setOutfitState('loading');
    cabinet.setError(null);
    try {
      const dressWave = normalizeWaveModel(dressModelId, s.contentMode === 'nsfw');
      const { result } = await cabinet.runMotionControlDress({
        modelId: cabinet.selectedModelId,
        baseImageId,
        outfitRoute,
        motionVideoFileId: cabinet.motionVideoFileId,
        waveModelId: dressWave.apiId,
        wanEditTier: dressWave.tier,
        studioWaveProfile: dressWaveProfile,
        outputAspect: s.vidFormat || '9:16',
        clothingFile: clothFile,
      });
      const gid = result?.generation_id;
      const url = result?.generated_image_url || '';
      setOutfitGenId(gid);
      setOutfitPreviewUrl(url);
      setOutfitState('done');
      await cabinet.refreshArchiveFull();
      await cabinet.refreshMe();
    } catch (e) {
      setOutfitState('idle');
      cabinet.setError(e?.message || String(e));
    }
  }, [cabinet, baseImageId, outfitRoute, dressModelId, dressWaveProfile, s.vidFormat, s.contentMode, lang, outfitSource]);

  const uploadOutfit = useCallback(async () => {
    if (!cabinet.selectedModelId) {
      cabinet.setError(lang === 'ru' ? 'Выберите персонажа' : 'Pick a character');
      return;
    }
    const file = cabinet.uploadFiles['mc-outfit-upload'];
    if (!file) {
      cabinet.setError(lang === 'ru' ? 'Загрузите фото образа' : 'Upload outfit photo');
      return;
    }
    setOutfitState('loading');
    cabinet.setError(null);
    try {
      const result = await cabinet.uploadMotionControlOutfit({
        modelId: cabinet.selectedModelId,
        file,
        outputAspect: s.vidFormat || '9:16',
      });
      setOutfitGenId(result?.generation_id ?? null);
      setOutfitPreviewUrl(result?.generated_image_url || '');
      setOutfitState('done');
      await cabinet.refreshArchiveFull();
    } catch (e) {
      setOutfitState('idle');
      cabinet.setError(e?.message || String(e));
    }
  }, [cabinet, s.vidFormat, lang]);

  const runTurnaround = useCallback(async () => {
    if (turnSource !== 'generate') return;
    if (!outfitGenId || !faceImageId) {
      cabinet.setError(lang === 'ru' ? 'Сначала соберите образ и выберите лицо' : 'Build outfit and pick face');
      return;
    }
    setTurnState('loading');
    cabinet.setError(null);
    try {
      const { result } = await cabinet.runMotionControlTurnaround({
        modelId: cabinet.selectedModelId,
        outfitGenerationId: outfitGenId,
        faceImageId,
        waveModelId: turnWave.apiId,
        wanEditTier: turnWave.tier,
        studioWaveProfile: dressWaveProfile,
      });
      const gid = result?.generation_id;
      const url = result?.generated_image_url || '';
      setTurnaroundGenId(gid);
      setTurnaroundPreviewUrl(url);
      setTurnState('done');
      await cabinet.refreshArchiveFull();
      await cabinet.refreshMe();
    } catch (e) {
      setTurnState('idle');
      cabinet.setError(e?.message || String(e));
    }
  }, [cabinet, outfitGenId, faceImageId, turnWave, dressWaveProfile, lang, turnSource]);

  const uploadTurnaround = useCallback(async () => {
    if (!cabinet.selectedModelId) {
      cabinet.setError(lang === 'ru' ? 'Выберите персонажа' : 'Pick a character');
      return;
    }
    const file = cabinet.uploadFiles['mc-turnaround-upload'];
    if (!file) {
      cabinet.setError(lang === 'ru' ? 'Загрузите фото развёртки' : 'Upload turnaround photo');
      return;
    }
    setTurnState('loading');
    cabinet.setError(null);
    try {
      const result = await cabinet.uploadMotionControlTurnaround({
        modelId: cabinet.selectedModelId,
        file,
      });
      setTurnaroundGenId(result?.generation_id ?? null);
      setTurnaroundPreviewUrl(result?.generated_image_url || '');
      setTurnState('done');
      await cabinet.refreshArchiveFull();
    } catch (e) {
      setTurnState('idle');
      cabinet.setError(e?.message || String(e));
    }
  }, [cabinet, lang]);

  const handleGenerateVideo = () => {
    if (!cabinet.motionVideoFileId) {
      cabinet.setError(lang === 'ru' ? 'Загрузите референс-видео' : 'Upload reference video');
      return;
    }
    if (!turnaroundGenId) {
      cabinet.setError(lang === 'ru' ? 'Подготовьте развёртку перед видео' : 'Prepare turnaround before video');
      return;
    }
    void onGenerate({
      motionControlWizard: true,
      turnaroundGenerationId: turnaroundGenId,
      trimMode,
      trimStartSec: trimMode === 'part' ? trimIn : null,
      trimEndSec: trimMode === 'part' ? trimOut : null,
      durationSeconds: Math.ceil(clipDuration),
    });
  };

  const stepBlock = {
    background: color.surface,
    border: `1px solid ${line.hair}`,
    borderRadius: isMobile ? 16 : 20,
    padding: isMobile ? 14 : 16,
    marginBottom: 12,
  };

  const layout = isMobile
    ? { display: 'flex', flexDirection: 'column', gap: 12 }
    : { display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, alignItems: 'start' };

  const seedanceModelOpts = isEvolink
    ? [{ v: 'standard', l: t.vidModelStandard }, { v: 'seedance_25', l: t.vidModel25, hot: true }]
    : [
        { v: 'standard', l: t.vidModelStandard },
        { v: 'seedance_25', l: t.vidModel25, hot: true },
        { v: 'mini', l: t.vidModelMini },
      ];
  const qualityOpts = isEvolink
    ? [{ l: '480p', v: '480' }, { l: '720p', v: '720' }]
    : [{ l: '480p', v: '480' }, { l: '720p', v: '720' }, { l: '1080p', v: '1080' }];

  return (
    <div style={layout}>
      <div style={{ minWidth: 0 }}>
        {/* 1 · Персонаж */}
        <div style={stepBlock}>
          <Eyebrow>{lang === 'ru' ? '1 · ПЕРСОНАЖ' : '1 · CHARACTER'}</Eyebrow>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
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
          {model && (
            <div style={{ fontSize: 12, color: color.textDim, marginTop: 8, lineHeight: 1.45 }}>
              {lang === 'ru'
                ? `Лицо для развёртки — тег face (${faceImages.length} фото). Образ собирается на шаге 3.`
                : `Face tag for turnaround (${faceImages.length}). Outfit on step 3.`}
            </div>
          )}
        </div>

        {/* 2 · Реф-видео */}
        <div style={stepBlock}>
          <Eyebrow>{lang === 'ru' ? '2 · РЕФЕРЕНС-ВИДЕО' : '2 · REFERENCE VIDEO'}</Eyebrow>
          <input
            ref={videoRef}
            type="file"
            accept="video/mp4,video/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onDrivingVideoPicked(file);
              e.target.value = '';
            }}
          />
          <Hoverable
            style={{
              marginTop: 10,
              position: 'relative',
              borderRadius: 12,
              padding: 20,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              ...refUploadStyle(Boolean(cabinet.motionVideoFileId)).base,
            }}
            hover={refUploadStyle(Boolean(cabinet.motionVideoFileId)).hover}
            onClick={() => videoRef.current?.click()}
          >
            <span style={{ display: 'flex', width: 22, height: 22, color: color.textMuted }}><IcoFilm /></span>
            <span style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, textAlign: 'center' }}>
              {cabinet.uploadFiles['motion-video']?.name || t.dropVideo}
            </span>
            {cabinet.motionVideoFileId && (
              <span style={{ fontFamily: font.mono, fontSize: 10, color: color.textGhost }}>
                {durationSec.toFixed(1)}s · {s.vidFormat || '9:16'}
              </span>
            )}
          </Hoverable>

          {cabinet.motionVideoFileId && (
            <>
              <div style={{ display: 'flex', gap: 5, marginTop: 12, flexWrap: 'wrap' }}>
                {[['full', lang === 'ru' ? 'Всё видео' : 'Full'], ['part', lang === 'ru' ? 'Отрезок' : 'Segment']].map(([k, label]) => (
                  <Chip key={k} on={trimMode === k} onClick={() => setTrimMode(k)}>{label}</Chip>
                ))}
              </div>
              {trimMode === 'part' && (
                <MotionTrimTimeline
                  videoSrc={motionVideoPreviewUrl}
                  durationSec={durationSec}
                  trimIn={trimIn}
                  trimOut={trimOut}
                  onTrimIn={setTrimIn}
                  onTrimOut={setTrimOut}
                  lang={lang}
                />
              )}
            </>
          )}
        </div>

        {/* 3 · Образ */}
        <div style={stepBlock}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Eyebrow>{lang === 'ru' ? '3 · ОБРАЗ' : '3 · OUTFIT'}</Eyebrow>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', gap: 5 }}>
              <Chip on={outfitSource === 'generate'} onClick={() => setOutfitSource('generate')}>
                {lang === 'ru' ? 'Сгенерировать' : 'Generate'}
              </Chip>
              <Chip on={outfitSource === 'upload'} onClick={() => setOutfitSource('upload')}>
                {lang === 'ru' ? 'Своё фото' : 'Own photo'}
              </Chip>
            </div>
          </div>

          {outfitSource === 'generate' ? (
            <>
              <div style={{ display: 'flex', gap: 5, marginTop: 10, justifyContent: 'flex-end' }}>
                <Chip on={outfitRoute === 'video'} onClick={() => setOutfitRoute('video')}>
                  {lang === 'ru' ? 'С видео' : 'From video'}
                </Chip>
                <Chip on={outfitRoute === 'own'} onClick={() => setOutfitRoute('own')}>
                  {lang === 'ru' ? 'Своя одежда' : 'Own clothing'}
                </Chip>
              </div>
              <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 8, lineHeight: 1.5 }}>
                {outfitRoute === 'video'
                  ? (lang === 'ru'
                    ? 'Берём одежду с первого кадра реф-видео и одеваем выбранное фото модели.'
                    : 'Dress selected model photo using clothing from the first video frame.')
                  : (lang === 'ru'
                    ? 'Загрузите фото одежды и выберите фото персонажа.'
                    : 'Upload clothing reference and pick character photo.')}
              </div>

              <div style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1.2, color: color.textGhost, margin: '14px 0 8px' }}>
                {lang === 'ru' ? 'ФОТО ПЕРСОНАЖА, КОТОРОЕ ОДЕВАЕМ' : 'CHARACTER PHOTO TO DRESS'}
              </div>
              <div style={{ display: 'flex', gap: 9, overflowX: 'auto', paddingBottom: 4 }}>
                {basePhotos.map((im) => (
                  <div
                    key={im.id}
                    style={photoPickStyle(Number(baseImageId) === Number(im.id))}
                    onClick={() => setBaseImageId(Number(im.id))}
                  >
                    <img src={im.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                    <span style={{
                      position: 'absolute', left: 5, bottom: 5, fontFamily: font.mono, fontSize: 8,
                      color: '#fff', background: 'rgba(10,11,13,.76)', borderRadius: 5, padding: '1px 5px',
                    }}
                    >
                      {photoKindShortLabel(lang, im.kind)}
                    </span>
                  </div>
                ))}
              </div>

              {outfitRoute === 'own' && (
                <>
                  <input
                    ref={clothingRef}
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) cabinet.setUploadFile('mc-clothing', file);
                      e.target.value = '';
                    }}
                  />
                  <Hoverable
                    style={{
                      marginTop: 12,
                      borderRadius: 12,
                      padding: 16,
                      cursor: 'pointer',
                      ...refUploadStyle(Boolean(cabinet.uploadFiles['mc-clothing'])).base,
                    }}
                    hover={refUploadStyle(Boolean(cabinet.uploadFiles['mc-clothing'])).hover}
                    onClick={() => clothingRef.current?.click()}
                  >
                    <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: color.textDim }}>
                      {cabinet.uploadFiles['mc-clothing']?.name || (lang === 'ru' ? 'Загрузить одежду' : 'Upload clothing')}
                    </span>
                  </Hoverable>
                </>
              )}

              {!simplifiedUi && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ fontFamily: font.mono, fontSize: 9, color: color.textGhost, marginBottom: 6 }}>
                    {lang === 'ru' ? 'МОДЕЛЬ ФОТО' : 'IMAGE MODEL'}
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {dressModels.map((m) => {
                      const on = dressModelId === m.id;
                      const st = cardPickStyle(on);
                      return (
                        <Hoverable key={m.id} style={st.base} hover={st.hover} onClick={() => setDressModelId(m.id)}>
                          <div style={{ fontWeight: 800, fontSize: 12, ...(on ? { color: color.lime } : {}) }}>{m.name}</div>
                        </Hoverable>
                      );
                    })}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                <Hoverable
                  style={{
                    background: color.lime,
                    color: color.limeInk,
                    fontWeight: 800,
                    fontSize: 13,
                    borderRadius: 11,
                    padding: '10px 16px',
                    cursor: outfitState === 'loading' ? 'wait' : 'pointer',
                    opacity: outfitState === 'loading' ? 0.7 : 1,
                  }}
                  hover={{ filter: 'brightness(1.05)' }}
                  onClick={() => { if (outfitState !== 'loading') void runDress(); }}
                >
                  {lang === 'ru' ? 'Одеть в одежду' : 'Dress outfit'}
                </Hoverable>
                <span style={{ fontFamily: font.mono, fontSize: 10, color: color.textDim }}>
                  −{formatImageCostBadge(dressCredits, lang)}
                </span>
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 8, lineHeight: 1.5 }}>
                {lang === 'ru'
                  ? 'Загрузите готовое фото образа — генерация не нужна, кредиты не списываются.'
                  : 'Upload a ready outfit photo — no generation, no credits charged.'}
              </div>
              <input
                ref={outfitUploadRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) cabinet.setUploadFile('mc-outfit-upload', file);
                  e.target.value = '';
                }}
              />
              <Hoverable
                style={{
                  marginTop: 12,
                  borderRadius: 12,
                  padding: 16,
                  cursor: 'pointer',
                  ...refUploadStyle(Boolean(cabinet.uploadFiles['mc-outfit-upload'])).base,
                }}
                hover={refUploadStyle(Boolean(cabinet.uploadFiles['mc-outfit-upload'])).hover}
                onClick={() => outfitUploadRef.current?.click()}
              >
                <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
                <span style={{ fontSize: 11, fontWeight: 700, color: color.textDim }}>
                  {cabinet.uploadFiles['mc-outfit-upload']?.name || (lang === 'ru' ? 'Загрузить фото образа' : 'Upload outfit photo')}
                </span>
              </Hoverable>
              {cabinet.uploadPreviewUrls?.['mc-outfit-upload'] && outfitState !== 'done' && (
                <div style={{ marginTop: 12 }}>
                  <img
                    src={cabinet.uploadPreviewUrls['mc-outfit-upload']}
                    alt=""
                    style={{ maxWidth: 140, borderRadius: 12, border: `1px solid ${line.soft}` }}
                  />
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                <Hoverable
                  style={{
                    background: color.lime,
                    color: color.limeInk,
                    fontWeight: 800,
                    fontSize: 13,
                    borderRadius: 11,
                    padding: '10px 16px',
                    cursor: outfitState === 'loading' ? 'wait' : 'pointer',
                    opacity: outfitState === 'loading' ? 0.7 : 1,
                  }}
                  hover={{ filter: 'brightness(1.05)' }}
                  onClick={() => { if (outfitState !== 'loading') void uploadOutfit(); }}
                >
                  {lang === 'ru' ? 'Использовать фото' : 'Use photo'}
                </Hoverable>
                <span style={{ fontFamily: font.mono, fontSize: 10, color: color.textDim }}>
                  {lang === 'ru' ? 'бесплатно' : 'free'}
                </span>
              </div>
            </>
          )}

          {outfitState === 'loading' && (
            <div style={{ marginTop: 12, fontSize: 11, color: '#38BDF8' }}>
              {outfitSource === 'upload'
                ? (lang === 'ru' ? 'Загружаем образ…' : 'Uploading outfit…')
                : (lang === 'ru' ? 'Собираем образ…' : 'Building outfit…')}
            </div>
          )}
          {outfitState === 'done' && outfitPreviewUrl && (
            <div style={{ marginTop: 12 }}>
              <img src={outfitPreviewUrl} alt="" style={{ maxWidth: 140, borderRadius: 12, border: `1px solid ${line.soft}` }} />
            </div>
          )}
        </div>

        {/* 4 · Развёртка */}
        <div style={stepBlock}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Eyebrow>{lang === 'ru' ? '4 · РАЗВЁРТКА' : '4 · TURNAROUND'}</Eyebrow>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', gap: 5 }}>
              <Chip on={turnSource === 'generate'} onClick={() => setTurnSource('generate')}>
                {lang === 'ru' ? 'Сгенерировать' : 'Generate'}
              </Chip>
              <Chip on={turnSource === 'upload'} onClick={() => setTurnSource('upload')}>
                {lang === 'ru' ? 'Своё фото' : 'Own photo'}
              </Chip>
            </div>
          </div>
          <div style={{ fontSize: 11, color: color.textDim, marginTop: 6, lineHeight: 1.45 }}>
            {lang === 'ru' ? 'Character sheet 16:9 для video-edit' : '16:9 character sheet for video-edit'}
          </div>

          {turnSource === 'generate' ? (
            <>
              <div style={{ fontFamily: font.mono, fontSize: 9, color: color.textGhost, margin: '12px 0 8px' }}>
                {lang === 'ru' ? 'ЛИЦО ПЕРСОНАЖА (FACE)' : 'FACE PHOTO'}
              </div>
              <div style={{ display: 'flex', gap: 9, overflowX: 'auto', paddingBottom: 4 }}>
                {(faceImages.length ? faceImages : modelImages).map((im) => (
                  <div
                    key={im.id}
                    style={photoPickStyle(Number(faceImageId) === Number(im.id))}
                    onClick={() => setFaceImageId(Number(im.id))}
                  >
                    <img src={im.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                  </div>
                ))}
              </div>

              {!simplifiedUi && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontFamily: font.mono, fontSize: 9, color: color.textGhost, marginBottom: 6 }}>
                    {lang === 'ru' ? 'МОДЕЛЬ ГЕНЕРАЦИИ' : 'GENERATION MODEL'}
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {turnModels.map((m) => {
                      const on = turnModelId === m.id;
                      const st = cardPickStyle(on);
                      return (
                        <Hoverable key={m.id} style={st.base} hover={st.hover} onClick={() => setTurnModelId(m.id)}>
                          <div style={{ fontWeight: 800, fontSize: 12, ...(on ? { color: color.lime } : {}) }}>{m.name}</div>
                        </Hoverable>
                      );
                    })}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                <Hoverable
                  style={{
                    background: 'rgba(56,189,248,.15)',
                    border: '1px solid rgba(56,189,248,.35)',
                    color: '#7DD3FC',
                    fontWeight: 800,
                    fontSize: 13,
                    borderRadius: 11,
                    padding: '10px 16px',
                    cursor: turnState === 'loading' ? 'wait' : 'pointer',
                    opacity: turnState === 'loading' ? 0.7 : 1,
                  }}
                  hover={{ background: 'rgba(56,189,248,.22)' }}
                  onClick={() => { if (turnState !== 'loading') void runTurnaround(); }}
                >
                  {lang === 'ru' ? 'Сгенерировать развёртку' : 'Generate turnaround'}
                </Hoverable>
                <span style={{ fontFamily: font.mono, fontSize: 10, color: color.textDim }}>
                  −{formatImageCostBadge(turnCredits, lang)}
                </span>
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 8, lineHeight: 1.5 }}>
                {lang === 'ru'
                  ? 'Загрузите готовую развёртку 16:9 — генерация не нужна, кредиты не списываются.'
                  : 'Upload a ready 16:9 turnaround — no generation, no credits charged.'}
              </div>
              <input
                ref={turnaroundUploadRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) cabinet.setUploadFile('mc-turnaround-upload', file);
                  e.target.value = '';
                }}
              />
              <Hoverable
                style={{
                  marginTop: 12,
                  borderRadius: 12,
                  padding: 16,
                  cursor: 'pointer',
                  ...refUploadStyle(Boolean(cabinet.uploadFiles['mc-turnaround-upload'])).base,
                }}
                hover={refUploadStyle(Boolean(cabinet.uploadFiles['mc-turnaround-upload'])).hover}
                onClick={() => turnaroundUploadRef.current?.click()}
              >
                <span style={{ display: 'flex', width: 20, height: 20, color: color.textMuted }}><IcoUpload /></span>
                <span style={{ fontSize: 11, fontWeight: 700, color: color.textDim }}>
                  {cabinet.uploadFiles['mc-turnaround-upload']?.name || (lang === 'ru' ? 'Загрузить развёртку' : 'Upload turnaround')}
                </span>
              </Hoverable>
              {cabinet.uploadPreviewUrls?.['mc-turnaround-upload'] && turnState !== 'done' && (
                <div style={{ marginTop: 12 }}>
                  <img
                    src={cabinet.uploadPreviewUrls['mc-turnaround-upload']}
                    alt=""
                    style={{ maxWidth: '100%', maxHeight: 180, borderRadius: 12, border: `1px solid ${line.soft}` }}
                  />
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                <Hoverable
                  style={{
                    background: 'rgba(56,189,248,.15)',
                    border: '1px solid rgba(56,189,248,.35)',
                    color: '#7DD3FC',
                    fontWeight: 800,
                    fontSize: 13,
                    borderRadius: 11,
                    padding: '10px 16px',
                    cursor: turnState === 'loading' ? 'wait' : 'pointer',
                    opacity: turnState === 'loading' ? 0.7 : 1,
                  }}
                  hover={{ background: 'rgba(56,189,248,.22)' }}
                  onClick={() => { if (turnState !== 'loading') void uploadTurnaround(); }}
                >
                  {lang === 'ru' ? 'Использовать фото' : 'Use photo'}
                </Hoverable>
                <span style={{ fontFamily: font.mono, fontSize: 10, color: color.textDim }}>
                  {lang === 'ru' ? 'бесплатно' : 'free'}
                </span>
              </div>
            </>
          )}

          {turnState === 'loading' && (
            <div style={{ marginTop: 12, fontSize: 11, color: '#38BDF8' }}>
              {turnSource === 'upload'
                ? (lang === 'ru' ? 'Загружаем развёртку…' : 'Uploading turnaround…')
                : (lang === 'ru' ? 'Генерируем развёртку…' : 'Generating turnaround…')}
            </div>
          )}
          {turnState === 'done' && turnaroundPreviewUrl && (
            <div style={{ marginTop: 12 }}>
              <img src={turnaroundPreviewUrl} alt="" style={{ maxWidth: '100%', maxHeight: 220, borderRadius: 12, border: `1px solid ${line.soft}` }} />
            </div>
          )}
        </div>
      </div>

      {/* Правая колонка: параметры видео */}
      <div
        style={{
          background: color.surface,
          border: `1px solid ${line.hair}`,
          borderRadius: 16,
          padding: 16,
          position: isMobile ? 'static' : 'sticky',
          top: 12,
          height: 'fit-content',
        }}
      >
        <div style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: 2, color: color.textDim, marginBottom: 12 }}>
          {lang === 'ru' ? 'ПАРАМЕТРЫ ВИДЕО' : 'VIDEO PARAMS'}
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, marginBottom: 6 }}>{t.format}</div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {['9:16', '16:9', '1:1'].map((v) => (
              <Chip key={v} on={s.vidFormat === v} onClick={() => setS({ vidFormat: v })}>{v}</Chip>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, marginBottom: 6 }}>
            {isEvolink ? <SeedanceSaleLabel /> : (lang === 'ru' ? 'Модель Seedance' : 'Seedance model')}
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {seedanceModelOpts.map((m) => (
              <Chip key={m.v} on={(s.vidSeedanceVariant || 'standard') === m.v} onClick={() => setS({ vidSeedanceVariant: m.v })}>
                {m.l}
              </Chip>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: color.textDim, marginBottom: 6 }}>{lang === 'ru' ? 'Качество' : 'Quality'}</div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {qualityOpts.map((q) => (
              <Chip key={q.v} on={s.vidQuality === q.v} onClick={() => setS({ vidQuality: q.v })}>{q.l}</Chip>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 14, fontSize: 11, color: color.textDim, lineHeight: 1.5 }}>
          <div>{lang === 'ru' ? 'Длина клипа' : 'Clip length'}: {clipDuration.toFixed(1)}s</div>
          <div>{lang === 'ru' ? 'Оценка за запуск' : 'Run estimate'}: ~{Math.round(totalCredits)} {t.cr}</div>
        </div>

        <Hoverable
          style={{
            background: color.lime,
            color: color.limeInk,
            fontWeight: 800,
            fontSize: 14,
            borderRadius: 12,
            padding: '14px 16px',
            textAlign: 'center',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
          }}
          hover={{ filter: 'brightness(1.05)' }}
          onClick={handleGenerateVideo}
        >
          <span style={{ display: 'flex', width: 16, height: 16 }}><IcoPlay /></span>
          {lang === 'ru' ? 'Сгенерировать видео' : 'Generate video'}
          <span style={{ fontFamily: font.mono, fontSize: 11 }}>
            −{formatMotionCreditCost(videoCredits, isEvolink ? evolinkPricing : cabinet.health?.studio_motion_video_pricing, t.cr)}
          </span>
        </Hoverable>
        <div style={{ fontSize: 10.5, color: color.textGhost, marginTop: 8, lineHeight: 1.45 }}>
          {lang === 'ru'
            ? 'Video-edit: развёртка + отрезок реф-видео. Промпт character-only replacement.'
            : 'Video-edit with turnaround + trimmed reference clip.'}
        </div>
      </div>
    </div>
  );
}
