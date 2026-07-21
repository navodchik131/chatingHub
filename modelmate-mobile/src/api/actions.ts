import { apiFetch, apiJson, apiJsonOptional } from '@/src/api/client';
import { normalizePhotoKind } from '@/src/api/helpers';
import { postStudioJobStart, waitForStudioJobResult } from '@/src/api/studioJobs';
import type { LocalFile, HealthOut, StudioGenerationOut, StudioModelOut } from '@/src/api/types';
import { apiUrl, getApiBaseUrl } from '@/src/api/config';
import { archiveThumbUrl } from '@/src/api/media';
import MMOS_STUDIO_SCENARIOS from '@/src/studio/mmOsStudioScenarios';
import {
  isNsfwMode,
  normalizeWaveModel,
  waveModelFromState,
} from '@/src/studio/studioHelpers';

function dedupeArchive(items: StudioGenerationOut[]): StudioGenerationOut[] {
  const seen = new Set<number>();
  return items.filter((g) => {
    if (seen.has(g.id)) return false;
    seen.add(g.id);
    return true;
  });
}

export async function login(email: string, password: string, memberLogin?: string) {
  const body: Record<string, string> = { email: email.trim(), password };
  if (memberLogin?.trim()) body.member_login = memberLogin.trim();
  return apiJson<{ access_token: string; token_type: string }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function register(email: string, password: string) {
  return apiJson<{ access_token: string; token_type: string }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email: email.trim(), password }),
  });
}

export async function fetchHealth() {
  return apiJsonOptional<HealthOut>('/api/health', {}, {});
}

export async function fetchMe() {
  return apiJson('/api/auth/me');
}

export async function fetchConversations() {
  return apiJsonOptional('/api/conversations', {}, []);
}

export async function fetchConversationFolders() {
  return apiJsonOptional('/api/conversation-folders', {}, []);
}

export async function createConversationFolder(name: string, conversationIds: number[] = []) {
  return apiJson('/api/conversation-folders', {
    method: 'POST',
    body: JSON.stringify({ name, conversation_ids: conversationIds }),
  });
}

export async function patchConversationFolder(
  folderId: number,
  patch: { name?: string; conversation_ids?: number[] },
) {
  return apiJson(`/api/conversation-folders/${folderId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function deleteConversationFolder(folderId: number) {
  await apiFetch(`/api/conversation-folders/${folderId}`, { method: 'DELETE' });
}

export async function addConversationToFolder(folderId: number, convId: number) {
  return apiJson(`/api/conversation-folders/${folderId}/conversations/${convId}`, {
    method: 'POST',
    body: '{}',
  });
}

export async function fetchMessages(convId: number) {
  return apiJson(`/api/conversations/${convId}/messages?limit=50`);
}

export async function markConversationRead(convId: number) {
  await apiFetch(`/api/conversations/${convId}/read`, { method: 'POST' });
}

export async function sendReply(convId: number, text: string) {
  return apiJson(`/api/conversations/${convId}/reply`, {
    method: 'POST',
    body: JSON.stringify({ text: text.trim() }),
  });
}

export async function refreshArchiveImages() {
  const [page, pending] = await Promise.all([
    fetchArchiveImagesPage(0),
    apiJsonOptional<{ items: StudioGenerationOut[] }>(
      '/api/studio/generations/pending?media_kind=image',
      {},
      { items: [] },
    ),
  ]);
  return dedupeArchive([...(page.items || []), ...(pending.items || [])]);
}

export async function fetchArchiveImagesPage(skip = 0, limit = 40) {
  return apiJsonOptional<{ items: StudioGenerationOut[] }>(
    `/api/studio/generations?limit=${limit}&skip=${skip}&media_kind=image`,
    {},
    { items: [] },
  );
}

export async function loadMoreArchiveImages(skip: number, limit = 40) {
  const page = await fetchArchiveImagesPage(skip, limit);
  return page.items || [];
}

export async function refreshArchiveVideos() {
  const [page, pending, motion] = await Promise.all([
    fetchArchiveVideosPage(0),
    apiJsonOptional<{ items: StudioGenerationOut[] }>(
      '/api/studio/generations/pending?media_kind=video',
      {},
      { items: [] },
    ),
    apiJsonOptional<{ items: StudioGenerationOut[] }>(
      '/api/studio/motion/renders?limit=40&skip=0',
      {},
      { items: [] },
    ),
  ]);
  const motionItems = Array.isArray(motion?.items) ? motion.items : [];
  return dedupeArchive([...(page.items || []), ...(pending.items || []), ...motionItems]);
}

export async function fetchArchiveVideosPage(skip = 0, limit = 40) {
  return apiJsonOptional<{ items: StudioGenerationOut[] }>(
    `/api/studio/generations?limit=${limit}&skip=${skip}&media_kind=video`,
    {},
    { items: [] },
  );
}

export async function loadMoreArchiveVideos(skip: number, limit = 40) {
  const page = await fetchArchiveVideosPage(skip, limit);
  return page.items || [];
}

export async function fetchModels() {
  return apiJsonOptional('/api/studio/models', {}, []);
}

export async function fetchIntegrations() {
  return apiJsonOptional('/api/integrations', {}, null);
}

export async function fetchBillingPlans() {
  return apiJsonOptional('/api/billing/plans', {}, null);
}

export async function fetchCreditHistory() {
  return apiJsonOptional('/api/workspace/credit-history?limit=40&skip=0', {}, { items: [] });
}

export async function fetchMembers() {
  return apiJsonOptional('/api/workspace/members', {}, []);
}

export async function fetchChatterStats() {
  return apiJsonOptional('/api/workspace/chatter-stats/summary', {}, null);
}

export async function fetchDonationEvents() {
  return apiJsonOptional('/api/creator-donations/events?limit=50', {}, []);
}

export async function fetchDonationOverview() {
  return apiJsonOptional('/api/creator-donations/overview', {}, null);
}

export async function fetchDonations() {
  return apiJsonOptional('/api/creator-donations', {}, []);
}

export async function fetchPayoutSettings() {
  return apiJsonOptional('/api/creator-donations/payout-settings', {}, null);
}

export async function savePayoutSettings(walletAddress: string) {
  return apiJson('/api/creator-donations/payout-settings', {
    method: 'PUT',
    body: JSON.stringify({ wallet_address: walletAddress, asset: 'USDT' }),
  });
}

export async function requestDonationPayout(currency = 'RUB') {
  return apiJson('/api/creator-donations/payout-requests', {
    method: 'POST',
    body: JSON.stringify({ source_currency: currency }),
  });
}

export async function saveDonationLink(payload: Record<string, unknown>, editingId?: number) {
  if (editingId) {
    return apiJson(`/api/creator-donations/${editingId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }
  return apiJson('/api/creator-donations', { method: 'POST', body: JSON.stringify(payload) });
}

export async function addWorkspaceMember(payload: Record<string, unknown>) {
  return apiJson('/api/workspace/members', { method: 'POST', body: JSON.stringify(payload) });
}

export async function updateWorkspaceMember(memberId: number, payload: Record<string, unknown>) {
  return apiJson(`/api/workspace/members/${memberId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export async function deleteWorkspaceMember(memberId: number) {
  return apiJson(`/api/workspace/members/${memberId}`, { method: 'DELETE' });
}

export async function createStudioModel(name: string) {
  const fd = new FormData();
  fd.append('name', name.trim());
  fd.append('profile_text', '');
  const res = await apiFetch('/api/studio/models', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось создать персонажа');
  return data;
}

export async function patchStudioModel(id: number, patch: Record<string, unknown>) {
  return apiJson(`/api/studio/models/${id}`, { method: 'PATCH', body: JSON.stringify(patch) });
}

export async function uploadStudioModelImage(charId: number, file: LocalFile, kind: string) {
  const fd = new FormData();
  fd.append('images', { uri: file.uri, name: file.name, type: file.type } as unknown as Blob);
  fd.append('image_kinds', JSON.stringify([normalizePhotoKind(kind)]));
  const res = await apiFetch(`/api/studio/models/${charId}/images`, { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить фото');
  return data;
}

export async function uploadPhoneExifReference(modelId: number, role: 'selfie' | 'main', file: LocalFile) {
  const fd = new FormData();
  fd.append('role', role);
  fd.append('image', { uri: file.uri, name: file.name, type: file.type } as unknown as Blob);
  const res = await apiFetch(`/api/studio/models/${modelId}/phone-exif-reference`, { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить EXIF-эталон');
  return data;
}

export async function fetchSupportTickets() {
  return apiJsonOptional<import('@/src/api/types').SupportTicketListItemOut[]>('/api/support/tickets', {}, []);
}

export async function fetchSupportTicket(ticketId: number) {
  return apiJson<import('@/src/api/types').SupportTicketOut>(`/api/support/tickets/${ticketId}`);
}

export async function createSupportTicket(payload: { type: string; subject: string; message: string }) {
  return apiJson<import('@/src/api/types').SupportTicketOut>('/api/support/tickets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function patchProfileEmail(email: string) {
  return apiJson('/api/auth/profile', {
    method: 'PATCH',
    body: JSON.stringify({ email: email.trim() }),
  });
}

export async function changePassword(currentPassword: string, newPassword: string) {
  return apiJson('/api/auth/password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export async function generateStudioModelProfile(model: StudioModelOut) {
  const images = model.images || [];
  if (!images.length) throw new Error('Сначала загрузите фото персонажа');
  const fd = new FormData();
  let appended = 0;
  for (const im of images.slice(0, 8)) {
    const path = im.url.startsWith('http') ? im.url.replace(getApiBaseUrl(), '') : im.url;
    const res = await apiFetch(path.startsWith('/') ? path : im.url);
    if (!res.ok) continue;
    const blob = await res.blob();
    const reader = new FileReader();
    const dataUrl = await new Promise<string>((resolve, reject) => {
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    fd.append('images', {
      uri: dataUrl,
      name: `model-${im.id}.jpg`,
      type: blob.type || 'image/jpeg',
    } as unknown as Blob);
    appended += 1;
  }
  if (!appended) throw new Error('Не удалось прочитать фото модели');
  const res = await apiFetch('/api/studio/models/generate-profile', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Генерация не удалась');
  return data;
}

export async function saveTelegramBot(token: string, studioModelId?: number) {
  const body: Record<string, unknown> = { bot_token: token };
  if (studioModelId) body.studio_model_id = studioModelId;
  return apiJson('/api/integrations/telegram', { method: 'PUT', body: JSON.stringify(body) });
}

export async function deleteTelegramConnection(connectionId: number) {
  return apiJson(`/api/integrations/telegram/${connectionId}`, { method: 'DELETE' });
}

export async function deleteFanvueConnection(connectionId: number) {
  return apiJson(`/api/integrations/fanvue?connection_id=${connectionId}`, { method: 'DELETE' });
}

export async function deleteTributeConnection(connectionId: number) {
  return apiJson(`/api/integrations/tribute?connection_id=${connectionId}`, { method: 'DELETE' });
}

export async function saveTributeKey(apiKey: string, studioModelId?: number) {
  const body: Record<string, unknown> = { api_key: apiKey };
  if (studioModelId) body.studio_model_id = studioModelId;
  return apiJson('/api/integrations/tribute', { method: 'PUT', body: JSON.stringify(body) });
}

export async function payYookassa(product: string, creditsQuantity?: number) {
  const body: Record<string, unknown> = { product };
  if (product === 'credits_pack' && creditsQuantity) body.credits_quantity = creditsQuantity;
  return apiJson('/api/billing/yookassa/payment', { method: 'POST', body: JSON.stringify(body) });
}

export async function payTributeCheckout(product: string, creditsQuantity?: number) {
  const body: Record<string, unknown> = { product };
  if (product === 'credits_pack' && creditsQuantity) body.credits_quantity = creditsQuantity;
  return apiJson('/api/billing/tribute/checkout', { method: 'POST', body: JSON.stringify(body) });
}

export async function fetchAdminStats() {
  return apiJsonOptional('/api/admin/stats?chart_days=30', {}, null);
}

export async function fetchAdminUsers(search = '') {
  const q = new URLSearchParams();
  q.set('limit', '200');
  if (search.trim()) q.set('q', search.trim());
  return apiJsonOptional(`/api/admin/users?${q}`, {}, []);
}

export async function patchAdminUserSubscription(userId: number, payload: Record<string, unknown>) {
  return apiJson(`/api/admin/users/${userId}/subscription`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function adjustAdminUserCredits(userId: number, delta: number) {
  return apiJson(`/api/admin/users/${userId}/credits`, {
    method: 'POST',
    body: JSON.stringify({ delta }),
  });
}

export async function resetAdminUserPassword(userId: number, password: string) {
  return apiJson(`/api/admin/users/${userId}/password`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}

export async function sendAdminCampaign(subject: string) {
  return apiJson('/api/admin/email/campaigns', {
    method: 'POST',
    body: JSON.stringify({ subject, segment: 'inactive_30d' }),
  });
}

export async function fetchExifBotStats() {
  return apiJsonOptional('/api/admin/exif-bot/stats', {}, null);
}

export async function fetchExifBotUsers() {
  return apiJsonOptional('/api/admin/exif-bot/users?limit=50', {}, []);
}

export async function fetchIgBotStats() {
  return apiJsonOptional('/api/admin/ig-bot/stats', {}, null);
}

export async function fetchIgBotUsers() {
  return apiJsonOptional('/api/admin/ig-bot/users?limit=50', {}, []);
}

function appendLocalFile(fd: FormData, field: string, file: LocalFile) {
  fd.append(field, { uri: file.uri, name: file.name, type: file.type } as unknown as Blob);
}

export async function uploadWorkflowReference(file: LocalFile): Promise<string> {
  const fd = new FormData();
  appendLocalFile(fd, 'file', file);
  const res = await apiFetch('/api/studio/workflow/reference', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить референс');
  if (!data.ref_id) throw new Error('Сервер не вернул ref_id');
  return data.ref_id;
}

export async function uploadMotionDrivingVideo(file: LocalFile): Promise<string> {
  const fd = new FormData();
  appendLocalFile(fd, 'video', file);
  const res = await apiFetch('/api/studio/motion/upload-driving-video', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить видео');
  const id = String(data.motion_video_file_id || '').trim();
  if (!id) throw new Error('Сервер не вернул id видео');
  return id;
}

let cachedDemoWorkflowWorkspaceId: number | null = null;

async function resolveDemoWorkflowWorkspaceId(): Promise<number | null> {
  if (cachedDemoWorkflowWorkspaceId != null) return cachedDemoWorkflowWorkspaceId;
  const list = await apiJsonOptional<{ id: number }[]>('/api/studio/workflow/workspaces', {}, []);
  const id = Array.isArray(list) && list[0]?.id != null ? Number(list[0].id) : null;
  if (id) cachedDemoWorkflowWorkspaceId = id;
  return id;
}

export async function executeWorkflowGraph(
  graph: unknown,
  targetNodeId: string,
  workflowDemoLimited = false,
) {
  const fd = new FormData();
  fd.append('graph', JSON.stringify(graph));
  fd.append('target_node_id', targetNodeId);
  if (workflowDemoLimited) {
    const wsId = await resolveDemoWorkflowWorkspaceId();
    if (!wsId) throw new Error('Не найден workflow-проект для демо-тарифа.');
    fd.append('workspace_id', String(wsId));
  }
  return postStudioJobStart('/api/studio/workflow/execute', { method: 'POST', body: fd });
}

function slotUploadKey(mode: string, index: number) {
  if (mode === 'outfit') return index === 0 ? 'ref' : 'outfit-cloth';
  if (mode === 'loc' || mode === 'location') return index === 0 ? 'ref' : 'location-photo';
  if (mode === 'carousel') return 'carousel';
  return 'ref';
}

function slotStateKey(mode: string, index: number) {
  return `${mode}:${index}`;
}

function resolveSlotSource(
  mode: string,
  index: number,
  uploadFiles: Record<string, LocalFile | undefined>,
  slotArchivePicks: Record<string, number | undefined>,
) {
  const uploadKey = slotUploadKey(mode, index);
  return {
    file: uploadFiles[uploadKey] ?? null,
    archiveId: slotArchivePicks[slotStateKey(mode, index)] ?? null,
    uploadKey,
    slotKey: slotStateKey(mode, index),
  };
}

export async function runImageGeneration(params: {
  modeId: string;
  navState: Record<string, unknown>;
  uploadFiles: Record<string, LocalFile | undefined>;
  slotArchivePicks: Record<string, number | undefined>;
  selectedModelId: number | null;
  archiveImages: StudioGenerationOut[];
  workflowDemoLimited?: boolean;
}) {
  const mode = params.modeId === 'loc' ? 'location' : params.modeId;
  const modelId = params.selectedModelId;
  const needsModel = mode === 'ref' || mode === 'swap' || mode === 'prompt';
  if (needsModel && !modelId) throw new Error('Выберите персонажа');

  const appState = {
    contentMode: String(params.navState.contentMode || 'sfw'),
    aiEngine: String(params.navState.aiEngine || ''),
    imgFormat: String(params.navState.imgFormat || '9:16'),
    studioPrompt: String(params.navState.imgPrompt || ''),
  };

  const store = {
    selectedAspect: params.navState.imgFormat || '9:16',
    uploadFiles: params.uploadFiles,
    slotArchivePicks: params.slotArchivePicks,
    archiveImages: params.archiveImages,
    selectedModelId: modelId,
  };

  const bridgeApi = {
    apiFetch,
    readJson: async (r: Response) => r.json().catch(() => ({})),
    formatDetail: (d: { detail?: unknown }) => (typeof d?.detail === 'string' ? d.detail : ''),
  };

  const helpers = {
    normalizeWaveModel,
    waveModelFromState: () => waveModelFromState(appState),
    isNsfwMode: () => isNsfwMode(appState),
    slotStateKey,
    slotUploadKey,
    resolveSlotSource: (m: string, i: number) =>
      resolveSlotSource(m, i, params.uploadFiles, params.slotArchivePicks),
    userPrompt: String(params.navState.imgPrompt || ''),
  };

  if (mode === 'carousel') {
    const fd = new FormData();
    fd.append('model_id', String(modelId));
    fd.append('count', String(params.navState.carouselCount || 3));
    fd.append('description', String(params.navState.imgPrompt || ''));
    fd.append('output_aspect', String(params.navState.imgFormat || '9:16'));
    fd.append('studio_wave_profile', isNsfwMode(appState) ? 'nsfw' : 'regular');
    const wave = normalizeWaveModel(waveModelFromState(appState), isNsfwMode(appState));
    fd.append('workflow_wave_model', wave.apiId);
    if (wave.tier) fd.append('wan_edit_tier', wave.tier);
    const carouselFile = params.uploadFiles.carousel;
    if (carouselFile) appendLocalFile(fd, 'image', carouselFile);
    return postStudioJobStart('/api/studio/carousel', { method: 'POST', body: fd });
  }

  if (mode === 'edit') {
    const needsRef = String(params.navState.editNeedsRef || '') === 'yes';
    const frameFile = params.uploadFiles['edit-frame'] ?? params.uploadFiles.ref;
    if (!frameFile) throw new Error('Загрузите кадр для изменения');
    if (!String(params.navState.imgPrompt || '').trim()) throw new Error('Опишите, что нужно изменить');
    if (needsRef && !modelId) throw new Error('Выберите персонажа');
    const fd = new FormData();
    fd.append('studio_mode', 'photo_edit');
    fd.append('description', String(params.navState.imgPrompt || ''));
    fd.append('output_aspect', String(params.navState.imgFormat || '9:16'));
    fd.append('studio_wave_profile', isNsfwMode(appState) ? 'nsfw' : 'regular');
    const wave = normalizeWaveModel(waveModelFromState(appState), isNsfwMode(appState));
    fd.append('workflow_wave_model', wave.apiId);
    if (wave.tier) fd.append('wan_edit_tier', wave.tier);
    appendLocalFile(fd, 'image', frameFile);
    if (needsRef && modelId) fd.append('model_id', String(modelId));
    const refFile = params.uploadFiles['edit-ref'];
    if (needsRef && refFile) appendLocalFile(fd, 'inpaint_mask', refFile);
    return postStudioJobStart('/api/studio/refine-prompt', { method: 'POST', body: fd });
  }

  const built = await MMOS_STUDIO_SCENARIOS.buildGraphForMode(mode, {
    API: bridgeApi,
    store,
    archiveThumbUrl,
    s: appState,
    modelId,
    userPrompt: String(params.navState.imgPrompt || ''),
    helpers,
  });
  if (!built) throw new Error('Неизвестный режим генерации');
  return executeWorkflowGraph(built.graph, built.targetNodeId, params.workflowDemoLimited);
}

export async function runMotionFirstFrame(params: {
  modelId: number;
  aspect: string;
  nsfw: boolean;
  videoFile?: LocalFile;
  frameFile?: LocalFile;
  existingGenerationId?: number | null;
  description?: string;
}) {
  const fd = new FormData();
  fd.append('model_id', String(params.modelId));
  fd.append('output_aspect', params.aspect || '9:16');
  fd.append('studio_wave_profile', params.nsfw ? 'nsfw' : 'regular');
  if (params.videoFile) appendLocalFile(fd, 'video', params.videoFile);
  if (params.frameFile) appendLocalFile(fd, 'first_frame_image', params.frameFile);
  if (params.existingGenerationId) {
    fd.append('existing_generation_id', String(params.existingGenerationId));
  }
  if (params.description) fd.append('description', params.description);
  fd.append('auto_motion_prompt', '1');
  const accepted = await postStudioJobStart('/api/studio/motion/first-frame', { method: 'POST', body: fd });
  if (accepted.job_id) {
    const result = await waitForStudioJobResult(accepted.job_id, { maxWaitMs: 10 * 60 * 1000 });
    return { accepted, result };
  }
  return { accepted, result: null };
}

export async function runMotionVideo(params: {
  modelId: number;
  prompt: string;
  aspect: string;
  resolution: string;
  durationSeconds: number;
  motionVideoFileId?: string;
  firstFrameGenerationId?: number | null;
  autoMotionPrompt?: boolean;
  promptOnlyMode?: boolean;
  frameFile?: LocalFile;
}) {
  const fd = new FormData();
  fd.append('model_id', String(params.modelId));
  fd.append('prompt', params.prompt || '');
  fd.append('output_aspect', params.aspect || '9:16');
  const raw = String(params.resolution || '1080').toLowerCase();
  const videoResolution =
    raw === '1080' || raw === '1080p' || raw === '4k'
      ? '1080p'
      : raw === '720' || raw === '720p'
        ? '720p'
        : raw === '480' || raw === '480p'
          ? '480p'
          : '720p';
  fd.append('video_resolution', videoResolution);
  fd.append('duration_seconds', String(params.durationSeconds));
  if (params.promptOnlyMode) fd.append('prompt_only_mode', '1');
  if (params.motionVideoFileId) fd.append('motion_video_file_id', params.motionVideoFileId);
  if (params.firstFrameGenerationId) {
    fd.append('first_frame_generation_id', String(params.firstFrameGenerationId));
  }
  if (params.autoMotionPrompt) fd.append('auto_motion_prompt', '1');
  if (params.frameFile) appendLocalFile(fd, 'image', params.frameFile);
  const accepted = await postStudioJobStart('/api/studio/motion/render-video', { method: 'POST', body: fd });
  if (accepted.job_id) {
    await waitForStudioJobResult(accepted.job_id, { maxWaitMs: 15 * 60 * 1000 }).catch(() => {});
  }
  return accepted;
}

export async function pollStudioJob(jobId: number) {
  return waitForStudioJobResult(jobId, { maxWaitMs: 15 * 60 * 1000 });
}
