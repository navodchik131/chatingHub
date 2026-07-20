import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import * as actions from '@/src/api/actions';
import { refreshPendingArchiveImages } from '@/src/api/archivePoll';
import { isArchivePending, archiveThumbUrl } from '@/src/api/media';
import { resolveMediaUrl } from '@/src/api/config';
import { fmtMoney, maskFromOpRights, photoTagsRu } from '@/src/api/helpers';
import {
  mapAdminUser,
  mapArchiveTile,
  mapCharacter,
  mapDialogRow,
  mapDonationRow,
  mapIntegrationCards,
  mapMessage,
  mapOverviewKpis,
  mapTeamMember,
  userDisplayName,
} from '@/src/api/mappers';
import { getToken, setToken } from '@/src/api/token';
import { connectRealtime } from '@/src/api/realtime';
import type {
  AdminStats,
  ConversationFolderOut,
  ConversationOut,
  CreatorDonationLinkOut,
  IntegrationStatusOut,
  HealthOut,
  LocalFile,
  MessageOut,
  StudioGenerationOut,
  StudioModelOut,
  UserMeOut,
  WorkspaceMemberOut,
} from '@/src/api/types';
import { modelIdByName } from '@/src/studio/studioHelpers';
import type { NavigationState } from '@/src/navigation/types';

type GenKey = string;

type AppDataValue = {
  ready: boolean;
  authenticated: boolean;
  busy: boolean;
  error: string | null;
  clearError: () => void;
  me: UserMeOut | null;
  userName: string;
  userEmail: string;
  conversations: ReturnType<typeof mapDialogRow>[];
  rawConversations: ConversationOut[];
  conversationFolders: ConversationFolderOut[];
  messages: ReturnType<typeof mapMessage>[];
  models: ReturnType<typeof mapCharacter>[];
  rawModels: StudioModelOut[];
  modelNames: string[];
  archiveTiles: ReturnType<typeof mapArchiveTile>[];
  rawArchiveImages: StudioGenerationOut[];
  connectionsList: ReturnType<typeof mapIntegrationCards>;
  rawIntegrations: IntegrationStatusOut | null;
  health: HealthOut | null;
  overviewKpis: ReturnType<typeof mapOverviewKpis>;
  billingPlans: { standard: [string, string][]; pro: [string, string][] };
  creditPacks: [string, string][];
  creditHistory: { label: string; amount: string; positive: boolean }[];
  donations: ReturnType<typeof mapDonationRow>[];
  donationAvailableMinor: number;
  payoutWallet: string;
  members: ReturnType<typeof mapTeamMember>[];
  chatterStats: { replies: string; sla: string } | null;
  adminStats: AdminStats | null;
  adminUsers: ReturnType<typeof mapAdminUser>[];
  exifBotStats: { users: string; today: string; processed: string } | null;
  igBotStats: { users: string; today: string; processed: string } | null;
  exifBotUsers: { name: string; u: string; m: string }[];
  igBotUsers: { name: string; u: string; m: string }[];
  photoTags: string[];
  photoTagsExtended: string[];
  uploadFiles: Record<string, LocalFile | undefined>;
  setUploadFile: (key: string, file: LocalFile | undefined) => void;
  motionVideoFileId: string | null;
  setMotionVideoFileId: (id: string | null) => void;
  firstFrameGenId: number | null;
  firstFrameUrl: string;
  generateFirstFrame: (nav: NavigationState, patchFfState: (state: NavigationState['ffState']) => void) => Promise<void>;
  genResults: Record<string, { imageUrl: string }>;
  bootstrap: () => Promise<void>;
  refreshAll: () => Promise<void>;
  refreshArchive: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadThread: (convId: number) => Promise<void>;
  sendThreadMessage: (convId: number, text: string) => Promise<void>;
  loadConversationFolders: () => Promise<void>;
  createConversationFolder: (name: string, conversationIds?: number[]) => Promise<void>;
  renameConversationFolder: (folderId: number, name: string) => Promise<void>;
  deleteConversationFolder: (folderId: number) => Promise<void>;
  setFolderMembers: (folderId: number, conversationIds: number[]) => Promise<void>;
  addConversationToFolder: (folderId: number, convId: number) => Promise<void>;
  startGeneration: (key: GenKey, nav: NavigationState, patchGenStatus: (key: GenKey, status: 'loading' | 'done' | null) => void) => Promise<void>;
  saveCharacterFields: (charId: number, fields: NavigationState['charFields']) => Promise<void>;
  createCharacter: (name: string, photoTagIdx: number, photoFile?: LocalFile) => Promise<number>;
  generateCharacterProfile: (charId: number) => Promise<string>;
  savePayoutWallet: (wallet: string) => Promise<void>;
  requestPayout: () => Promise<void>;
  saveDonationDraft: (fields: NavigationState['donationFields'], charName: string) => Promise<void>;
  addOperator: (login: string, password: string, opRights: Record<string, boolean>) => Promise<void>;
  saveConnection: (platformId: string, token: string, charName: string) => Promise<void>;
  disconnectConnection: (platformId: string) => Promise<void>;
  openBillingCheckout: (product: string) => Promise<string | null>;
  loadAdmin: () => Promise<void>;
  searchAdminUsers: (q: string) => Promise<void>;
  saveAdminSubscription: (userId: number, payload: Record<string, unknown>) => Promise<void>;
  adjustAdminCredits: (userId: number, deltaText: string) => Promise<void>;
  sendBroadcast: (subject: string) => Promise<void>;
};

const AppDataContext = createContext<AppDataValue | null>(null);

const defaultBillingPlans = {
  standard: [
    ['Solo', '990'],
    ['Studio', '1 490'],
    ['Agency', '4 990'],
  ] as [string, string][],
  pro: [
    ['Pro Solo', '2 990'],
    ['Pro Studio', '4 990'],
    ['Pro Agency', '9 990'],
  ] as [string, string][],
};

const defaultCreditPacks: [string, string][] = [
  ['200 кр.', '490 ₽'],
  ['600 кр.', '1 290 ₽'],
  ['1 500 кр.', '2 990 ₽'],
  ['5 000 кр.', '8 990 ₽'],
];

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [me, setMe] = useState<UserMeOut | null>(null);
  const [rawConversations, setRawConversations] = useState<ConversationOut[]>([]);
  const [conversationFolders, setConversationFolders] = useState<ConversationFolderOut[]>([]);
  const [rawMessages, setRawMessages] = useState<MessageOut[]>([]);
  const [rawModels, setRawModels] = useState<StudioModelOut[]>([]);
  const [rawArchiveImages, setRawArchiveImages] = useState<StudioGenerationOut[]>([]);
  const rawArchiveImagesRef = useRef<StudioGenerationOut[]>([]);
  const [rawIntegrations, setRawIntegrations] = useState<IntegrationStatusOut | null>(null);
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [billingPlansApi, setBillingPlansApi] = useState<unknown>(null);
  const [creditHistoryRaw, setCreditHistoryRaw] = useState<unknown[]>([]);
  const [rawDonations, setRawDonations] = useState<CreatorDonationLinkOut[]>([]);
  const [donationAvailableMinor, setDonationAvailableMinor] = useState(0);
  const [payoutWallet, setPayoutWallet] = useState('');
  const [rawMembers, setRawMembers] = useState<WorkspaceMemberOut[]>([]);
  const [chatterStatsRaw, setChatterStatsRaw] = useState<{ replies_per_month?: number; sla_percent?: number } | null>(null);
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [adminUsersRaw, setAdminUsersRaw] = useState<ReturnType<typeof mapAdminUser>[]>([]);
  const [exifBotStats, setExifBotStats] = useState<AppDataValue['exifBotStats']>(null);
  const [igBotStats, setIgBotStats] = useState<AppDataValue['igBotStats']>(null);
  const [exifBotUsers, setExifBotUsers] = useState<AppDataValue['exifBotUsers']>([]);
  const [igBotUsers, setIgBotUsers] = useState<AppDataValue['igBotUsers']>([]);
  const [uploadFiles, setUploadFilesState] = useState<Record<string, LocalFile | undefined>>({});
  const [motionVideoFileId, setMotionVideoFileId] = useState<string | null>(null);
  const [firstFrameGenId, setFirstFrameGenId] = useState<number | null>(null);
  const [firstFrameUrl, setFirstFrameUrl] = useState('');
  const [genResults, setGenResults] = useState<Record<string, { imageUrl: string }>>({});
  const refreshLock = useRef(false);
  const activeThreadConvIdRef = useRef<number | null>(null);

  const mergeInboundMessage = useCallback((prev: MessageOut[], incoming: MessageOut) => {
    const id = Number(incoming?.id);
    if (!id) return prev;
    const idx = prev.findIndex((m) => Number(m.id) === id);
    if (idx >= 0) {
      const next = [...prev];
      next[idx] = { ...next[idx], ...incoming, pending: false };
      return next;
    }
    const withoutPending = prev.filter(
      (m) => !(m.pending && m.direction === 'outbound' && m.text_original === incoming.text_original),
    );
    return [...withoutPending, { ...incoming, pending: false }];
  }, []);

  const patchConversationPreview = useCallback((convId: number, message: MessageOut, bumpUnread = false) => {
    const preview = (message.text_original || message.text_translated || '').trim() || '📷';
    setRawConversations((prev) => {
      const next = prev.map((c) => {
        if (Number(c.id) !== Number(convId)) return c;
        const unread = bumpUnread ? Number(c.unread_count || 0) + 1 : 0;
        return {
          ...c,
          last_message_preview: preview,
          last_message_at: message.created_at || c.last_message_at,
          unread_count: bumpUnread ? unread : 0,
        };
      });
      return next.sort((a, b) => {
        const ta = new Date(a.last_message_at || a.updated_at || 0).getTime();
        const tb = new Date(b.last_message_at || b.updated_at || 0).getTime();
        return tb - ta;
      });
    });
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const setUploadFile = useCallback((key: string, file: LocalFile | undefined) => {
    setUploadFilesState((prev) => ({ ...prev, [key]: file }));
  }, []);

  useEffect(() => {
    rawArchiveImagesRef.current = rawArchiveImages;
  }, [rawArchiveImages]);

  const refreshArchive = useCallback(async () => {
    const archive = await actions.refreshArchiveImages();
    setRawArchiveImages(archive);
  }, []);

  const refreshAll = useCallback(async () => {
    if (refreshLock.current) return;
    refreshLock.current = true;
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setAuthenticated(false);
        setMe(null);
        return;
      }
      const [
        meData,
        convs,
        folders,
        modelsData,
        archiveImg,
        integrationsData,
        healthData,
        donationOv,
        dons,
        plans,
        history,
        payout,
        mems,
        stats,
      ] = await Promise.all([
        actions.fetchMe() as Promise<UserMeOut>,
        actions.fetchConversations() as Promise<ConversationOut[]>,
        actions.fetchConversationFolders() as Promise<ConversationFolderOut[]>,
        actions.fetchModels() as Promise<StudioModelOut[]>,
        actions.refreshArchiveImages(),
        actions.fetchIntegrations() as Promise<IntegrationStatusOut | null>,
        actions.fetchHealth(),
        actions.fetchDonationOverview() as Promise<{ available_minor?: number } | null>,
        actions.fetchDonations() as Promise<CreatorDonationLinkOut[]>,
        actions.fetchBillingPlans(),
        actions.fetchCreditHistory() as Promise<{ items?: unknown[] }>,
        actions.fetchPayoutSettings() as Promise<{ wallet_address?: string } | null>,
        actions.fetchMembers() as Promise<WorkspaceMemberOut[]>,
        actions.fetchChatterStats() as Promise<{ replies_per_month?: number; sla_percent?: number } | null>,
      ]);

      setMe(meData);
      setAuthenticated(true);
      setRawConversations(Array.isArray(convs) ? convs : []);
      setConversationFolders(Array.isArray(folders) ? folders : []);
      setRawModels(Array.isArray(modelsData) ? modelsData : []);
      setRawArchiveImages(Array.isArray(archiveImg) ? archiveImg : []);
      setRawIntegrations(integrationsData);
      setHealth(healthData);
      setDonationAvailableMinor(Number(donationOv?.available_minor || 0));
      setRawDonations(Array.isArray(dons) ? dons : []);
      setBillingPlansApi(plans);
      setCreditHistoryRaw(Array.isArray(history?.items) ? history.items : []);
      setPayoutWallet(String(payout?.wallet_address || ''));
      setRawMembers(Array.isArray(mems) ? mems : []);
      setChatterStatsRaw(stats);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/401|403|сессия/i.test(msg)) {
        await setToken(null);
        setAuthenticated(false);
        setMe(null);
      } else {
        setError(msg);
      }
    } finally {
      refreshLock.current = false;
    }
  }, []);

  const bootstrap = useCallback(async () => {
    setReady(false);
    await refreshAll();
    setReady(true);
  }, [refreshAll]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (!ready || !authenticated) return;
    if (!rawArchiveImages.some(isArchivePending)) return;
    const timer = setInterval(() => {
      void refreshPendingArchiveImages(rawArchiveImagesRef.current).then(({ items, changed }) => {
        if (changed) setRawArchiveImages(items);
      });
    }, 12_000);
    return () => clearInterval(timer);
  }, [ready, authenticated, rawArchiveImages]);

  const login = useCallback(async (email: string, password: string) => {
    setBusy(true);
    setError(null);
    try {
      const data = await actions.login(email, password);
      await setToken(data.access_token);
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [refreshAll]);

  const register = useCallback(async (email: string, password: string) => {
    setBusy(true);
    setError(null);
    try {
      const data = await actions.register(email, password);
      await setToken(data.access_token);
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [refreshAll]);

  const logout = useCallback(async () => {
    await setToken(null);
    setAuthenticated(false);
    setMe(null);
    setRawConversations([]);
    setRawMessages([]);
  }, []);

  const loadConversationFolders = useCallback(async () => {
    try {
      const rows = (await actions.fetchConversationFolders()) as ConversationFolderOut[];
      setConversationFolders(Array.isArray(rows) ? rows : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const loadThread = useCallback(async (convId: number) => {
    activeThreadConvIdRef.current = convId;
    try {
      const msgs = (await actions.fetchMessages(convId)) as MessageOut[];
      setRawMessages(Array.isArray(msgs) ? msgs : []);
      await actions.markConversationRead(convId);
      setRawConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const sendThreadMessage = useCallback(async (convId: number, text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const tempId = -Date.now();
    const optimistic: MessageOut = {
      id: tempId,
      direction: 'outbound',
      text_original: trimmed,
      created_at: new Date().toISOString(),
      pending: true,
    };
    setRawMessages((prev) => [...prev, optimistic]);

    try {
      const sent = (await actions.sendReply(convId, trimmed)) as MessageOut;
      if (sent?.id) {
        setRawMessages((prev) => mergeInboundMessage(prev, sent));
        patchConversationPreview(convId, sent);
      } else {
        await loadThread(convId);
      }
    } catch (e) {
      setRawMessages((prev) => prev.filter((m) => m.id !== tempId));
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    }
  }, [loadThread, mergeInboundMessage, patchConversationPreview]);

  const createConversationFolder = useCallback(async (name: string, conversationIds: number[] = []) => {
    setBusy(true);
    setError(null);
    try {
      await actions.createConversationFolder(name, conversationIds);
      await loadConversationFolders();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [loadConversationFolders]);

  const renameConversationFolder = useCallback(async (folderId: number, name: string) => {
    setBusy(true);
    setError(null);
    try {
      await actions.patchConversationFolder(folderId, { name });
      await loadConversationFolders();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [loadConversationFolders]);

  const deleteConversationFolder = useCallback(async (folderId: number) => {
    setBusy(true);
    setError(null);
    try {
      await actions.deleteConversationFolder(folderId);
      await loadConversationFolders();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [loadConversationFolders]);

  const setFolderMembers = useCallback(async (folderId: number, conversationIds: number[]) => {
    setBusy(true);
    setError(null);
    try {
      await actions.patchConversationFolder(folderId, { conversation_ids: conversationIds });
      await loadConversationFolders();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [loadConversationFolders]);

  const addConversationToFolder = useCallback(async (folderId: number, convId: number) => {
    setBusy(true);
    setError(null);
    try {
      await actions.addConversationToFolder(folderId, convId);
      await loadConversationFolders();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  }, [loadConversationFolders]);

  useEffect(() => {
    if (!ready || !authenticated) return;
    let conn: Awaited<ReturnType<typeof connectRealtime>> | null = null;
    void connectRealtime((msg) => {
      const convId = Number(msg?.conversation_id);
      const activeId = Number(activeThreadConvIdRef.current);
      if (
        msg?.type === 'new_message' ||
        msg?.type === 'message_updated' ||
        msg?.type === 'message_created'
      ) {
        const payload = msg.message as MessageOut | undefined;
        if (payload?.id && convId) {
          if (activeId && convId === activeId) {
            setRawMessages((prev) => mergeInboundMessage(prev, payload));
            patchConversationPreview(convId, payload);
          } else {
            patchConversationPreview(convId, payload, true);
          }
        }
      }
      if (
        msg?.type === 'studio_generation_updated' ||
        msg?.type === 'studio_job' ||
        msg?.type === 'studio_generation' ||
        msg?.type === 'credits_updated'
      ) {
        void refreshArchive();
        void actions.fetchMe().then((m) => setMe(m as UserMeOut));
      }
    }).then((c) => {
      conn = c;
    });
    return () => {
      conn?.close();
    };
  }, [ready, authenticated, mergeInboundMessage, patchConversationPreview, refreshArchive]);

  const startGeneration = useCallback(
    async (
      key: GenKey,
      nav: NavigationState,
      patchGenStatus: (key: GenKey, status: 'loading' | 'done' | null) => void,
    ) => {
      patchGenStatus(key, 'loading');
      setError(null);
      try {
        const modelId = modelIdByName(rawModels, nav.imgChar || nav.vidChar);
        let generationId: number | null = null;
        let directImageUrl = '';

        if (key === 'video') {
          if (!modelId) throw new Error('Выберите персонажа');
          const motionControl = (nav.vidMode || 'motion-control') === 'motion-control';
          if (motionControl && !motionVideoFileId) throw new Error('Загрузите референс-видео');
          const accepted = await actions.runMotionVideo({
            modelId,
            prompt: motionControl ? '' : (nav.imgPrompt || 'Cinematic motion'),
            aspect: nav.vidFormat,
            resolution: nav.vidQuality,
            durationSeconds: nav.vidDuration,
            motionVideoFileId: motionVideoFileId || undefined,
            firstFrameGenerationId: firstFrameGenId,
            autoMotionPrompt: motionControl && Boolean(motionVideoFileId),
            frameFile: uploadFiles['motion-frame'],
          });
          generationId = accepted.generation_id ?? null;
        } else if (key.startsWith('img:')) {
          const modeId = key.slice(4);
          const accepted = await actions.runImageGeneration({
            modeId,
            navState: nav as unknown as Record<string, unknown>,
            uploadFiles,
            slotArchivePicks: {},
            selectedModelId: modelId,
            archiveImages: rawArchiveImages,
            workflowDemoLimited: me?.workflow_demo_limited,
          });
          generationId = accepted.generation_id ?? null;
          if (accepted.job_id) {
            const jobResult = (await actions.pollStudioJob(accepted.job_id)) as {
              generation_id?: number;
              image_url?: string;
            };
            generationId = jobResult.generation_id ?? generationId;
            if (jobResult.image_url) directImageUrl = resolveMediaUrl(jobResult.image_url);
          }
        }

        const archive = await actions.refreshArchiveImages();
        setRawArchiveImages(archive);

        const hit =
          generationId != null
            ? archive.find((g) => Number(g.id) === Number(generationId))
            : archive.find((g) => !isArchivePending(g) && Boolean((g.image_url || '').trim()));
        const imageUrl = archiveThumbUrl(hit) || directImageUrl;
        if (imageUrl) {
          setGenResults((prev) => ({ ...prev, [key]: { imageUrl } }));
        }

        patchGenStatus(key, 'done');
        if (me) {
          const freshMe = (await actions.fetchMe()) as UserMeOut;
          setMe(freshMe);
        }
      } catch (e) {
        patchGenStatus(key, null);
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [rawModels, rawArchiveImages, uploadFiles, motionVideoFileId, firstFrameGenId, me],
  );

  const generateFirstFrame = useCallback(
    async (nav: NavigationState, patchFfState: (state: NavigationState['ffState']) => void) => {
      const modelId = modelIdByName(rawModels, nav.vidChar);
      if (!modelId) throw new Error('Выберите персонажа');
      if (!uploadFiles['motion-video'] && !motionVideoFileId) {
        throw new Error('Загрузите референс-видео');
      }
      patchFfState('loading');
      setError(null);
      try {
        const { result } = await actions.runMotionFirstFrame({
          modelId,
          aspect: nav.vidFormat,
          nsfw: nav.contentMode === 'nsfw',
          videoFile: uploadFiles['motion-video'],
          frameFile: uploadFiles['motion-frame'],
          existingGenerationId: firstFrameGenId,
          description: '',
        });
        if (result?.generation_id) setFirstFrameGenId(Number(result.generation_id));
        const url = resolveMediaUrl(
          String(result?.generated_image_url || result?.image_url || ''),
        );
        if (url) setFirstFrameUrl(url);
        else if (result?.generation_id) {
          const archive = await actions.refreshArchiveImages();
          setRawArchiveImages(archive);
          const hit = archive.find((g) => Number(g.id) === Number(result.generation_id));
          const thumb = archiveThumbUrl(hit);
          if (thumb) setFirstFrameUrl(thumb);
        } else {
          await refreshArchive();
        }
        patchFfState('done');
        if (me) {
          const freshMe = (await actions.fetchMe()) as UserMeOut;
          setMe(freshMe);
        }
      } catch (e) {
        patchFfState('idle');
        setError(e instanceof Error ? e.message : String(e));
        throw e;
      }
    },
    [rawModels, uploadFiles, motionVideoFileId, firstFrameGenId, me, refreshArchive],
  );

  const saveCharacterFields = useCallback(async (charId: number, fields: NavigationState['charFields']) => {
    await actions.patchStudioModel(charId, {
      profile_text: fields.appearance,
      companion_persona: JSON.stringify({
        ageCity: fields.ageCity,
        character: fields.character,
        chatStyle: fields.chatStyle,
        camera: fields.camera,
        geo: fields.geo,
      }),
    });
    await refreshAll();
  }, [refreshAll]);

  const createCharacter = useCallback(async (name: string, photoTagIdx: number, photoFile?: LocalFile) => {
    const created = (await actions.createStudioModel(name)) as StudioModelOut;
    if (photoFile && created.id) {
      const kinds = ['face', 'turnaround', 'body', 'genitals', 'other'];
      await actions.uploadStudioModelImage(created.id, photoFile, kinds[photoTagIdx] || 'face');
    }
    await refreshAll();
    return created.id;
  }, [refreshAll]);

  const generateCharacterProfile = useCallback(async (charId: number) => {
    const model = rawModels.find((m) => m.id === charId);
    if (!model) throw new Error('Персонаж не найден');
    const data = (await actions.generateStudioModelProfile(model)) as { profile_text?: string };
    if (data.profile_text) {
      await actions.patchStudioModel(charId, { profile_text: data.profile_text });
    }
    await refreshAll();
    return data.profile_text || '';
  }, [rawModels, refreshAll]);

  const savePayoutWallet = useCallback(async (wallet: string) => {
    await actions.savePayoutSettings(wallet);
    setPayoutWallet(wallet);
  }, []);

  const requestPayout = useCallback(async () => {
    await actions.requestDonationPayout('RUB');
    await refreshAll();
  }, [refreshAll]);

  const saveDonationDraft = useCallback(async (fields: NavigationState['donationFields'], charName: string) => {
    const modelId = modelIdByName(rawModels, charName);
    const min = parseInt(fields.min.replace(/\D/g, ''), 10) || 10000;
    await actions.saveDonationLink({
      title: fields.title,
      description: fields.desc,
      min_amount_minor: min,
      studio_model_id: modelId,
      currency: 'RUB',
    });
    await refreshAll();
  }, [rawModels, refreshAll]);

  const addOperator = useCallback(async (login: string, password: string, opRights: Record<string, boolean>) => {
    await actions.addWorkspaceMember({
      member_login: login,
      password,
      permissions_mask: maskFromOpRights(opRights),
    });
    await refreshAll();
  }, [refreshAll]);

  const saveConnection = useCallback(async (platformId: string, token: string, charName: string) => {
    const modelId = modelIdByName(rawModels, charName);
    if (platformId === 'tg') await actions.saveTelegramBot(token, modelId ?? undefined);
    if (platformId === 'tr') await actions.saveTributeKey(token, modelId ?? undefined);
    await refreshAll();
  }, [rawModels, refreshAll]);

  const disconnectConnection = useCallback(async (platformId: string) => {
    if (platformId === 'tg' && rawIntegrations?.telegram_connections?.[0]?.id) {
      await actions.deleteTelegramConnection(rawIntegrations.telegram_connections[0].id);
    }
    await refreshAll();
  }, [rawIntegrations, refreshAll]);

  const openBillingCheckout = useCallback(async (product: string) => {
    try {
      if (me?.tribute_billing_available) {
        const data = (await actions.payTributeCheckout(product)) as { checkout_url?: string };
        return data.checkout_url || null;
      }
      if (me?.online_payment_available) {
        const data = (await actions.payYookassa(product)) as { confirmation_url?: string };
        return data.confirmation_url || null;
      }
      await actions.payYookassa(product);
      return null;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, [me]);

  const loadAdmin = useCallback(async () => {
    const [stats, exifStats, igStats, exifUsers, igUsers] = await Promise.all([
      actions.fetchAdminStats(),
      actions.fetchExifBotStats() as Promise<{ users_total?: number; processed_total?: number } | null>,
      actions.fetchIgBotStats() as Promise<{ users_total?: number; processed_total?: number } | null>,
      actions.fetchExifBotUsers() as Promise<{ username?: string; telegram_username?: string; messages_count?: number; display_name?: string }[]>,
      actions.fetchIgBotUsers() as Promise<{ username?: string; messages_count?: number; display_name?: string }[]>,
    ]);
    setAdminStats(stats as AdminStats | null);
    setExifBotStats({
      users: String(exifStats?.users_total ?? 0),
      today: '0',
      processed: String(exifStats?.processed_total ?? 0),
    });
    setIgBotStats({
      users: String(igStats?.users_total ?? 0),
      today: '0',
      processed: String(igStats?.processed_total ?? 0),
    });
    setExifBotUsers(
      (exifUsers || []).map((u) => ({
        name: u.display_name || u.username || '—',
        u: u.telegram_username || u.username || '—',
        m: `${u.messages_count ?? 0} msg`,
      })),
    );
    setIgBotUsers(
      (igUsers || []).map((u) => ({
        name: u.display_name || u.username || '—',
        u: u.username || '—',
        m: `${u.messages_count ?? 0} msg`,
      })),
    );
  }, []);

  const searchAdminUsers = useCallback(async (q: string) => {
    const rows = (await actions.fetchAdminUsers(q)) as { id: number; email: string; role?: string; billing_plan?: string; credits_balance?: number; subscription_status?: string }[];
    setAdminUsersRaw(rows.map(mapAdminUser));
  }, []);

  const saveAdminSubscription = useCallback(async (userId: number, payload: Record<string, unknown>) => {
    await actions.patchAdminUserSubscription(userId, payload);
    await searchAdminUsers('');
  }, [searchAdminUsers]);

  const adjustAdminCredits = useCallback(async (userId: number, deltaText: string) => {
    const delta = parseInt(deltaText.replace(/[^-\d]/g, ''), 10);
    if (!Number.isFinite(delta) || delta === 0) throw new Error('Укажите изменение кредитов');
    await actions.adjustAdminUserCredits(userId, delta);
    await searchAdminUsers('');
  }, [searchAdminUsers]);

  const sendBroadcast = useCallback(async (subject: string) => {
    await actions.sendAdminCampaign(subject);
  }, []);

  const { userName, userEmail } = userDisplayName(me);
  const conversations = rawConversations.map(mapDialogRow);
  const messages = rawMessages.map(mapMessage);
  const models = rawModels.map(mapCharacter);
  const modelNames = rawModels.map((m) => m.name);
  const archiveTiles = rawArchiveImages.map((g, i) => mapArchiveTile(g, i, rawModels));
  const connectionsList = mapIntegrationCards(rawIntegrations);
  const overviewKpis = mapOverviewKpis(me, rawConversations, donationAvailableMinor);
  const donations = rawDonations.map(mapDonationRow);
  const members = rawMembers.map(mapTeamMember);
  const chatterStats = chatterStatsRaw
    ? { replies: String(chatterStatsRaw.replies_per_month ?? '—'), sla: `${chatterStatsRaw.sla_percent ?? '—'}%` }
    : null;

  const creditHistory = (creditHistoryRaw as { description?: string; amount?: number }[]).slice(0, 10).map((row) => ({
    label: row.description || 'Операция',
    amount: `${row.amount && row.amount > 0 ? '+' : ''}${row.amount ?? 0}`,
    positive: (row.amount ?? 0) > 0,
  }));

  const value = useMemo<AppDataValue>(
    () => ({
      ready,
      authenticated,
      busy,
      error,
      clearError,
      me,
      userName,
      userEmail,
      conversations,
      rawConversations,
      conversationFolders,
      messages,
      models,
      rawModels,
      modelNames: modelNames.length ? modelNames : ['Mia', 'Ruby'],
      archiveTiles,
      rawArchiveImages,
      connectionsList,
      rawIntegrations,
      health,
      overviewKpis,
      billingPlans: defaultBillingPlans,
      creditPacks: defaultCreditPacks,
      creditHistory,
      donations,
      donationAvailableMinor,
      payoutWallet,
      members,
      chatterStats,
      adminStats,
      adminUsers: adminUsersRaw,
      exifBotStats,
      igBotStats,
      exifBotUsers,
      igBotUsers,
      photoTags: photoTagsRu().slice(0, 3),
      photoTagsExtended: photoTagsRu(),
      uploadFiles,
      setUploadFile,
      motionVideoFileId,
      setMotionVideoFileId,
      firstFrameGenId,
      firstFrameUrl,
      generateFirstFrame,
      genResults,
      bootstrap,
      refreshAll,
      refreshArchive,
      login,
      register,
      logout,
      loadThread,
      sendThreadMessage,
      loadConversationFolders,
      createConversationFolder,
      renameConversationFolder,
      deleteConversationFolder,
      setFolderMembers,
      addConversationToFolder,
      startGeneration,
      saveCharacterFields,
      createCharacter,
      generateCharacterProfile,
      savePayoutWallet,
      requestPayout,
      saveDonationDraft,
      addOperator,
      saveConnection,
      disconnectConnection,
      openBillingCheckout,
      loadAdmin,
      searchAdminUsers,
      saveAdminSubscription,
      adjustAdminCredits,
      sendBroadcast,
    }),
    [
      ready,
      authenticated,
      busy,
      error,
      clearError,
      me,
      userName,
      userEmail,
      conversations,
      rawConversations,
      conversationFolders,
      messages,
      models,
      rawModels,
      modelNames,
      archiveTiles,
      rawArchiveImages,
      connectionsList,
      rawIntegrations,
      health,
      overviewKpis,
      creditHistory,
      donations,
      donationAvailableMinor,
      payoutWallet,
      members,
      chatterStats,
      adminStats,
      adminUsersRaw,
      exifBotStats,
      igBotStats,
      exifBotUsers,
      igBotUsers,
      uploadFiles,
      setUploadFile,
      motionVideoFileId,
      firstFrameGenId,
      firstFrameUrl,
      generateFirstFrame,
      genResults,
      bootstrap,
      refreshAll,
      refreshArchive,
      login,
      register,
      logout,
      loadThread,
      sendThreadMessage,
      loadConversationFolders,
      createConversationFolder,
      renameConversationFolder,
      deleteConversationFolder,
      setFolderMembers,
      addConversationToFolder,
      startGeneration,
      saveCharacterFields,
      createCharacter,
      generateCharacterProfile,
      savePayoutWallet,
      requestPayout,
      saveDonationDraft,
      addOperator,
      saveConnection,
      disconnectConnection,
      openBillingCheckout,
      loadAdmin,
      searchAdminUsers,
      saveAdminSubscription,
      adjustAdminCredits,
      sendBroadcast,
    ],
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error('useAppData must be used within AppDataProvider');
  return ctx;
}

export const AppProvider = AppDataProvider;

/** @deprecated use useAppData */
export function useApp() {
  const data = useAppData();
  return { userName: data.userName, userEmail: data.userEmail, me: data.me };
}
