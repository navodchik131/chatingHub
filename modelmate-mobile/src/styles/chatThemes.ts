import { color } from '@/src/styles/tokens';

export type ChatThemeId = 'default' | 'ocean' | 'emerald' | 'sunset' | 'mono';

export type ChatTheme = {
  id: ChatThemeId;
  label: string;
  swatch: [string, string] | [string];
  background: string;
};

export const CHAT_THEMES: ChatTheme[] = [
  {
    id: 'default',
    label: 'Тёмная',
    swatch: ['#1b1f2a', '#141824'],
    background: color.threadBg,
  },
  {
    id: 'ocean',
    label: 'Океан',
    swatch: ['#0E3B5C', '#0A1F33'],
    background: '#0A1F33',
  },
  {
    id: 'emerald',
    label: 'Изумруд',
    swatch: ['#0F5132', '#0A2E1D'],
    background: '#0A2E1D',
  },
  {
    id: 'sunset',
    label: 'Закат',
    swatch: ['#5C2A1E', '#2E140F'],
    background: '#2E140F',
  },
  {
    id: 'mono',
    label: 'Чёрная',
    swatch: ['#0A0B0D'],
    background: '#0A0B0D',
  },
];

export function chatThemeById(id?: string | null): ChatTheme {
  return CHAT_THEMES.find((t) => t.id === id) || CHAT_THEMES[0];
}
