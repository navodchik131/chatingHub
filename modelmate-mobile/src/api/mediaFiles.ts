import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import { File as ExpoFile } from 'expo-file-system';
import { apiUrl, resolveMediaUrl } from '@/src/api/config';
import { getToken } from '@/src/api/token';
import type { LocalFile } from '@/src/api/types';

/**
 * Expo 57 подменяет global fetch на expo/fetch — он не понимает RN-объект { uri, name, type }.
 * Для native используем expo-file-system File (совместим с expo/fetch FormData).
 */
export async function appendFormDataFile(fd: FormData, field: string, file: LocalFile): Promise<void> {
  const uri = (file.uri || '').trim();
  if (!uri) throw new Error('Файл не выбран');

  if (Platform.OS === 'web') {
    const response = await fetch(uri);
    const blob = await response.blob();
    const name = file.name || 'upload.bin';
    const type = file.type || blob.type || 'application/octet-stream';
    fd.append(field, new window.File([blob], name, { type }));
    return;
  }

  fd.append(field, new ExpoFile(uri) as never);
}

/** content:// и ph:// на Android копируем в cache — иначе File/FormData не прочитает файл. */
export async function prepareUploadFile(file: LocalFile): Promise<LocalFile> {
  if (Platform.OS === 'web') return file;

  let uri = (file.uri || '').trim();
  if (!uri) throw new Error('Файл не выбран');

  const needsCopy =
    uri.startsWith('content://')
    || uri.startsWith('ph://')
    || uri.startsWith('assets-library://');

  if (needsCopy) {
    const safeName = (file.name || 'upload.jpg').replace(/[^\w.\-]+/g, '_');
    const dest = `${FileSystem.cacheDirectory}upload-${Date.now()}-${safeName}`;
    await FileSystem.copyAsync({ from: uri, to: dest });
    return { ...file, uri: dest };
  }

  if (!uri.startsWith('file://') && uri.startsWith('/')) {
    uri = `file://${uri}`;
  }

  return { ...file, uri };
}

function resolveFetchUrl(url: string): string {
  const resolved = resolveMediaUrl(url);
  if (/^https?:\/\//i.test(resolved)) return resolved;
  return apiUrl(resolved.startsWith('/') ? resolved : `/${resolved}`);
}

/** Скачивает удалённое изображение во временный файл для FormData. */
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
