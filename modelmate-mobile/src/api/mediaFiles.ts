import * as FileSystem from 'expo-file-system/legacy';
import { apiUrl, resolveMediaUrl } from '@/src/api/config';
import { getToken } from '@/src/api/token';
import type { LocalFile } from '@/src/api/types';

function resolveFetchUrl(url: string): string {
  const resolved = resolveMediaUrl(url);
  if (/^https?:\/\//i.test(resolved)) return resolved;
  return apiUrl(resolved.startsWith('/') ? resolved : `/${resolved}`);
}

/** Скачивает удалённое изображение во временный файл для FormData в React Native. */
export async function remoteImageToLocalFile(url: string, name: string): Promise<LocalFile> {
  const fullUrl = resolveFetchUrl(url);
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const dest = `${FileSystem.cacheDirectory}${name.replace(/[^\w.\-]+/g, '_')}`;
  const result = await FileSystem.downloadAsync(fullUrl, dest, { headers });
  if (result.status < 200 || result.status >= 300) {
    throw new Error(`Не удалось загрузить файл (${result.status})`);
  }
  const ext = name.split('.').pop()?.toLowerCase() || 'jpg';
  const mime = ext === 'png' ? 'image/png' : ext === 'webp' ? 'image/webp' : 'image/jpeg';
  return { uri: result.uri, name, type: mime };
}
