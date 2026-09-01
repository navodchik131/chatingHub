import { FALLBACK_GEN_MODELS } from './studioHelpers';

/** Локализация pipeline_key из API архива. */
const PIPELINE_RU = {
  image_model_scene: 'Модель + сцена',
  image_model: 'Только модель',
  image_photo_edit: 'Доработка фото',
  image_face_swap: 'Face swap',
  image_no_face: 'Без лица',
  image_grok_compose: 'Grok compose',
  image_carousel: 'Карусель',
  image_carousel_shot: 'Кадр карусели',
  image_upscale: 'Апскейл',
  image_shot_batch: 'Shot batch',
  image_workflow: 'Workflow',
  image_bootstrap: 'Создание модели',
  image_outfit: 'Образ',
  video_motion_control: 'Motion Control',
  video_motion_control_outline: 'Motion Control · силуэт',
  video_motion_swap: 'Motion swap',
  video_motion_swap_outline: 'Motion swap · силуэт',
  video_prompt: 'Промпт → видео',
  video_grok: 'Grok Imagine',
  video_seedance_sale: 'Seedance Sale',
  video_seedance_director: 'Seedance Director',
};

const PIPELINE_EN = {
  image_model_scene: 'Model + scene',
  image_model: 'Model only',
  image_photo_edit: 'Photo edit',
  image_face_swap: 'Face swap',
  image_no_face: 'No face',
  image_grok_compose: 'Grok compose',
  image_carousel: 'Carousel',
  image_carousel_shot: 'Carousel shot',
  image_upscale: 'Upscale',
  image_shot_batch: 'Shot batch',
  image_workflow: 'Workflow',
  image_bootstrap: 'Model bootstrap',
  image_outfit: 'Outfit',
  video_motion_control: 'Motion Control',
  video_motion_control_outline: 'Motion Control · silhouette',
  video_motion_swap: 'Motion swap',
  video_motion_swap_outline: 'Motion swap · silhouette',
  video_prompt: 'Prompt → video',
  video_grok: 'Grok Imagine',
  video_seedance_sale: 'Seedance Sale',
  video_seedance_director: 'Seedance Director',
};

function resolveEngineLabel(engine, engineId) {
  const raw = (engine || engineId || '').trim();
  if (!raw) return '';
  const hit = FALLBACK_GEN_MODELS.find((m) => m.id === raw);
  return hit?.label || raw;
}

/** Строка для бейджа на карточке архива: «режим · движок». */
export function formatArchivePipelineLabel(item, lang) {
  const key = (item?.pipeline_key || '').trim();
  const engine = resolveEngineLabel(item?.engine_label, item?.engine_id);
  const dict = lang === 'ru' ? PIPELINE_RU : PIPELINE_EN;
  const mode = dict[key] || key;
  if (mode && engine) return `${mode} · ${engine}`;
  if (mode) return mode;
  if (engine) return engine;
  return '';
}
