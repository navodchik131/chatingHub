import { resolveMediaUrl } from '@/src/api/config';
import type { StudioGenerationOut } from '@/src/api/types';

/** Keep prior signed media URL when only the JWT query changed (disk/browser cache). */
export function preferStableMediaUrl(prev?: string | null, next?: string | null): string {
  const p = (prev || '').trim();
  const n = (next || '').trim();
  if (!n) return p;
  if (!p) return n;
  if (p === n) return p;
  const pBase = p.split('?')[0];
  const nBase = n.split('?')[0];
  if (
    pBase === nBase &&
    (pBase.includes('/api/studio/public-generation-image') ||
      pBase.includes('/api/studio/public-generation-video') ||
      pBase.includes('/api/studio/public-model-image'))
  ) {
    return p;
  }
  return n;
}

export function isArchivePending(item: StudioGenerationOut | null | undefined): boolean {
  if (!item) return false;
  const st = (item.status || '').trim();
  if (st === 'processing' || st === 'archiving') return true;
  if (st === 'failed' || st === 'ready') return false;
  if (st === 'provider_ready') {
    if (item.media_kind === 'video') return !(item.video_url || '').trim();
    return !(item.image_url || '').trim();
  }
  return false;
}

export function archiveThumbUrl(item: StudioGenerationOut | null | undefined): string {
  if (!item) return '';
  if (item.media_kind === 'video') {
    const poster = (item.image_url || '').trim();
    if (poster) return resolveMediaUrl(poster);
    return resolveMediaUrl(item.video_url);
  }
  return resolveMediaUrl(item.image_url);
}
