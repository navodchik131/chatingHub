import { apiJsonOptional } from '@/src/api/client';
import { isArchivePending } from '@/src/api/media';
import type { StudioGenerationOut } from '@/src/api/types';

function archiveItemPollKey(item: StudioGenerationOut): string {
  return [
    item.id,
    item.status || '',
    item.image_url || '',
    item.video_url || '',
    item.error_message || '',
    item.job_id || '',
  ].join('|');
}

function dedupeById(items: StudioGenerationOut[]): StudioGenerationOut[] {
  const seen = new Set<number>();
  return items.filter((g) => {
    if (seen.has(g.id)) return false;
    seen.add(g.id);
    return true;
  });
}

export async function refreshPendingArchiveImages(current: StudioGenerationOut[]) {
  const tracked = current.filter((g) => isArchivePending(g));
  if (!tracked.length) return { items: current, changed: false };

  const pending = await apiJsonOptional<{ items: StudioGenerationOut[] }>(
    '/api/studio/generations/pending?media_kind=image',
    {},
    { items: [] },
  );
  const pendingItems = pending.items || [];
  const pendingById = new Map(pendingItems.map((p) => [p.id, p]));
  let changed = false;
  const maybeCompletedIds: number[] = [];

  let next = current.map((g) => {
    if (!isArchivePending(g)) return g;
    const upd = pendingById.get(g.id);
    if (upd) {
      const merged = { ...g, ...upd };
      if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true;
      return merged;
    }
    maybeCompletedIds.push(g.id);
    return g;
  });

  if (maybeCompletedIds.length) {
    const page = await apiJsonOptional<{ items: StudioGenerationOut[] }>(
      '/api/studio/generations?limit=40&skip=0&media_kind=image',
      {},
      { items: [] },
    );
    const freshById = new Map((page.items || []).map((p) => [p.id, p]));
    next = next.map((g) => {
      if (!maybeCompletedIds.includes(g.id)) return g;
      const fresh = freshById.get(g.id);
      if (!fresh) return g;
      const merged = { ...g, ...fresh };
      if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true;
      return merged;
    });
  }

  return { items: dedupeById(next), changed };
}
