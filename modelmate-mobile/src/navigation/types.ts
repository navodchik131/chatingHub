export type CharTab = 'photos' | 'persona' | 'exif' | 'history';
export type BillTier = 'standard' | 'pro';
export type ContentMode = 'sfw' | 'nsfw';
export type GenStatus = 'loading' | 'done';
export type DescGenStatus = 'idle' | 'loading' | 'done';
export type AdminDonTab = 'moderation' | 'stats' | 'all' | 'payouts';

export type TabRoot = 'overview' | 'dialogs' | 'studio' | 'characters' | 'profile';

export type NavigationState = {
  stack: string[];
  chatIdx: number;
  genStatus: Record<string, GenStatus>;
  charTab: CharTab;
  charId: string;
  photoTagPick: boolean;
  photoTagIdx: number;
  descGen: DescGenStatus;
  billTier: BillTier;
  archiveIdx: number;
  opRights: Record<string, boolean>;
  adminSubActive: boolean;
  adminPlanIdx: number;
  adminDonTab: AdminDonTab;
  adminUserIdx: number;
  /** Auth & forms */
  authEmail: string;
  authPassword: string;
  dialogFolderId: 'all' | number;
  newFolderName: string;
  newFolderSelected: number[];
  folderPickerConvId: number | null;
  swipeOpenDialogId: number | null;
  folderEditId: number | null;
  folderEditName: string;
  folderEditSelected: number[];
  threadDraft: string;
  contentMode: ContentMode;
  aiEngine: string;
  imgFormat: string;
  imgChar: string;
  carouselCount: number;
  vidQuality: string;
  vidFormat: string;
  vidDuration: number;
  vidChar: string;
  vidHasFirstFrame: boolean;
  connChar: string;
  newCharName: string;
  charFields: Record<string, string>;
  donationFields: Record<string, string>;
  donationCharIdx: number;
  adminCreditsDelta: string;
  adminSearch: string;
  broadcastSubject: string;
  imgPrompt: string;
  connToken: string;
  opLogin: string;
  opPassword: string;
  adminSubUntil: string;
};

export const IMG_FORMATS = ['9:16', '16:9', '3:4', '4:3', '1:1'] as const;
export const VID_QUALITIES = ['480p', '720p', '1080p'] as const;
export const VID_DURATIONS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] as const;
export const CAROUSEL_COUNTS = [2, 3, 4, 6] as const;

export function enginesForMode(mode: ContentMode): string[] {
  return mode === 'sfw'
    ? ['Nano Banana Pro', 'GPT Image']
    : ['Seedream 5 Pro', 'Wan 2.7 Pro'];
}

export const defaultNavState: NavigationState = {
  stack: ['splash'],
  chatIdx: 0,
  genStatus: {},
  charTab: 'photos',
  charId: 'mia',
  photoTagPick: false,
  photoTagIdx: 0,
  descGen: 'idle',
  billTier: 'standard',
  archiveIdx: 0,
  opRights: { chat: true, studio: true, models: false, keys: false, billing: false },
  adminSubActive: true,
  adminPlanIdx: 0,
  adminDonTab: 'moderation',
  adminUserIdx: 0,
  authEmail: '',
  authPassword: '',
  dialogFolderId: 'all',
  newFolderName: '',
  newFolderSelected: [],
  folderPickerConvId: null,
  swipeOpenDialogId: null,
  folderEditId: null,
  folderEditName: '',
  folderEditSelected: [],
  threadDraft: '',
  contentMode: 'sfw',
  aiEngine: 'Nano Banana Pro',
  imgFormat: '9:16',
  imgChar: 'Mia',
  carouselCount: 3,
  vidQuality: '1080p',
  vidFormat: '9:16',
  vidDuration: 5,
  vidChar: 'Mia',
  vidHasFirstFrame: true,
  connChar: 'Mia',
  newCharName: '',
  charFields: {
    ageCity: '',
    character: '',
    chatStyle: '',
    camera: '',
    geo: '',
    appearance: '',
  },
  donationFields: {
    title: '',
    desc: '',
    min: '',
    usdt: '',
  },
  donationCharIdx: 0,
  adminCreditsDelta: '',
  adminSearch: '',
  broadcastSubject: '',
  imgPrompt: '',
  connToken: '',
  opLogin: '',
  opPassword: '',
  adminSubUntil: '',
};

export function currentRoute(stack: string[]): string {
  return stack[stack.length - 1] ?? 'auth';
}

export function tabRoot(stack: string[]): TabRoot {
  const root = stack[0];
  if (root === 'dialogs' || root === 'studio' || root === 'characters' || root === 'profile') {
    return root;
  }
  return 'overview';
}

export function hideTabBar(stack: string[]): boolean {
  const cur = currentRoute(stack);
  const root = stack[0];
  if (cur === 'auth' || cur === 'splash' || cur === 'thread') return true;
  if (cur === 'newfolder' || cur === 'folder-picker' || cur === 'folder-edit') return true;
  if (cur === 'settings' || cur.startsWith('settings-')) return true;
  if (root === 'admin' || cur === 'admin' || cur.startsWith('admin-')) return true;
  return false;
}
