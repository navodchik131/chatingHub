/** Video archive helpers for Telegram video notes (mirrors web studioArchive). */

export type VideoArchiveItem = {
  id: number;
  media_kind?: string;
  video_url?: string | null;
  motion_render_id?: number | null;
};

const OPTIMISTIC_FLOOR = -1_000_000_000;

export function isMotionRenderArchiveId(id: number): boolean {
  return id < 0 && id > OPTIMISTIC_FLOOR;
}

export function motionRenderIdFromItem(item: VideoArchiveItem): number | null {
  const explicit = item.motion_render_id;
  if (explicit != null && explicit > 0) return explicit;
  if (isMotionRenderArchiveId(item.id)) return -item.id;
  return null;
}

export function videoNoteDownloadPath(item: VideoArchiveItem): string | null {
  const renderId = motionRenderIdFromItem(item);
  if (renderId != null) return `/api/studio/motion/renders/${renderId}/video-note`;
  if (item.media_kind === 'video' && item.id > 0) {
    return `/api/studio/generations/${item.id}/video-note`;
  }
  return null;
}

export function videoNoteSendPayload(item: VideoArchiveItem): {
  renderId?: number;
  generationId?: number;
} | null {
  const renderId = motionRenderIdFromItem(item);
  if (renderId != null) return { renderId };
  if (item.media_kind === 'video' && item.id > 0) return { generationId: item.id };
  return null;
}

export type MotionRenderListItem = {
  id: number;
  created_at?: string;
  studio_generation_id?: number | null;
  studio_model_id?: number | null;
  video_url?: string | null;
  frame_image_url?: string | null;
};

export function mergeMotionRendersIntoVideoArchive<T extends VideoArchiveItem & {
  image_url?: string;
  status?: string;
}>(generations: T[], motionRenders: MotionRenderListItem[]): T[] {
  const enriched = generations.map((g) => ({ ...g }));
  const extra: T[] = [];

  for (const r of motionRenders) {
    const url = (r.video_url || '').trim();
    if (!url) continue;
    const gid = r.studio_generation_id;
    if (gid != null) {
      const idx = enriched.findIndex((g) => g.id === gid && g.media_kind === 'video');
      if (idx >= 0) {
        const cur = enriched[idx];
        let next = { ...cur, motion_render_id: r.id } as T;
        if (!(cur.video_url || '').trim()) {
          next = { ...next, video_url: url, status: 'ready' } as T;
        }
        if (r.frame_image_url && !(cur as { image_url?: string }).image_url) {
          next = { ...next, image_url: r.frame_image_url } as T;
        }
        enriched[idx] = next;
        continue;
      }
    }
    extra.push({
      id: -r.id,
      created_at: r.created_at,
      status: 'ready',
      media_kind: 'video',
      image_url: r.frame_image_url || url,
      video_url: url,
      studio_model_id: r.studio_model_id,
      motion_render_id: r.id,
    } as T);
  }

  return [...enriched, ...extra].sort(
    (a, b) => (Date.parse(String(b.created_at || '')) || 0) - (Date.parse(String(a.created_at || '')) || 0),
  );
}
