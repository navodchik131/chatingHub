import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useCabinetData } from '../api/CabinetDataProvider';
import {
  clearLocaleUserSet,
  isLocaleUserSet,
  localeFromMe,
  markLocaleUserSet,
  readStoredLocale,
  writeStoredLocale,
} from '../api/locale';
import { pageFromPathname, pathnameFromPage, WORKFLOW_APP_URL } from '../CabinetRoute';
import { dict } from '../data/i18n';
import { BREAKPOINT_MOBILE, BREAKPOINT_NARROW } from '../styles/tokens';

const AppCtx = createContext(null);

const initial = {
  imgMode: 'ref',
  connDetail: null,
  charDetail: null,
  donTab: 'overview',
  partnerTab: 'overview',
  tier: 'standard',
  period: 'month',
  moreOpen: false,
  chatOpen: 0,
  chatFilter: 'all',
  activeFolderId: 'all',
  chatPlatform: 'all',
  chatModelId: 'all',
  folderFormOpen: false,
  folderFormName: '',
  folderFormSelected: [],
  folderPickerConvId: null,
  folderEditId: null,
  folderEditName: '',
  folderEditSelected: [],
  mobileChat: false,
  msgReact: null,
  emojiOpen: false,
  contentMode: 'sfw',
  aiModel: 'nano-banana-pro',
  carouselCount: 4,
  carouselPickId: null,
  chatSearchQuery: '',
  replyToMessageId: null,
  slotSource: {},
  needsRef: 'no',
  hasFirstFrame: 'yes',
  vidMode: 'motion-control',
  vidQuality: '1080',
  vidFormat: '9:16',
  vidTime: '5',
  vidGenerateAudio: true,
  vidSeedanceVariant: 'standard',
  charTab: 'photos',
  lightbox: null,
  showGenError: false,
  ffState: 'idle',
  ffPreviewOpen: false,
  vidLightbox: null,
  photoMenu: null,
  opError: false,
  opEditId: null,
  opRights: { chat: false, studio: false, models: false, keys: false, billing: false },
  mediaStep: null,
  noteFormOpen: false,
  noteTag: 0,
  noteDraft: '',
  replyDraft: '',
  dlgSettingsOpen: false,
  studioPrompt: '',
  motionPrompt: '',
  donForm: { title: '', description: '', minAmount: 0, currency: 'RUB', modelId: '' },
  connForms: {},
  connFlash: null,
  connOauthReason: null,
  opForm: { login: '', password: '', tribute: '15', modelIds: [] },
  lang: readStoredLocale(),
};

function useViewport(forceMobile = false) {
  const [size, setSize] = useState({
    isMobile: forceMobile,
    isNarrow: false,
  });

  useEffect(() => {
    const onResize = () => {
      const w = window.innerWidth;
      const isMobile = forceMobile || w < BREAKPOINT_MOBILE;
      setSize({ isMobile, isNarrow: !isMobile && w < BREAKPOINT_NARROW });
    };
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [forceMobile]);

  return size;
}

export function AppProvider({ children, forceMobile = false }) {
  const navigate = useNavigate();
  const location = useLocation();
  const page = pageFromPathname(location.pathname);
  const cabinet = useCabinetData();
  const [state, setState] = useState(initial);
  const { isMobile, isNarrow } = useViewport(forceMobile);

  const lang = state.lang === 'en' ? 'en' : 'ru';

  const setLang = useCallback((next) => {
    const normalized = next === 'en' ? 'en' : 'ru';
    writeStoredLocale(normalized);
    markLocaleUserSet();
    setState((prev) => (prev.lang === normalized ? prev : { ...prev, lang: normalized }));
    void cabinet.saveUiLocale(normalized)
      .then(() => clearLocaleUserSet())
      .catch(() => {});
  }, [cabinet]);

  useEffect(() => {
    if (!cabinet.me) return;
    const fromMe = localeFromMe(cabinet.me);
    if (!fromMe) return;
    const stored = readStoredLocale();
    if (isLocaleUserSet() && stored !== fromMe) {
      void cabinet.saveUiLocale(stored)
        .then(() => clearLocaleUserSet())
        .catch(() => {});
      return;
    }
    writeStoredLocale(fromMe);
    setState((prev) => (prev.lang === fromMe ? prev : { ...prev, lang: fromMe }));
    if (fromMe === stored) clearLocaleUserSet();
  }, [cabinet.me?.id, cabinet.me?.ui_locale, cabinet]);

  const setS = useCallback((patch) => {
    setState((prev) => {
      let changed = false
      for (const k of Object.keys(patch)) {
        if (prev[k] !== patch[k]) {
          changed = true
          break
        }
      }
      if (!changed) return prev
      return { ...prev, ...patch }
    })
  }, [])

  const go = useCallback((nextPage) => () => {
    if (nextPage === 'workflow') {
      window.location.assign(WORKFLOW_APP_URL)
      return
    }
    navigate(pathnameFromPage(nextPage))
    setS({ connDetail: null, charDetail: null, moreOpen: false })
  }, [navigate, setS])

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const fanvue = params.get('fanvue');
    const instagram = params.get('instagram');
    if (page !== 'connections' || (!fanvue && !instagram)) return;
    if (fanvue) {
      const reason = params.get('reason');
      setS({
        connDetail: 'fanvue',
        connFlash: fanvue === 'connected' ? 'ok' : 'error',
        connOauthReason: fanvue === 'connected' ? null : (reason || null),
      });
      params.delete('fanvue');
    }
    if (instagram) {
      const reason = params.get('reason');
      setS({
        connDetail: 'ig',
        connFlash: instagram === 'connected' ? 'ok' : 'error',
        connOauthReason: instagram === 'connected' ? null : (reason || null),
      });
      params.delete('instagram');
    }
    cabinet.clearBusy();
    void cabinet.refreshAll();
    params.delete('reason');
    const rest = params.toString();
    navigate({ pathname: location.pathname, search: rest ? `?${rest}` : '' }, { replace: true });
  }, [page, location.pathname, location.search, navigate, cabinet, setS]);

  const t = dict[lang];

  const value = useMemo(
    () => ({
      ...state,
      page,
      lang,
      s: { ...state, page, lang },
      setS,
      setLang,
      go,
      t,
      isMobile,
      isNarrow,
      cabinet,
    }),
    [state, page, lang, isMobile, isNarrow, cabinet, t, setS, setLang, go],
  );

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>');
  return ctx;
}

export function useCabinet() {
  return useApp().cabinet;
}
