import type { AppLocale } from '@/src/i18n/prefs';

export type ModeDef = {
  id: string;
  color: string;
  title: string;
  desc: string;
  icon: 'image' | 'user' | 'wand' | 'star' | 'bolt';
};

const MODE_DEFS_RU: ModeDef[] = [
  { id: 'ref', color: '215,244,82', title: 'Кадр по референсу', desc: 'Похожий кадр по образцу', icon: 'image' },
  { id: 'swap', color: '240,168,200', title: 'Face Swap', desc: 'Лицо персонажа на кадр', icon: 'user' },
  { id: 'edit', color: '192,132,252', title: 'Изменить детали', desc: 'Точечно изменить или добавить элемент', icon: 'wand' },
  { id: 'outfit', color: '192,132,252', title: 'Замена одежды', desc: 'Одежда с фото на модель', icon: 'star' },
  { id: 'loc', color: '56,189,248', title: 'Смена локации', desc: 'Новый фон и окружение', icon: 'image' },
  { id: 'prompt', color: '250,204,21', title: 'Кадр по промпту', desc: 'Свободная генерация текстом', icon: 'bolt' },
  { id: 'carousel', color: '74,222,128', title: 'Карусель', desc: 'Серия связанных кадров', icon: 'bolt' },
];

const MODE_DEFS_EN: ModeDef[] = [
  { id: 'ref', color: '215,244,82', title: 'Reference frame', desc: 'Match a reference shot', icon: 'image' },
  { id: 'swap', color: '240,168,200', title: 'Face Swap', desc: 'Put character face on frame', icon: 'user' },
  { id: 'edit', color: '192,132,252', title: 'Edit details', desc: 'Change or add elements', icon: 'wand' },
  { id: 'outfit', color: '192,132,252', title: 'Outfit swap', desc: 'Apply clothing from photo', icon: 'star' },
  { id: 'loc', color: '56,189,248', title: 'Location swap', desc: 'New background and scene', icon: 'image' },
  { id: 'prompt', color: '250,204,21', title: 'Prompt frame', desc: 'Free-form text generation', icon: 'bolt' },
  { id: 'carousel', color: '74,222,128', title: 'Carousel', desc: 'Series of related frames', icon: 'bolt' },
];

const SLOT_LABELS_RU: Record<string, string[]> = {
  ref: ['Референс-кадр'],
  swap: ['Референс-кадр'],
  edit: ['Кадр для изменения', 'Референс для изменения'],
  outfit: ['Кадр', 'Фото одежды'],
  loc: ['Кадр', 'Фото локации'],
  prompt: [],
  carousel: ['Базовый кадр'],
};

const SLOT_LABELS_EN: Record<string, string[]> = {
  ref: ['Reference frame'],
  swap: ['Reference frame'],
  edit: ['Frame to edit', 'Edit reference'],
  outfit: ['Frame', 'Outfit photo'],
  loc: ['Frame', 'Location photo'],
  prompt: [],
  carousel: ['Base frame'],
};

export function getModeDefs(locale: AppLocale): ModeDef[] {
  return locale === 'en' ? MODE_DEFS_EN : MODE_DEFS_RU;
}

export function getSlotLabels(locale: AppLocale): Record<string, string[]> {
  return locale === 'en' ? SLOT_LABELS_EN : SLOT_LABELS_RU;
}
