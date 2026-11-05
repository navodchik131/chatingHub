import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { dict } from '../data/i18n';
import { BREAKPOINT_MOBILE, BREAKPOINT_NARROW } from '../styles/tokens';

const AppCtx = createContext(null);

// Mirrors the prototype's `state = { ... }` block exactly.
const initial = {
  page: 'overview',
  lang: 'ru',
  imgMode: 'ref',
  connDetail: null,
  charDetail: null,
  donTab: 'overview',
  tier: 'standard',
  period: 'month',
  moreOpen: false,
  chatOpen: 0,
  chatFilter: 'all',
  chatPlatform: 'all',
  mobileChat: false,
  msgReact: null,
  emojiOpen: false,
  reactions: {},
  contentMode: 'sfw',
  aiModel: 'nano',
  carouselCount: 4,
  slotSource: {},
  hasFirstFrame: 'yes',
  vidQuality: '1080',
  vidFormat: '9:16',
  vidTime: '5',
  charTab: 'photos',
  lightbox: null,
  showGenError: false,
  ffState: 'idle',
  photoMenu: null,
  opRights: { chat: true, studio: true, models: true, keys: false, billing: false },
  opError: false,
  mediaStep: null,
  noteFormOpen: false,
  noteTag: 0,
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
  const [state, setState] = useState(initial);
  const { isMobile, isNarrow } = useViewport(forceMobile);

  // setS(patch) — same shape as the prototype's setState helper.
  const setS = (patch) => setState((prev) => ({ ...prev, ...patch }));

  // go(page) — resets detail views, matching prototype nav behaviour.
  const go = (page) => () =>
    setS({ page, connDetail: null, charDetail: null, moreOpen: false });

  const t = dict[state.lang];

  const value = useMemo(
    () => ({ ...state, s: state, setS, go, t, lang: state.lang, isMobile, isNarrow }),
    [state, isMobile, isNarrow],
  );

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>');
  return ctx;
}
