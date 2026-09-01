import { useEffect, useRef, useMemo } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoFilm, IcoSpark, IcoUpload, IcoPlay, IcoText, IcoZoom } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip, SelectPill, Overlay, CloseButton } from '../components/ui';
import VideoPreviewModal from '../components/VideoPreviewModal';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { modeCardStyle, refUploadStyle, borderHoverOff, refThumbStyle, cardPickStyle } from '../styles/mixins';
import { videoModeDefs } from '../data/catalog';
import { archiveThumbUrl, archiveDownloadUrl, archiveVideoUrl, isArchivePending, downloadVideoNoteByPath } from '../api/actions';
import { downloadArchiveBlob } from '../api/archiveDownload';
import { sameStudioModelId, enginesForNsfw, isUiSimplified } from '../api/studioHelpers';
import { formatArchiveErrorMessage } from '../api/helpers';
import { formatArchivePipelineLabel } from '../api/archivePipelineLabel';
import { normalizeBillingPlan } from '../../billing/planCatalog';
import {
  computeEvolinkVideoCreditCost,
  computeMotionVideoCreditCost,
  computeMotionVideoUsdCost,
  evolinkDurationMax,
  formatMotionCreditCost,
  formatMotionUsd,
  mergeEvolinkVideoPricing,
} from '../../studioMotionPricing';
import { videoNoteDownloadPath, videoNoteSendPayload } from '../../studioArchive';
import SeedanceSaleLabel from '../components/SeedanceSaleLabel';
import SeedanceDirector from './SeedanceDirector';
import MotionControlWizard from '../components/MotionControlWizard';

const vidModeIcons = { film: IcoFilm, text: IcoText };

function isTelegramConversation(c) {
  const p = String(c?.platform || '').toLowerCase();
  return p === 'telegram' || p === 'telegram_user';
}

function vidQualityLabel(q) {
  const v = String(q || '1080').toLowerCase();
  if (v === '4k') return '4K';
  if (v === '480' || v === '480p') return '480p';
  if (v === '720' || v === '720p') return '720p';
  return '1080p';
}

function buildVideoMetaLine({ quality, ratio, durationSec, lang }) {
  const parts = [];
  if (quality) parts.push(quality);
  if (ratio) parts.push(ratio);
  if (durationSec) parts.push(lang === 'ru' ? `${durationSec} с` : `${durationSec}s`);
  return parts.join(' · ');
}

/** Как на бэкенде: 720/1080/4k → Seedance resolution (4k в API уходит как 1080p). */
function vidQualityToResolution(vidQuality) {
  const v = String(vidQuality || '1080').toLowerCase();
  if (v === '1080' || v === '1080p' || v === '4k') return '1080p';
  if (v === '480' || v === '480p') return '480p';
  return '720p';
}

function aspectCss(ratio) {
  const r = String(ratio || '9:16').trim();
  if (r === '16:9') return '16 / 9';
  if (r === '1:1') return '1 / 1';
  if (r === '4:3') return '4 / 3';
  if (r === '3:4') return '3 / 4';
  return '9 / 16';
}

export function VideoStudioPage({ backend = 'wavespeed' }) {
  const isEvolink = backend === 'evolink';
  const { t, lang, s, setS, isMobile, go, cabinet } = useApp();
  const simplifiedUi = isUiSimplified(cabinet.me);
  const isPro = !isEvolink && normalizeBillingPlan(cabinet.me?.billing_plan) === 'pro';
  const evolinkEnabled = cabinet.health?.evolink_video_enabled !== false;
  const evolinkPricing = mergeEvolinkVideoPricing(cabinet.health?.studio_evolink_video_pricing);
  const pageArchiveVideos = isEvolink ? (cabinet.archiveSeedanceVideos || []) : (cabinet.archiveVideos || []);
  const pageArchiveHasMore = isEvolink ? cabinet.archiveSeedanceVideosHasMore : cabinet.archiveVideosHasMore;
  const loadMoreArchiveVideos = isEvolink ? cabinet.loadMoreArchiveSeedanceVideos : cabinet.loadMoreArchiveVideos;
  const videoRef = useRef(null);
  const frameRef = useRef(null);
  const timer = useRef(null);

  const tgConversations = useMemo(
    () => (cabinet.conversations || []).filter(isTelegramConversation),
    [cabinet.conversations],
  );

  const downloadArchiveVideo = (url, filename) => {
    if (!url) {
      cabinet.setError(lang === 'ru' ? 'Файл недоступен для скачивания' : 'File unavailable for download');
      return;
    }
    cabinet.setError(null);
    void downloadArchiveBlob(url, filename).catch((err) => {
      cabinet.setError(err?.message || String(err));
    });
  };

  useEffect(() => () => clearTimeout(timer.current), []);

  useEffect(() => {
    if (!isEvolink) return;
    const patches = {};
    if (s.vidSeedanceVariant === 'mini') patches.vidSeedanceVariant = 'standard';
    const res = vidQualityToResolution(s.vidQuality);
    if (res !== '480p' && res !== '720p') patches.vidQuality = '720';
    if (Object.keys(patches).length) setS(patches);
  }, [isEvolink, s.vidSeedanceVariant, s.vidQuality, setS]);

  const genFirstFrame = () => {
    setS({ ffState: 'loading' });
    void cabinet
      .generateFirstFrame(s, '')
      .then(() => setS({ ffState: 'done' }))
      .catch(() => setS({ ffState: 'idle' }));
  };

  const handleGenerateVideo = (wizardOpts) => {
    return cabinet.generateVideo(s, {
      backend: isEvolink ? 'evolink' : 'wavespeed',
      wizard: wizardOpts || null,
    });
  };

  const vidModes = videoModeDefs(lang);
  const curVidMode = vidModes.find((m) => m.id === s.vidMode) || vidModes[0];
  const motionControl = s.vidMode === 'motion-control';
  const engineModels = enginesForNsfw(s.contentMode === 'nsfw', cabinet.genModels);
  const activeEngine = engineModels.find((m) => m.id === s.aiModel) || engineModels[0];
  const pickedArchiveId = s.carouselPickId ?? cabinet.firstFrameGenId;
  const hasFrameUpload = Boolean(cabinet.uploadFiles['motion-frame']);
  const ffPreviewUrl = cabinet.uploadPreviewUrls?.['motion-frame']
    || (hasFrameUpload ? '' : cabinet.firstFrameUrl)
    || (hasFrameUpload ? '' : (() => {
      const pickId = s.carouselPickId ?? cabinet.firstFrameGenId
      if (pickId == null) return ''
      const hit = (cabinet.archiveImages || []).find((x) => Number(x.id) === Number(pickId))
      return hit ? archiveThumbUrl(hit) : ''
    })());
  const ffRatio = s.vidFormat || cabinet.selectedAspect || '9:16';
  const ffWho = cabinet.models.find((m) => sameStudioModelId(m.id, cabinet.selectedModelId))?.name || '—';

  const clearArchiveFramePick = () => {
    cabinet.clearFirstFrameArchivePick();
    setS({ carouselPickId: null });
  };

  const pickArchiveFrame = (item) => {
    const id = Number(item.id);
    if (Number(pickedArchiveId) === id) {
      clearArchiveFramePick();
      return;
    }
    cabinet.pickFirstFrameFromArchive(item);
    setS({ carouselPickId: item.id });
    cabinet.setUploadFile('motion-frame', null);
  };

  const onFrameFilePicked = (file) => {
    cabinet.setUploadFile('motion-frame', file);
    clearArchiveFramePick();
  };

  const onDrivingVideoPicked = (file) => {
    setS({ carouselPickId: null, ffState: 'idle' });
    cabinet.clearFirstFrameArchivePick();
    void cabinet.uploadDrivingVideo(file);
  };

  const uploadClearBtn = (onClear, title) => (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={(e) => {
        e.stopPropagation();
        onClear();
      }}
      style={{
        position: 'absolute',
        top: 6,
        right: 6,
        zIndex: 2,
        border: 'none',
        borderRadius: 6,
        padding: '2px 7px',
        background: 'rgba(0,0,0,.65)',
        color: '#fff',
        fontSize: 11,
        fontWeight: 700,
        cursor: 'pointer',
      }}
    >
      ✕
    </button>
  );

  const pickContentMode = (contentMode) => {
    const list = enginesForNsfw(contentMode === 'nsfw', cabinet.genModels);
    setS({
      contentMode,
      aiModel: list[0]?.id || (contentMode === 'nsfw' ? 'seedream-v5.0-pro' : 'nano-banana-pro'),
    });
  };

  const cmSeg = (on, tone) => ({
    flex: 1, textAlign: 'center', fontSize: 12, fontWeight: 800,
    borderRadius: 8, padding: '8px 10px', cursor: 'pointer', boxSizing: 'border-box',
    border: '1px solid transparent',
    ...(on ? tone : { color: color.textDim }),
  });

  const openFfPreview = () => {
    if (ffPreviewUrl) setS({ ffPreviewOpen: true });
  };

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
    const hasReferenceVideo = motionControl && Boolean(cabinet.motionVideoFileId);
    const variant = s.vidSeedanceVariant || 'standard';
    const resolution = vidQualityToResolution(s.vidQuality);
    const referenceVideoDuration = hasReferenceVideo ? cabinet.motionVideoDurationSec : null
    if (isEvolink) {
      return computeEvolinkVideoCreditCost(duration, hasReferenceVideo, evolinkPricing, {
        variant,
        resolution,
        referenceVideoDuration,
      });
    }
    return computeMotionVideoCreditCost(duration, hasReferenceVideo, cabinet.health?.studio_motion_video_pricing, {
      variant,
      resolution,
      referenceVideoDuration,
    });
  }, [isEvolink, evolinkPricing, cabinet.health, cabinet.motionVideoFileId, cabinet.motionVideoDurationSec, s.vidTime, s.vidQuality, s.vidSeedanceVariant, motionControl]);

  const vidUsd = useMemo(() => {
    if (isEvolink) return 0;
    const duration = Number(s.vidTime) || 5;
    const hasReferenceVideo = motionControl && Boolean(cabinet.motionVideoFileId);
    const pricing = cabinet.health?.studio_motion_video_pricing;
    const variant = s.vidSeedanceVariant || 'standard';
    const referenceVideoDuration = hasReferenceVideo ? cabinet.motionVideoDurationSec : null
    return computeMotionVideoUsdCost(duration, hasReferenceVideo, pricing, {
      variant,
      resolution: vidQualityToResolution(s.vidQuality),
      referenceVideoDuration,
    });
  }, [isEvolink, cabinet.health, cabinet.motionVideoFileId, cabinet.motionVideoDurationSec, s.vidTime, s.vidQuality, s.vidSeedanceVariant, motionControl]);

  const activePricing = isEvolink ? evolinkPricing : cabinet.health?.studio_motion_video_pricing;

  const vidCostLabel = isEvolink || !isPro
    ? `−${formatMotionCreditCost(vidCost, activePricing, t.cr)}`
    : formatMotionUsd(vidUsd);

  const seedanceModelOptsAll = [
    { v: 'standard', l: t.vidModelStandard },
    { v: 'seedance_25', l: t.vidModel25, hot: true },
    { v: 'mini', l: t.vidModelMini },
  ];
  const seedanceModelOpts = isEvolink
    ? seedanceModelOptsAll.filter((m) => m.v !== 'mini')
    : seedanceModelOptsAll;
  const ffImgStyle = { width: 70, aspectRatio: '9/16', borderRadius: 10, flex: 'none', background: G[3] };

  const variant = s.vidSeedanceVariant || 'standard';
  const qualityOptsAll = [{ l: '480p', v: '480' }, { l: '720p', v: '720' }, { l: '1080p', v: '1080' }, { l: '4K', v: '4k' }];
  const qualityOptsEvolink = [{ l: '480p', v: '480' }, { l: '720p', v: '720' }];
  const qualityOpts = isEvolink ? qualityOptsEvolink : qualityOptsAll;
  const vfmtOpts = ['9:16', '16:9', '1:1', '4:3', '3:4'];
  const vtimeOpts = useMemo(() => {
    const maxDur = isEvolink
      ? evolinkDurationMax(variant, evolinkPricing)
      : 15;
    const minDur = isEvolink ? (evolinkPricing.duration_min ?? 4) : 4;
    const len = Math.max(1, maxDur - minDur + 1);
    return Array.from({ length: len }, (_, i) => {
      const sec = i + minDur;
      return { l: lang === 'ru' ? `${sec} с` : `${sec}s`, v: String(sec) };
    });
  }, [isEvolink, evolinkPricing, variant, lang]);

  return (
    <Fade data-screen-label="Студия — Видео">
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>
          {isEvolink ? <SeedanceSaleLabel active style={{ fontSize: 'inherit', fontWeight: 'inherit' }} /> : t.navVideo}
        </PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{isEvolink ? t.seedanceSaleDesc : t.videoDesc}</div>
        {isEvolink && !evolinkEnabled && (
          <div style={{ marginTop: 10, fontSize: 12, color: '#fbbf24', lineHeight: 1.45 }}>
            {t.seedanceSaleDisabled}
          </div>
        )}
        {isEvolink && evolinkEnabled && (
          <div style={{ marginTop: 10, fontSize: 11.5, color: color.textDim, lineHeight: 1.45 }}>
            {t.seedanceSaleCreditsHint}
          </div>
        )}
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
                if (!disabled) {
                  // Смена режима видео — сброс кадра/драйвинга, иначе тянется реф прошлого режима.
                  cabinet.setUploadFile('motion-frame', null);
                  cabinet.clearFirstFrameArchivePick();
                  setS({ vidMode: m.id, carouselPickId: null, ffState: 'idle' });
                }
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

      {motionControl ? (
      <>
        <MotionControlWizard
          t={t}
          lang={lang}
          s={s}
          setS={setS}
          isMobile={isMobile}
          cabinet={cabinet}
          isEvolink={isEvolink}
          onGenerate={handleGenerateVideo}
        />

        {/* archive */}
        <div>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 10 }}>{t.archive}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10 }}>
            {(pageArchiveVideos || []).map((item, i) => {
              const poster = archiveThumbUrl(item);
              const videoUrl = archiveVideoUrl(item);
              const downloadUrl = archiveDownloadUrl(item) || videoUrl;
              const videoNotePath = videoNoteDownloadPath(item);
              const pending = isArchivePending(item);
              const failed = (item.status || '').trim() === 'failed';
              const model = (cabinet.models || []).find((m) => m.id === item.studio_model_id);
              const pipelineLabel = formatArchivePipelineLabel(item, lang);
              const ratio = item.output_aspect || '9:16';
              return (
              <Hoverable
                key={item.id || i}
                style={{
                  borderRadius: 12, overflow: 'hidden', background: color.surface,
                  border: `1px solid ${failed ? 'rgba(248,113,113,.45)' : line.hair}`,
                  cursor: pending || failed || !videoUrl ? 'default' : 'pointer',
                  opacity: pending ? 0.88 : 1,
                }}
                hover={pending || failed || !videoUrl ? {} : { borderColor: borderHoverOff }}
                onClick={() => {
                  if (!pending && !failed && videoUrl) {
                    setS({
                      vidLightbox: {
                        url: videoUrl,
                        poster: poster || '',
                        who: model?.name || '—',
                        ratio,
                        metaLine: buildVideoMetaLine({
                          quality: vidQualityLabel(s.vidQuality),
                          ratio,
                          durationSec: Number(s.vidTime) || null,
                          lang,
                        }),
                        downloadUrl,
                        id: item.id,
                        videoNotePath,
                        videoNotePayload: videoNoteSendPayload(item),
                      },
                    });
                  }
                }}
              >
                <div
                  style={{
                    aspectRatio: '9/16', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    position: 'relative', overflow: 'hidden',
                    background: (!videoUrl && poster) ? `url(${poster}) center/cover` : G[(i + 2) % 6],
                  }}
                >
                  {videoUrl && !pending && !failed && (
                    <video
                      src={videoUrl}
                      muted
                      playsInline
                      preload="metadata"
                      style={{
                        position: 'absolute', inset: 0, width: '100%', height: '100%',
                        objectFit: 'cover', display: 'block', pointerEvents: 'none',
                      }}
                      onLoadedMetadata={(e) => {
                        try { e.currentTarget.currentTime = 0.05; } catch { /* ignore */ }
                      }}
                    />
                  )}
                  {poster && !videoUrl && !pending && !failed && (
                    <img
                      src={poster}
                      alt=""
                      style={{
                        position: 'absolute', inset: 0, width: '100%', height: '100%',
                        objectFit: 'cover', display: 'block', pointerEvents: 'none',
                      }}
                    />
                  )}
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
                        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', gap: 6,
                        background: 'rgba(40,10,12,.82)', padding: '10px 8px',
                      }}
                      title={formatArchiveErrorMessage(item.error_message, lang)}
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
                        {formatArchiveErrorMessage(item.error_message, lang)}
                      </span>
                    </div>
                  )}
                  {!pending && !failed && (
                  <div
                    style={{
                      position: 'relative', zIndex: 1,
                      width: 36, height: 36, borderRadius: '50%', background: 'rgba(0,0,0,.45)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    <span style={{ display: 'flex', width: 14, height: 14, color: '#fff', marginLeft: 2 }}><IcoPlay /></span>
                  </div>
                  )}
                </div>
                <div style={{ padding: '8px 10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontWeight: 700, fontSize: 11 }}>{model?.name || item.model_name || '—'}</span>
                    {downloadUrl && !pending && (
                      <span style={{ fontSize: 10, fontWeight: 700, color: color.textDim }}>MP4</span>
                    )}
                  </div>
                  {pipelineLabel && (
                    <div style={{
                      marginTop: 4,
                      fontSize: 9.5,
                      color: color.textDim,
                      lineHeight: 1.35,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    >
                      {pipelineLabel}
                    </div>
                  )}
                </div>
              </Hoverable>
            );})}
          </div>
          {pageArchiveHasMore && (
            <Hoverable
              style={{
                marginTop: 12, display: 'inline-flex', alignItems: 'center', gap: 8,
                fontSize: 12.5, fontWeight: 700, color: color.lime, cursor: 'pointer',
                border: '1px solid rgba(215,244,82,.35)', borderRadius: 10, padding: '8px 16px',
              }}
              hover={{ background: 'rgba(215,244,82,.08)' }}
              onClick={() => void loadMoreArchiveVideos?.()}
            >
              {t.showMore}
            </Hoverable>
          )}
        </div>
      </>
      ) : (
        <>
          <SeedanceDirector embedded backend={isEvolink ? 'evolink' : 'wavespeed'} />
          <div style={{ marginTop: 24 }}>
            <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 10 }}>{t.archive}</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10 }}>
              {(pageArchiveVideos || []).map((item, i) => {
                const poster = archiveThumbUrl(item);
                const videoUrl = archiveVideoUrl(item);
                const downloadUrl = archiveDownloadUrl(item) || videoUrl;
                const videoNotePath = videoNoteDownloadPath(item);
                const pending = isArchivePending(item);
                const failed = (item.status || '').trim() === 'failed';
                const model = (cabinet.models || []).find((m) => m.id === item.studio_model_id);
                const pipelineLabel = formatArchivePipelineLabel(item, lang);
                const ratio = item.output_aspect || '9:16';
                return (
                <Hoverable
                  key={item.id || i}
                  style={{
                    borderRadius: 12, overflow: 'hidden', background: color.surface,
                    border: `1px solid ${failed ? 'rgba(248,113,113,.45)' : line.hair}`,
                    cursor: pending || failed || !videoUrl ? 'default' : 'pointer',
                    opacity: pending ? 0.88 : 1,
                  }}
                  hover={pending || failed || !videoUrl ? {} : { borderColor: borderHoverOff }}
                  onClick={() => {
                    if (!pending && !failed && videoUrl) {
                      setS({
                        vidLightbox: {
                          url: videoUrl,
                          poster: poster || '',
                          who: model?.name || '—',
                          ratio,
                          metaLine: buildVideoMetaLine({
                            quality: vidQualityLabel(s.vidQuality),
                            ratio,
                            durationSec: Number(s.vidTime) || null,
                            lang,
                          }),
                          downloadUrl,
                          id: item.id,
                          videoNotePath,
                          videoNotePayload: videoNoteSendPayload(item),
                        },
                      });
                    }
                  }}
                >
                  <div
                    style={{
                      aspectRatio: '9/16', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      position: 'relative', overflow: 'hidden',
                      background: (!videoUrl && poster) ? `url(${poster}) center/cover` : G[(i + 2) % 6],
                    }}
                  >
                    {videoUrl && !pending && !failed && (
                      <video
                        src={videoUrl}
                        muted
                        playsInline
                        preload="metadata"
                        style={{
                          position: 'absolute', inset: 0, width: '100%', height: '100%',
                          objectFit: 'cover', display: 'block', pointerEvents: 'none',
                        }}
                        onLoadedMetadata={(e) => {
                          try { e.currentTarget.currentTime = 0.05; } catch { /* ignore */ }
                        }}
                      />
                    )}
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
                          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                          alignItems: 'center', justifyContent: 'center', gap: 6,
                          background: 'rgba(40,10,12,.82)', padding: '10px 8px',
                        }}
                        title={formatArchiveErrorMessage(item.error_message, lang)}
                      >
                        <span style={{ fontFamily: font.mono, fontSize: 8, fontWeight: 800, color: color.red }}>
                          {lang === 'ru' ? 'ОШИБКА' : 'FAILED'}
                        </span>
                      </div>
                    )}
                    {!pending && !failed && (
                    <div
                      style={{
                        position: 'relative', zIndex: 1,
                        width: 36, height: 36, borderRadius: '50%', background: 'rgba(0,0,0,.45)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}
                    >
                      <span style={{ display: 'flex', width: 14, height: 14, color: '#fff', marginLeft: 2 }}><IcoPlay /></span>
                    </div>
                    )}
                  </div>
                  <div style={{ padding: '8px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontWeight: 700, fontSize: 11 }}>{model?.name || item.model_name || '—'}</span>
                    </div>
                    {pipelineLabel && (
                      <div style={{
                        marginTop: 4,
                        fontSize: 9.5,
                        color: color.textDim,
                        lineHeight: 1.35,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      >
                        {pipelineLabel}
                      </div>
                    )}
                  </div>
                </Hoverable>
              );})}
            </div>
            {pageArchiveHasMore && (
              <Hoverable
                style={{
                  marginTop: 12, display: 'inline-flex', alignItems: 'center', gap: 8,
                  fontSize: 12.5, fontWeight: 700, color: color.lime, cursor: 'pointer',
                  border: '1px solid rgba(215,244,82,.35)', borderRadius: 10, padding: '8px 16px',
                }}
                hover={{ background: 'rgba(215,244,82,.08)' }}
                onClick={() => void loadMoreArchiveVideos?.()}
              >
                {t.showMore}
              </Hoverable>
            )}
          </div>
        </>
      )}

      {s.ffPreviewOpen && ffPreviewUrl && (
        <Overlay onClose={() => setS({ ffPreviewOpen: false })}>
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: 14,
              width: 'min(96vw, 720px)', maxHeight: '92vh',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: 15 }}>{ffWho}</div>
                <div style={{ fontSize: 11, color: color.textDim }}>
                  {t.firstFrame} · {ffRatio}
                </div>
              </div>
              <CloseButton onClick={() => setS({ ffPreviewOpen: false })} label={t.close} />
            </div>
            <div
              style={{
                width: '100%', aspectRatio: aspectCss(ffRatio),
                maxHeight: 'min(calc(92vh - 120px), 85vh)',
                borderRadius: 14, overflow: 'hidden', background: color.bgPanel,
              }}
            >
              <img
                src={ffPreviewUrl}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
              />
            </div>
          </div>
        </Overlay>
      )}

      <VideoPreviewModal
        open={Boolean(s.vidLightbox?.url)}
        onClose={() => setS({ vidLightbox: null })}
        who={s.vidLightbox?.who}
        metaLine={s.vidLightbox?.metaLine}
        ratio={s.vidLightbox?.ratio || '9:16'}
        videoUrl={s.vidLightbox?.url}
        posterUrl={s.vidLightbox?.poster}
        mp4Hint="MP4"
        downloadUrl={s.vidLightbox?.downloadUrl}
        videoNotePath={s.vidLightbox?.videoNotePath}
        videoNotePayload={s.vidLightbox?.videoNotePayload}
        tgConversations={tgConversations}
        t={t}
        lang={lang}
        onDownloadMp4={() => downloadArchiveVideo(
          s.vidLightbox?.downloadUrl,
          `modelmate-video-${s.vidLightbox?.id || 'clip'}.mp4`,
        )}
        onDownloadVideoNote={() => {
          const path = s.vidLightbox?.videoNotePath;
          if (!path) {
            cabinet.setError(lang === 'ru' ? 'Кружок недоступен для этого видео' : 'Video note unavailable for this clip');
            return;
          }
          cabinet.setError(null);
          void downloadVideoNoteByPath(
            path,
            `modelmate-video-note-${Math.abs(s.vidLightbox?.id || 0)}.mp4`,
          ).catch((err) => {
            cabinet.setError(err?.message || String(err));
          });
        }}
        onSendVideoNote={(convId, payload) => cabinet.sendVideoNoteReply(convId, payload)}
      />
    </Fade>
  );
}

export default function Video() {
  return <VideoStudioPage backend="wavespeed" />;
}
