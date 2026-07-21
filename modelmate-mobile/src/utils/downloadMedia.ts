import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { apiUrl, resolveMediaUrl } from '@/src/api/config';
import { getToken } from '@/src/api/token';

function guessExtension(url: string, mimeType?: string): string {
  const fromMime: Record<string, string> = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'video/mp4': 'mp4',
    'video/quicktime': 'mov',
  };
  if (mimeType && fromMime[mimeType]) return fromMime[mimeType];
  const match = url.split('?')[0].match(/\.([a-z0-9]{2,5})$/i);
  return match?.[1]?.toLowerCase() || 'bin';
}

function resolveDownloadUrl(url: string): string {
  const resolved = resolveMediaUrl(url);
  if (/^https?:\/\//i.test(resolved)) return resolved;
  return apiUrl(resolved.startsWith('/') ? resolved : `/${resolved}`);
}

export async function downloadMedia(
  url: string,
  opts?: { filename?: string; mimeType?: string },
): Promise<void> {
  const fullUrl = resolveDownloadUrl(url);
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const ext = guessExtension(fullUrl, opts?.mimeType);
  const baseName = opts?.filename?.replace(/[^\w.\-()]+/g, '_') || `modelmate-${Date.now()}.${ext}`;
  const dest = `${FileSystem.cacheDirectory}${baseName}`;

  const result = await FileSystem.downloadAsync(fullUrl, dest, { headers });
  if (result.status < 200 || result.status >= 300) {
    throw new Error(`Не удалось скачать файл (${result.status})`);
  }

  if (!(await Sharing.isAvailableAsync())) {
    throw new Error('Сохранение недоступно на этом устройстве');
  }
  await Sharing.shareAsync(result.uri, {
    mimeType: opts?.mimeType || result.headers?.['content-type'] || undefined,
    dialogTitle: 'Сохранить файл',
  });
}
