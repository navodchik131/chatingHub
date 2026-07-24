import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import { apiUrl, resolveMediaUrl } from '@/src/api/config';
import { getToken } from '@/src/api/token';
import type { LocalFile } from '@/src/api/types';

/** React Native FormData принимает только { uri, name, type }, не Blob/File. */
export function appendFormDataFile(fd: FormData, field: string, file: LocalFile): void {
  fd.append(field, {
    uri: file.uri,
    name: file.name || 'upload.bin',
    type: file.type || 'application/octet-stream',
  } as never);
}

/** content:// и ph:// на Android копируем в cache — иначе fetch/FormData падает. */
export async function prepareUploadFile(file: LocalFile): Promise<LocalFile> {
  const uri = file.uri || '';
  if (
    Platform.OS === 'web'
    || uri.startsWith('file://')
    || (!uri.startsWith('content://') && !uri.startsWith('ph://'))
  ) {
    return file;
  }
  const safeName = (file.name || 'upload.jpg').replace(/[^\w.\-]+/g, '_');
  const dest = `${FileSystem.cacheDirectory}upload-${Date.now()}-${safeName}`;
  await FileSystem.copyAsync({ from: uri, to: dest });
  return { ...file, uri: dest };
}

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
