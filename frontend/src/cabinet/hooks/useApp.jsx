import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useCabinetData } from '../api/CabinetDataProvider';
import { pageFromPathname, pathnameFromPage, WORKFLOW_APP_URL } from '../CabinetRoute';
import { dict } from '../data/i18n';
import { BREAKPOINT_MOBILE, BREAKPOINT_NARROW } from '../styles/tokens';

const AppCtx = createContext(null);

const initial = {
  imgMode: 'ref',
  connDetail: null,
  charDetail: null,
  donTab: 'overview',
  tier: 'standard',
  period: 'month',
  moreOpen: false,
  chatOpen: 0,
  chatFilter: 'all',
  activeFolderId: 'all',
  chatPlatform: 'all',
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
  studioPrompt: '',
  motionPrompt: '',
  donForm: { title: '', description: '', minRub: 0, modelId: '' },
  connForms: {},
  connFlash: null,
  opForm: { login: '', password: '', tribute: '15', modelIds: [] },
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

  const lang = state.lang || (typeof localStorage !== 'undefined' && localStorage.getItem('i18nextLng')?.startsWith('en') ? 'en' : 'ru');

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
      setS({ connDetail: 'fanvue', connFlash: fanvue === 'connected' ? 'ok' : 'error' });
      params.delete('fanvue');
    }
    if (instagram) {
      setS({ connDetail: 'ig', connFlash: instagram === 'connected' ? 'ok' : 'error' });
      params.delete('instagram');
    }
    params.delete('reason');
    const rest = params.toString();
    navigate({ pathname: location.pathname, search: rest ? `?${rest}` : '' }, { replace: true });
  }, [page, location.pathname, location.search, navigate]);

  const t = dict[lang];

  const value = useMemo(
    () => ({
      ...state,
      page,
      lang,
      s: { ...state, page, lang },
      setS,
      go,
      t,
      isMobile,
      isNarrow,
      cabinet,
    }),
    [state, page, lang, isMobile, isNarrow, cabinet, t, setS, go],
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
