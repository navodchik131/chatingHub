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
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { showUserError } from '@/src/utils/userNotice';
import { AppState } from 'react-native';
import * as actions from '@/src/api/actions';
import { validateImageGeneration } from '@/src/api/actions';
import { refreshPendingArchiveImages } from '@/src/api/archivePoll';
import { isArchivePending, archiveThumbUrl, preferStableMediaUrl } from '@/src/api/media';
import { resolveMediaUrl } from '@/src/api/config';
import {
  extractStudioJobGenerationId,
  extractStudioJobImageUrl,
  extractStudioJobVideoUrl,
} from '@/src/studio/studioHelpers';
import { charFieldsFromModel, fmtMoney, maskFromOpRights, photoTagsRu, resolveDonationBalances } from '@/src/api/helpers';
import {
  mapAdminUser,
  mapArchiveTile,
  mapCharacter,
  mapDialogRow,
  mapDonationEventRow,
  mapDonationRow,
  mapIntegrationCards,
  mapMessage,
  mapOverviewKpis,
  mapTeamKpi,
  mapTeamMember,
  userDisplayName,
} from '@/src/api/mappers';
import { getToken, setToken } from '@/src/api/token';
import { connectRealtime } from '@/src/api/realtime';
import type {
  AdminStats,
  ConversationFolderOut,
  ConversationOut,
  CreatorDonationEventOut,
  CreatorDonationLinkOut,
  CreatorDonationOverviewOut,
  ChatterStatsSummaryOut,
  IntegrationStatusOut,
  HealthOut,
  LocalFile,
  MessageOut,
  StudioGenerationOut,
  StudioModelOut,
  SupportTicketListItemOut,
  SupportTicketOut,
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
  totalUnread: number;
  rawConversations: ConversationOut[];
  conversationFolders: ConversationFolderOut[];
  messages: ReturnType<typeof mapMessage>[];
  models: ReturnType<typeof mapCharacter>[];
  rawModels: StudioModelOut[];
  modelNames: string[];
  archiveTiles: ReturnType<typeof mapArchiveTile>[];
  rawArchiveImages: StudioGenerationOut[];
  archiveSkip: number;
  archiveHasMore: boolean;
  loadMoreArchive: () => Promise<void>;
  archiveVideoTiles: ReturnType<typeof mapArchiveTile>[];
  rawArchiveVideos: StudioGenerationOut[];
  videoArchiveSkip: number;
  videoArchiveHasMore: boolean;
  refreshArchiveVideos: () => Promise<void>;
  loadMoreVideoArchive: () => Promise<void>;
  supportTickets: SupportTicketListItemOut[];
  refreshSupportTickets: () => Promise<void>;
  createSupportTicket: (payload: { type: string; subject: string; message: string }) => Promise<SupportTicketOut>;
  fetchSupportTicket: (ticketId: number) => Promise<SupportTicketOut>;
  replySupportTicket: (ticketId: number, message: string) => Promise<void>;
  saveProfileEmail: (email: string) => Promise<void>;
  changeUserPassword: (current: string, next: string) => Promise<void>;
  uploadExifReference: (charId: number, role: 'selfie' | 'main', file: LocalFile) => Promise<void>;
  connectionsList: ReturnType<typeof mapIntegrationCards>;
  rawIntegrations: IntegrationStatusOut | null;
  health: HealthOut | null;
  overviewKpis: ReturnType<typeof mapOverviewKpis>;
  billingPlans: { standard: [string, string][]; pro: [string, string][] };
  creditPacks: [string, string][];
  creditHistory: { label: string; amount: string; positive: boolean }[];
  donations: ReturnType<typeof mapDonationRow>[];
  donationEvents: ReturnType<typeof mapDonationEventRow>[];
  donationBalances: { total: number; available: number; held: number; paid: number; currency: string };
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
  slotArchivePicks: Record<string, number>;
  setSlotArchivePick: (slotKey: string, generationId: number | null) => void;
  slotSource: Record<string, 'upload' | 'archive'>;
  setSlotSource: (slotKey: string, source: 'upload' | 'archive') => void;
  motionVideoFileId: string | null;
  setMotionVideoFileId: (id: string | null) => void;
  firstFrameGenId: number | null;
  setFirstFrameGenId: (id: number | null) => void;
  firstFrameUrl: string;
  setFirstFrameUrl: (url: string) => void;
  generateFirstFrame: (nav: NavigationState, patchFfState: (state: NavigationState['ffState']) => void) => Promise<void>;
  genResults: Record<string, { imageUrl?: string; videoUrl?: string }>;
  bootstrap: () => Promise<void>;
  refreshAll: () => Promise<void>;
  refreshArchive: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  loginWithTelegram: () => Promise<void>;
  logout: () => Promise<void>;
  loadThread: (convId: number) => Promise<void>;
  clearActiveThread: () => void;
  refreshConversations: () => Promise<void>;
  sendThreadMessage: (convId: number, text: string) => Promise<void>;
  sendThreadImage: (convId: number, text: string, file: LocalFile) => Promise<void>;
  loadConversationFolders: () => Promise<void>;
  createConversationFolder: (name: string, conversationIds?: number[]) => Promise<void>;
  renameConversationFolder: (folderId: number, name: string) => Promise<void>;
  deleteConversationFolder: (folderId: number) => Promise<void>;
  setFolderMembers: (folderId: number, conversationIds: number[]) => Promise<void>;
  addConversationToFolder: (folderId: number, convId: number) => Promise<void>;
  startGeneration: (key: GenKey, nav: NavigationState, patchGenStatus: (key: GenKey, status: 'loading' | 'done' | null) => void) => Promise<void>;
  saveCharacterFields: (charId: number, fields: NavigationState['charFields']) => Promise<void>;
  createCharacter: (name: string, photoTagIdx: number, photoFile?: LocalFile) => Promise<number>;
  renameCharacter: (charId: number, name: string) => Promise<void>;
  deleteCharacter: (charId: number) => Promise<void>;
  deleteCharacterPhoto: (charId: number, imageId: number) => Promise<void>;
  generateCharacterProfile: (charId: number) => Promise<string>;
  savePayoutWallet: (wallet: string) => Promise<void>;
  requestPayout: () => Promise<void>;
  saveDonationDraft: (fields: NavigationState['donationFields'], charName: string) => Promise<void>;
  addOperator: (login: string, password: string, opRights: Record<string, boolean>) => Promise<void>;
  updateOperator: (memberId: number, login: string, password: string, opRights: Record<string, boolean>) => Promise<void>;
  deleteOperator: (memberId: number) => Promise<void>;
  saveConnection: (platformId: string, token: string, charName: string) => Promise<boolean>;
  disconnectConnection: (platformId: string, connectionId: number) => Promise<void>;
  openBillingCheckout: (product: string) => Promise<string | null>;
  loadAdmin: () => Promise<void>;
  searchAdminUsers: (q: string) => Promise<void>;
  saveAdminSubscription: (userId: number, payload: Record<string, unknown>) => Promise<void>;
  adjustAdminCredits: (userId: number, deltaText: string) => Promise<void>;
  resetAdminPassword: (userId: number, password: string) => Promise<void>;
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

function reuseModelImageUrls(
  prevModels: StudioModelOut[],
  nextModels: StudioModelOut[],
): StudioModelOut[] {
  if (!prevModels.length || !nextModels.length) return nextModels;
  const urlByImageId = new Map<number, string>();
  for (const model of prevModels) {
    for (const image of model.images || []) {
      if (image?.id && image?.url) urlByImageId.set(image.id, image.url);
    }
  }
  return nextModels.map((model) => ({
    ...model,
    images: (model.images || []).map((image) => ({
      ...image,
      url: preferStableMediaUrl(urlByImageId.get(image.id), image.url) || image.url,
    })),
  }));
}

export function AppDataProvider({ children }: { children: ReactNode }) {
  const { t, locale } = useAppSettings();
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
  const [archiveSkip, setArchiveSkip] = useState(0);
  const [archiveHasMore, setArchiveHasMore] = useState(true);
  const [rawArchiveVideos, setRawArchiveVideos] = useState<StudioGenerationOut[]>([]);
  const [videoArchiveSkip, setVideoArchiveSkip] = useState(0);
  const [videoArchiveHasMore, setVideoArchiveHasMore] = useState(true);
  const [supportTickets, setSupportTickets] = useState<SupportTicketListItemOut[]>([]);
  const rawArchiveImagesRef = useRef<StudioGenerationOut[]>([]);
  const [rawIntegrations, setRawIntegrations] = useState<IntegrationStatusOut | null>(null);
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [billingPlansApi, setBillingPlansApi] = useState<unknown>(null);
  const [creditHistoryRaw, setCreditHistoryRaw] = useState<unknown[]>([]);
  const [rawDonations, setRawDonations] = useState<CreatorDonationLinkOut[]>([]);
  const [rawDonationEvents, setRawDonationEvents] = useState<CreatorDonationEventOut[]>([]);
  const [donationOverviewRaw, setDonationOverviewRaw] = useState<CreatorDonationOverviewOut | null>(null);
  const [donationAvailableMinor, setDonationAvailableMinor] = useState(0);
  const [payoutWallet, setPayoutWallet] = useState('');
  const [rawMembers, setRawMembers] = useState<WorkspaceMemberOut[]>([]);
  const [chatterStatsRaw, setChatterStatsRaw] = useState<ChatterStatsSummaryOut | null>(null);
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [adminUsersRaw, setAdminUsersRaw] = useState<ReturnType<typeof mapAdminUser>[]>([]);
  const [exifBotStats, setExifBotStats] = useState<AppDataValue['exifBotStats']>(null);
  const [igBotStats, setIgBotStats] = useState<AppDataValue['igBotStats']>(null);
  const [exifBotUsers, setExifBotUsers] = useState<AppDataValue['exifBotUsers']>([]);
  const [igBotUsers, setIgBotUsers] = useState<AppDataValue['igBotUsers']>([]);
  const [uploadFiles, setUploadFilesState] = useState<Record<string, LocalFile | undefined>>({});
  const [slotArchivePicks, setSlotArchivePicksState] = useState<Record<string, number>>({});
  const [slotSource, setSlotSourceState] = useState<Record<string, 'upload' | 'archive'>>({});
  const [motionVideoFileId, setMotionVideoFileId] = useState<string | null>(null);
  const [firstFrameGenId, setFirstFrameGenIdState] = useState<number | null>(null);
  const [firstFrameUrl, setFirstFrameUrlState] = useState('');
  const [genResults, setGenResults] = useState<Record<string, { imageUrl?: string; videoUrl?: string }>>({});
  const refreshLock = useRef(false);
  const activeThreadConvIdRef = useRef<number | null>(null);
  const rawConversationsRef = useRef<ConversationOut[]>([]);

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

  const patchConversationPreview = useCallback((
    convId: number,
    message: MessageOut,
    opts: { bumpUnread?: boolean; clearUnread?: boolean } = {},
  ) => {
    const { bumpUnread = false, clearUnread = false } = opts;
    const preview = (message.text_original || message.text_translated || '').trim() || '📷';
    setRawConversations((prev) => {
      const found = prev.some((c) => Number(c.id) === Number(convId));
      if (!found) return prev;
      const next = prev.map((c) => {
        if (Number(c.id) !== Number(convId)) return c;
        const unread = bumpUnread
          ? Number(c.unread_count || 0) + 1
          : clearUnread
            ? 0
            : Number(c.unread_count || 0);
        return {
          ...c,
          last_message_preview: preview,
          last_message_at: message.created_at || c.last_message_at,
          unread_count: unread,
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

  const reportError = useCallback((e: unknown, options?: { alert?: boolean }) => {
    const msg = e instanceof Error ? e.message : String(e);
    if (!msg.trim()) return;
    setError(msg);
    if (options?.alert !== false) {
      showUserError(msg, t.errorTitle);
    }
  }, [t.errorTitle]);

  const setUploadFile = useCallback((key: string, file: LocalFile | undefined) => {
    setUploadFilesState((prev) => ({ ...prev, [key]: file }));
  }, []);

  const setSlotArchivePick = useCallback((slotKey: string, generationId: number | null) => {
    setSlotArchivePicksState((prev) => {
      const next = { ...prev };
      if (generationId == null) delete next[slotKey];
      else next[slotKey] = generationId;
      return next;
    });
  }, []);

  const setSlotSource = useCallback((slotKey: string, source: 'upload' | 'archive') => {
    setSlotSourceState((prev) => ({ ...prev, [slotKey]: source }));
  }, []);

  const setFirstFrameGenId = useCallback((id: number | null) => {
    setFirstFrameGenIdState(id);
  }, []);

  const setFirstFrameUrl = useCallback((url: string) => {
    setFirstFrameUrlState(url);
  }, []);

  useEffect(() => {
    rawArchiveImagesRef.current = rawArchiveImages;
  }, [rawArchiveImages]);

  useEffect(() => {
    rawConversationsRef.current = rawConversations;
  }, [rawConversations]);

  const refreshArchive = useCallback(async () => {
    const archive = await actions.refreshArchiveImages();
    setRawArchiveImages(archive);
    const pageCount = archive.filter((g) => g.status !== 'processing' && g.status !== 'archiving').length;
    setArchiveSkip(Math.max(archive.length, pageCount));
    setArchiveHasMore(archive.length >= 40);
  }, []);

  const loadMoreArchive = useCallback(async () => {
    const items = await actions.loadMoreArchiveImages(archiveSkip);
    if (!items.length) {
      setArchiveHasMore(false);
      return;
    }
    setRawArchiveImages((prev) => {
      const seen = new Set(prev.map((g) => g.id));
      return [...prev, ...items.filter((g) => !seen.has(g.id))];
    });
    setArchiveSkip((prev) => prev + items.length);
    setArchiveHasMore(items.length >= 40);
  }, [archiveSkip]);

  const refreshArchiveVideos = useCallback(async () => {
    const archive = await actions.refreshArchiveVideos();
    setRawArchiveVideos(archive);
    setVideoArchiveSkip(archive.length);
    setVideoArchiveHasMore(archive.length >= 40);
  }, []);

  const loadMoreVideoArchive = useCallback(async () => {
    const items = await actions.loadMoreArchiveVideos(videoArchiveSkip);
    if (!items.length) {
      setVideoArchiveHasMore(false);
      return;
    }
    setRawArchiveVideos((prev) => {
      const seen = new Set(prev.map((g) => g.id));
      return [...prev, ...items.filter((g) => !seen.has(g.id))];
    });
    setVideoArchiveSkip((prev) => prev + items.length);
    setVideoArchiveHasMore(items.length >= 40);
  }, [videoArchiveSkip]);

  const refreshSupportTickets = useCallback(async () => {
    const rows = await actions.fetchSupportTickets();
    setSupportTickets(Array.isArray(rows) ? rows : []);
  }, []);

  const createSupportTicket = useCallback(async (payload: { type: string; subject: string; message: string }) => {
    const row = await actions.createSupportTicket(payload);
    await refreshSupportTickets();
    return row;
  }, [refreshSupportTickets]);

  const fetchSupportTicket = useCallback(async (ticketId: number) => {
    return actions.fetchSupportTicket(ticketId);
  }, []);

  const replySupportTicket = useCallback(async (ticketId: number, message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return;
    setError(null);
    try {
      await actions.replySupportTicket(ticketId, trimmed);
      await refreshSupportTickets();
    } catch (e) {
      reportError(e);
      throw e;
    }
  }, [refreshSupportTickets]);

  const refreshConversations = useCallback(async () => {
    try {
      const convs = (await actions.fetchConversations()) as ConversationOut[];
      if (Array.isArray(convs)) setRawConversations(convs);
    } catch {
      /* ignore polling errors */
    }
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
        donationEvents,
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
        actions.fetchDonationOverview() as Promise<CreatorDonationOverviewOut | null>,
        actions.fetchDonations() as Promise<CreatorDonationLinkOut[]>,
        actions.fetchDonationEvents() as Promise<CreatorDonationEventOut[]>,
        actions.fetchBillingPlans(),
        actions.fetchCreditHistory() as Promise<{ items?: unknown[] }>,
        actions.fetchPayoutSettings() as Promise<{ wallet_address?: string } | null>,
        actions.fetchMembers() as Promise<WorkspaceMemberOut[]>,
        actions.fetchChatterStats() as Promise<ChatterStatsSummaryOut | null>,
      ]);

      setMe(meData);
      setAuthenticated(true);
      setRawConversations(Array.isArray(convs) ? convs : []);
      setConversationFolders(Array.isArray(folders) ? folders : []);
      setRawModels((prev) => reuseModelImageUrls(prev, Array.isArray(modelsData) ? modelsData : []));
      setRawArchiveImages(Array.isArray(archiveImg) ? archiveImg : []);
      setRawIntegrations(integrationsData);
      setHealth(healthData);
      setDonationOverviewRaw(donationOv);
      const balances = resolveDonationBalances(donationOv, Array.isArray(donationEvents) ? donationEvents : []);
      setDonationAvailableMinor(balances.available);
      setRawDonations(Array.isArray(dons) ? dons : []);
      setRawDonationEvents(Array.isArray(donationEvents) ? donationEvents : []);
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

  const saveProfileEmail = useCallback(async (email: string) => {
    await actions.patchProfileEmail(email);
    await refreshAll();
  }, [refreshAll]);

  const changeUserPassword = useCallback(async (current: string, next: string) => {
    await actions.changePassword(current, next);
  }, []);

  const uploadExifReference = useCallback(async (charId: number, role: 'selfie' | 'main', file: LocalFile) => {
    await actions.uploadPhoneExifReference(charId, role, file);
    await refreshAll();
  }, [refreshAll]);

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
      reportError(e);
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
      reportError(e);
      throw e;
    } finally {
      setBusy(false);
    }
  }, [refreshAll]);

  const loginWithTelegram = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const { signInWithTelegram } = await import('@/src/auth/telegramLoginMobile');
      const token = await signInWithTelegram();
      await setToken(token);
      await refreshAll();
    } catch (e) {
      reportError(e);
      throw e;
    } finally {
      setBusy(false);
    }
  }, [refreshAll]);

  const logout = useCallback(async () => {
    try {
      const { unregisterMobilePush } = await import('@/src/push/notifications');
      await unregisterMobilePush();
    } catch {
      /* ignore */
    }
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
      reportError(e);
    }
  }, []);

  const loadThread = useCallback(async (convId: number) => {
    activeThreadConvIdRef.current = convId;
    setRawMessages([]);
    try {
      const msgs = (await actions.fetchMessages(convId)) as MessageOut[];
      if (activeThreadConvIdRef.current !== convId) return;
      setRawMessages(Array.isArray(msgs) ? msgs : []);
      await actions.markConversationRead(convId);
      setRawConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c)),
      );
    } catch (e) {
      if (activeThreadConvIdRef.current !== convId) return;
      reportError(e);
    }
  }, []);

  const clearActiveThread = useCallback(() => {
    activeThreadConvIdRef.current = null;
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
        patchConversationPreview(convId, sent, { clearUnread: false });
      } else {
        await loadThread(convId);
      }
    } catch (e) {
      setRawMessages((prev) => prev.filter((m) => m.id !== tempId));
      reportError(e);
      throw e;
    }
  }, [loadThread, mergeInboundMessage, patchConversationPreview]);

  const sendThreadImage = useCallback(async (convId: number, text: string, file: LocalFile) => {
    const tempId = -Date.now();
    const optimistic: MessageOut = {
      id: tempId,
      direction: 'outbound',
      text_original: text.trim() || '📷',
      created_at: new Date().toISOString(),
      pending: true,
    };
    setRawMessages((prev) => [...prev, optimistic]);
    try {
      const sent = (await actions.sendReplyWithImage(convId, text, file)) as MessageOut;
      if (sent?.id) {
        setRawMessages((prev) => mergeInboundMessage(prev, sent));
        patchConversationPreview(convId, sent, { clearUnread: false });
      } else {
        await loadThread(convId);
      }
    } catch (e) {
      setRawMessages((prev) => prev.filter((m) => m.id !== tempId));
      reportError(e);
      throw e;
    }
  }, [loadThread, mergeInboundMessage, patchConversationPreview]);

  const createConversationFolder = useCallback(async (name: string, conversationIds?: number[]) => {
    setBusy(true);
    setError(null);
    try {
      await actions.createConversationFolder(name, conversationIds);
      await loadConversationFolders();
    } catch (e) {
      reportError(e);
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
      reportError(e);
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
      reportError(e);
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
      reportError(e);
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
      reportError(e);
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

      if (msg?.type === 'conversation_updated') {
        void refreshConversations();
        return;
      }

      if (
        msg?.type === 'new_message' ||
        msg?.type === 'message_updated' ||
        msg?.type === 'message_created'
      ) {
        const payload = msg.message as MessageOut | undefined;
        if (payload?.id && convId) {
          const isInbound = payload.direction === 'inbound';
          const inOpenThread = activeId > 0 && convId === activeId;
          if (inOpenThread) {
            setRawMessages((prev) => mergeInboundMessage(prev, payload));
            if (isInbound) {
              patchConversationPreview(convId, payload, { clearUnread: true });
            } else {
              patchConversationPreview(convId, payload);
            }
          } else if (isInbound) {
            patchConversationPreview(convId, payload, { bumpUnread: true });
          } else {
            patchConversationPreview(convId, payload);
          }
          void refreshConversations();
        } else if (convId) {
          void refreshConversations();
        }
        return;
      }

      if (
        msg?.type === 'studio_generation_updated' ||
        msg?.type === 'studio_job' ||
        msg?.type === 'studio_generation' ||
        msg?.type === 'credits_updated'
      ) {
        void refreshArchive();
        void refreshArchiveVideos();
        void actions.fetchMe().then((m) => setMe(m as UserMeOut));
      }
    }).then((c) => {
      conn = c;
    });
    return () => {
      conn?.close();
    };
  }, [ready, authenticated, mergeInboundMessage, patchConversationPreview, refreshArchive, refreshArchiveVideos, refreshConversations]);

  useEffect(() => {
    if (!ready || !authenticated) return;
    const timer = setInterval(() => {
      void refreshConversations();
    }, 8000);
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') void refreshConversations();
    });
    return () => {
      clearInterval(timer);
      sub.remove();
    };
  }, [ready, authenticated, refreshConversations]);

  const startGeneration = useCallback(
    async (
      key: GenKey,
      nav: NavigationState,
      patchGenStatus: (key: GenKey, status: 'loading' | 'done' | null) => void,
    ) => {
      setError(null);

      const modelId = modelIdByName(rawModels, nav.imgChar || nav.vidChar);

      if (key === 'video') {
        const promptOnly = (nav.vidMode || 'motion-control') === 'prompt';
        const motionControl = !promptOnly && (nav.vidMode || 'motion-control') === 'motion-control';
        if (!modelId) {
          reportError(new Error(t.errSelectCharacter));
          return;
        }
        if (promptOnly) {
          if (!uploadFiles['motion-frame'] && !firstFrameGenId) {
            reportError(new Error(t.errUploadFirstFrame));
            return;
          }
          if (!String(nav.imgPrompt || '').trim()) {
            reportError(new Error(t.errPromptOnlyVideo));
            return;
          }
        }
        if (motionControl) {
          if (!motionVideoFileId) {
            reportError(new Error(t.errUploadRefVideo));
            return;
          }
          if (nav.vidHasFirstFrame && !firstFrameGenId && !uploadFiles['motion-frame']) {
            reportError(new Error(t.errUploadFirstFrame));
            return;
          }
          if (!nav.vidHasFirstFrame && !firstFrameGenId) {
            reportError(new Error(t.errUploadFirstFrame));
            return;
          }
        }
      } else if (key.startsWith('img:')) {
        const modeId = key.slice(4);
        const validationMsg = validateImageGeneration({
          modeId,
          navState: nav as unknown as Record<string, unknown>,
          uploadFiles,
          slotArchivePicks,
          slotSource,
          selectedModelId: modelId,
          labels: {
            errSelectCharacter: t.errSelectCharacter,
            errEnterPrompt: t.errEnterPrompt,
            errUploadReference: t.errUploadReference,
            errUploadSceneRef: t.errUploadSceneRef,
            errUploadOutfitCloth: t.errUploadOutfitCloth,
            errUploadLocationRef: t.errUploadLocationRef,
            errUploadEditFrame: t.errUploadEditFrame,
            errUploadEditDetailRef: t.errUploadEditDetailRef,
          },
        });
        if (validationMsg) {
          reportError(new Error(validationMsg));
          return;
        }
      }

      patchGenStatus(key, 'loading');

      const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

      const resolveFromArchive = async (
        generationId: number | null,
        directImageUrl: string,
        directVideoUrl: string,
      ) => {
        let archive = await actions.refreshArchiveImages();
        setRawArchiveImages(archive);

        const pickHit = (items: typeof archive) => {
          if (generationId != null) {
            return items.find((g) => Number(g.id) === Number(generationId));
          }
          return undefined;
        };

        let hit = pickHit(archive);
        let imageUrl = directImageUrl;
        let videoUrl = directVideoUrl;

        if (!imageUrl && !videoUrl && hit) {
          imageUrl = archiveThumbUrl(hit) || '';
          videoUrl = hit.video_url ? resolveMediaUrl(hit.video_url) : '';
        }

        if ((!imageUrl && !videoUrl) && generationId != null) {
          for (let attempt = 0; attempt < 8; attempt += 1) {
            if (attempt > 0) await sleep(2500);
            archive = await actions.refreshArchiveImages();
            setRawArchiveImages(archive);
            hit = pickHit(archive);
            if (!hit || isArchivePending(hit)) continue;
            imageUrl = archiveThumbUrl(hit) || '';
            videoUrl = hit.video_url ? resolveMediaUrl(hit.video_url) : '';
            if (imageUrl || videoUrl) break;
          }
        }

        if (!videoUrl && generationId != null) {
          let videoArchive = await actions.refreshArchiveVideos();
          setRawArchiveVideos(videoArchive);
          let vHit = videoArchive.find((g) => Number(g.id) === Number(generationId));
          if (vHit && !isArchivePending(vHit)) {
            videoUrl = vHit.video_url ? resolveMediaUrl(vHit.video_url) : videoUrl;
            if (!imageUrl) imageUrl = archiveThumbUrl(vHit) || '';
          } else {
            for (let attempt = 0; attempt < 8 && !videoUrl; attempt += 1) {
              if (attempt > 0) await sleep(2500);
              videoArchive = await actions.refreshArchiveVideos();
              setRawArchiveVideos(videoArchive);
              vHit = videoArchive.find((g) => Number(g.id) === Number(generationId));
              if (!vHit || isArchivePending(vHit)) continue;
              videoUrl = vHit.video_url ? resolveMediaUrl(vHit.video_url) : '';
              if (!imageUrl) imageUrl = archiveThumbUrl(vHit) || '';
            }
          }
        }

        return { imageUrl, videoUrl };
      };

      try {
        let generationId: number | null = null;
        let directImageUrl = '';
        let directVideoUrl = '';

        if (key === 'video') {
          if (!modelId) throw new Error(t.errSelectCharacter);
          const promptOnly = (nav.vidMode || 'motion-control') === 'prompt';
          const motionControl = !promptOnly && (nav.vidMode || 'motion-control') === 'motion-control';
          let ffGenId: number | null = motionControl ? firstFrameGenId : null;
          if (motionControl && !ffGenId && uploadFiles['motion-frame']) {
            const { result } = await actions.runMotionFirstFrame({
              modelId,
              aspect: nav.vidFormat,
              nsfw: nav.contentMode === 'nsfw',
              frameFile: uploadFiles['motion-frame'],
              autoMotionPrompt: false,
              useStillAsFinal: true,
            });
            const gid = result?.generation_id;
            ffGenId = gid != null ? Number(gid) : null;
            if (!ffGenId) throw new Error(t.errUploadFirstFrame);
          }
          const accepted = await actions.runMotionVideo({
            modelId,
            prompt: promptOnly ? (nav.imgPrompt || '') : (motionControl ? '' : (nav.imgPrompt || 'Cinematic motion')),
            aspect: nav.vidFormat,
            resolution: nav.vidQuality,
            durationSeconds: nav.vidDuration,
            motionVideoFileId: motionControl ? (motionVideoFileId || undefined) : undefined,
            firstFrameGenerationId: motionControl ? ffGenId : null,
            autoMotionPrompt: motionControl && Boolean(motionVideoFileId),
            promptOnlyMode: promptOnly,
            generateAudio: nav.vidGenerateAudio !== false,
          });
          generationId = accepted.generation_id ?? null;
          if (accepted.job_id) {
            const jobResult = (await actions.pollStudioJob(accepted.job_id)) as Record<string, unknown>;
            generationId = extractStudioJobGenerationId(jobResult) ?? generationId;
            directVideoUrl = resolveMediaUrl(extractStudioJobVideoUrl(jobResult));
            if (!directVideoUrl) {
              directImageUrl = resolveMediaUrl(extractStudioJobImageUrl(jobResult));
            }
          }
        } else if (key.startsWith('img:')) {
          const modeId = key.slice(4);
          const accepted = await actions.runImageGeneration({
            modeId,
            navState: nav as unknown as Record<string, unknown>,
            uploadFiles,
            slotArchivePicks,
            selectedModelId: modelId,
            archiveImages: rawArchiveImages,
            workflowDemoLimited: me?.workflow_demo_limited,
          });
          generationId = accepted.generation_id ?? null;
          if (accepted.job_id) {
            const jobResult = (await actions.pollStudioJob(accepted.job_id)) as Record<string, unknown>;
            generationId = extractStudioJobGenerationId(jobResult) ?? generationId;
            directImageUrl = resolveMediaUrl(extractStudioJobImageUrl(jobResult));
          }
        }

        const { imageUrl, videoUrl } = await resolveFromArchive(
          generationId,
          directImageUrl,
          directVideoUrl,
        );

        if (!imageUrl && !videoUrl) {
          throw new Error(generationId ? t.errGenPending : t.errGenFailed);
        }

        setGenResults((prev) => ({
          ...prev,
          [key]: { imageUrl: imageUrl || undefined, videoUrl: videoUrl || undefined },
        }));

        patchGenStatus(key, 'done');
        if (me) {
          const freshMe = (await actions.fetchMe()) as UserMeOut;
          setMe(freshMe);
        }
      } catch (e) {
        patchGenStatus(key, null);
        reportError(e);
      }
    },
    [rawModels, rawArchiveImages, uploadFiles, slotArchivePicks, slotSource, motionVideoFileId, firstFrameGenId, me, t, reportError],
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
        if (result?.generation_id) setFirstFrameGenIdState(Number(result.generation_id));
        const url = resolveMediaUrl(
          String(result?.generated_image_url || result?.image_url || ''),
        );
        if (url) setFirstFrameUrlState(url);
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
        reportError(e);
        throw e;
      }
    },
    [rawModels, uploadFiles, motionVideoFileId, firstFrameGenId, me, refreshArchive],
  );

  const saveCharacterFields = useCallback(async (charId: number, fields: NavigationState['charFields']) => {
    const [agePart, ...cityParts] = (fields.ageCity || '').split(',').map((s) => s.trim());
    const cityPart = cityParts.join(', ').trim();
    const geoParts = (fields.geo || '').split(',').map((s) => s.trim());
    const lat = geoParts[0] ? parseFloat(geoParts[0]) : undefined;
    const lon = geoParts[1] ? parseFloat(geoParts[1]) : undefined;
    await actions.patchStudioModel(charId, {
      profile_text: fields.appearance,
      companion_persona: {
        age: agePart || undefined,
        city: cityPart || undefined,
        personality: fields.character || undefined,
        speaking_style: fields.chatStyle || undefined,
      },
      ...(lat != null && !Number.isNaN(lat) ? { export_lat: lat } : {}),
      ...(lon != null && !Number.isNaN(lon) ? { export_lon: lon } : {}),
      ...(fields.camera ? { camera_preset_id: fields.camera } : {}),
    });
    await refreshAll();
  }, [refreshAll]);

  const createCharacter = useCallback(async (name: string, photoTagIdx: number, photoFile?: LocalFile) => {
    const trimmed = name.trim();
    if (!trimmed) {
      const err = new Error('Укажите имя персонажа');
      reportError(err);
      throw err;
    }
    const created = (await actions.createStudioModel(trimmed)) as StudioModelOut;
    if (photoFile && created.id) {
      const kinds = ['face', 'turnaround', 'body', 'genitals', 'other'];
      await actions.uploadStudioModelImage(created.id, photoFile, kinds[photoTagIdx] || 'face');
    }
    await refreshAll();
    return created.id;
  }, [refreshAll, reportError]);

  const renameCharacter = useCallback(async (charId: number, name: string) => {
    const trimmed = name.trim();
    if (!trimmed) throw new Error('Укажите имя персонажа');
    await actions.patchStudioModel(charId, { name: trimmed });
    await refreshAll();
  }, [refreshAll]);

  const deleteCharacter = useCallback(async (charId: number) => {
    await actions.deleteStudioModel(charId);
    await refreshAll();
  }, [refreshAll]);

  const deleteCharacterPhoto = useCallback(async (charId: number, imageId: number) => {
    await actions.deleteStudioModelImage(charId, imageId);
    await refreshAll();
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
    const rub = parseFloat((fields.min || '').replace(',', '.'));
    const min = Number.isFinite(rub) && rub > 0 ? Math.round(rub * 100) : 10000;
    await actions.saveDonationLink({
      title: fields.title,
      description: fields.desc,
      min_amount_minor: min,
      studio_model_id: modelId,
      currency: 'RUB',
      submit: true,
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

  const updateOperator = useCallback(async (memberId: number, login: string, password: string, opRights: Record<string, boolean>) => {
    const payload: Record<string, unknown> = {
      member_login: login,
      permissions_mask: maskFromOpRights(opRights),
    };
    if (password.trim()) payload.password = password;
    await actions.updateWorkspaceMember(memberId, payload);
    await refreshAll();
  }, [refreshAll]);

  const deleteOperator = useCallback(async (memberId: number) => {
    await actions.deleteWorkspaceMember(memberId);
    await refreshAll();
  }, [refreshAll]);

  const saveConnection = useCallback(async (platformId: string, token: string, charName: string) => {
    const modelId = modelIdByName(rawModels, charName);
    setError(null);
    try {
      let status: IntegrationStatusOut | null = null;
      if (platformId === 'tg') {
        const trimmed = token.trim();
        if (!trimmed) {
          reportError(new Error('Укажите токен Telegram-бота'));
          return false;
        }
        status = await actions.saveTelegramBot(trimmed, modelId ?? undefined);
      } else if (platformId === 'tr') {
        const trimmed = token.trim();
        if (!trimmed) {
          reportError(new Error('Введите API-ключ Tribute'));
          return false;
        }
        status = await actions.saveTributeKey(trimmed, modelId ?? undefined);
      } else if (platformId === 'ws') {
        const trimmed = token.trim();
        if (!trimmed) {
          reportError(new Error('Введите API-ключ WaveSpeed'));
          return false;
        }
        status = await actions.saveWavespeedKey(trimmed);
      } else if (platformId === 'fv') {
        const { connectFanvue } = await import('@/src/auth/fanvueOAuthMobile');
        const result = await connectFanvue(modelId ?? undefined);
        if (result === 'connected') {
          await refreshAll();
          return true;
        }
        if (result === 'error') reportError(new Error('Не удалось подключить Fanvue'));
        return false;
      } else {
        reportError(new Error('Сохранение недоступно для этой интеграции'));
        return false;
      }
      if (status) setRawIntegrations(status);
      await refreshAll();
      return true;
    } catch (e) {
      reportError(e);
      return false;
    }
  }, [rawModels, refreshAll]);

  const disconnectConnection = useCallback(async (platformId: string, connectionId: number) => {
    if (platformId === 'tg') await actions.deleteTelegramConnection(connectionId);
    else if (platformId === 'fv') await actions.deleteFanvueConnection(connectionId);
    else if (platformId === 'tr') await actions.deleteTributeConnection(connectionId);
    await refreshAll();
  }, [refreshAll]);

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
      reportError(e);
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

  const resetAdminPassword = useCallback(async (userId: number, password: string) => {
    const trimmed = password.trim();
    if (trimmed.length < 8) {
      setError('Пароль должен быть не короче 8 символов');
      showUserError('Пароль должен быть не короче 8 символов', t.errorTitle);
      return;
    }
    setError(null);
    try {
      await actions.resetAdminUserPassword(userId, trimmed);
    } catch (e) {
      reportError(e);
      throw e;
    }
  }, []);

  const sendBroadcast = useCallback(async (subject: string) => {
    await actions.sendAdminCampaign(subject);
  }, []);

  const { userName, userEmail } = userDisplayName(me);
  const conversations = rawConversations.map(mapDialogRow);
  const totalUnread = rawConversations.reduce((sum, c) => sum + (c.unread_count || 0), 0);
  const messages = rawMessages.map(mapMessage);
  const models = rawModels.map((m, i) => mapCharacter(m, i, locale));
  const modelNames = rawModels.map((m) => m.name);
  const archiveTiles = rawArchiveImages.map((g, i) => mapArchiveTile(g, i, rawModels));
  const archiveVideoTiles = rawArchiveVideos.map((g, i) => mapArchiveTile(g, i, rawModels));
  const connectionsList = mapIntegrationCards(rawIntegrations);
  const donationBalances = resolveDonationBalances(donationOverviewRaw, rawDonationEvents);
  const overviewKpis = mapOverviewKpis(me, rawConversations, donationBalances.available, locale);
  const donations = rawDonations.map(mapDonationRow);
  const donationEvents = rawDonationEvents.map(mapDonationEventRow);
  const members = rawMembers.map((m, i) => mapTeamMember(m, i, rawModels, chatterStatsRaw));
  const chatterStats = mapTeamKpi(chatterStatsRaw);

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
      totalUnread,
      rawConversations,
      conversationFolders,
      messages,
      models,
      rawModels,
      modelNames: modelNames.length ? modelNames : ['Mia', 'Ruby'],
      archiveTiles,
      rawArchiveImages,
      archiveSkip,
      archiveHasMore,
      loadMoreArchive,
      archiveVideoTiles,
      rawArchiveVideos,
      videoArchiveSkip,
      videoArchiveHasMore,
      refreshArchiveVideos,
      loadMoreVideoArchive,
      supportTickets,
      refreshSupportTickets,
      createSupportTicket,
      fetchSupportTicket,
      replySupportTicket,
      saveProfileEmail,
      changeUserPassword,
      uploadExifReference,
      connectionsList,
      rawIntegrations,
      health,
      overviewKpis,
      billingPlans: defaultBillingPlans,
      creditPacks: defaultCreditPacks,
      creditHistory,
      donations,
      donationEvents,
      donationBalances,
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
      slotArchivePicks,
      setSlotArchivePick,
      slotSource,
      setSlotSource,
      motionVideoFileId,
      setMotionVideoFileId,
      firstFrameGenId,
      setFirstFrameGenId,
      firstFrameUrl,
      setFirstFrameUrl,
      generateFirstFrame,
      genResults,
      bootstrap,
      refreshAll,
      refreshArchive,
      login,
      register,
      loginWithTelegram,
      logout,
      loadThread,
      clearActiveThread,
      refreshConversations,
      sendThreadMessage,
      sendThreadImage,
      loadConversationFolders,
      createConversationFolder,
      renameConversationFolder,
      deleteConversationFolder,
      setFolderMembers,
      addConversationToFolder,
      startGeneration,
      saveCharacterFields,
      createCharacter,
      renameCharacter,
      deleteCharacter,
      deleteCharacterPhoto,
      generateCharacterProfile,
      savePayoutWallet,
      requestPayout,
      saveDonationDraft,
      addOperator,
      updateOperator,
      deleteOperator,
      saveConnection,
      disconnectConnection,
      openBillingCheckout,
      loadAdmin,
      searchAdminUsers,
      saveAdminSubscription,
      adjustAdminCredits,
      resetAdminPassword,
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
      totalUnread,
      rawConversations,
      conversationFolders,
      messages,
      models,
      rawModels,
      modelNames,
      archiveTiles,
      rawArchiveImages,
      archiveSkip,
      archiveHasMore,
      loadMoreArchive,
      archiveVideoTiles,
      rawArchiveVideos,
      videoArchiveSkip,
      videoArchiveHasMore,
      refreshArchiveVideos,
      loadMoreVideoArchive,
      supportTickets,
      refreshSupportTickets,
      createSupportTicket,
      fetchSupportTicket,
      replySupportTicket,
      saveProfileEmail,
      changeUserPassword,
      uploadExifReference,
      connectionsList,
      rawIntegrations,
      health,
      overviewKpis,
      creditHistory,
      donations,
      donationEvents,
      donationBalances,
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
      loginWithTelegram,
      logout,
      loadThread,
      clearActiveThread,
      refreshConversations,
      sendThreadMessage,
      sendThreadImage,
      loadConversationFolders,
      createConversationFolder,
      renameConversationFolder,
      deleteConversationFolder,
      setFolderMembers,
      addConversationToFolder,
      startGeneration,
      saveCharacterFields,
      createCharacter,
      renameCharacter,
      deleteCharacter,
      deleteCharacterPhoto,
      generateCharacterProfile,
      savePayoutWallet,
      requestPayout,
      saveDonationDraft,
      addOperator,
      updateOperator,
      deleteOperator,
      saveConnection,
      disconnectConnection,
      openBillingCheckout,
      loadAdmin,
      searchAdminUsers,
      saveAdminSubscription,
      adjustAdminCredits,
      resetAdminPassword,
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
