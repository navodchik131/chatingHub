// Icons transferred from the prototype's `I(paths, fill)` factory.
// Same viewBox / stroke settings: 24x24, stroke-width 1.8, round caps/joins.

const Svg = ({ children, fill = false }) => (
  <svg
    viewBox="0 0 24 24"
    width="100%"
    height="100%"
    fill={fill ? 'currentColor' : 'none'}
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    {children}
  </svg>
);

export const IcoGrid = () => (
  <Svg>
    <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" />
  </Svg>
);

export const IcoChat = () => (
  <Svg>
    <path d="M21 12c0 4.4-4 8-9 8-1.2 0-2.4-.2-3.4-.6L3 21l1.7-4.1C3.6 15.5 3 13.8 3 12c0-4.4 4-8 9-8s9 3.6 9 8z" />
  </Svg>
);

export const IcoImage = () => (
  <Svg>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <circle cx="9" cy="10" r="1.8" />
    <path d="M3.5 18l5-5 3.5 3.5L16 12l4.5 5" />
  </Svg>
);

export const IcoFilm = () => (
  <Svg>
    <rect x="3" y="5" width="18" height="14" rx="3" />
    <path d="M10 9.5l5 2.5-5 2.5z" />
  </Svg>
);

export const IcoStar = () => (
  <Svg>
    <circle cx="12" cy="8.5" r="3.6" />
    <path d="M5 20c.8-3.4 3.6-5.4 7-5.4s6.2 2 7 5.4" />
  </Svg>
);

export const IcoHeart = () => (
  <Svg>
    <path d="M12 20.5S4 15.3 4 9.8C4 7 6.2 5 8.7 5c1.4 0 2.6.7 3.3 1.7C12.7 5.7 13.9 5 15.3 5 17.8 5 20 7 20 9.8c0 5.5-8 10.7-8 10.7z" />
  </Svg>
);

export const IcoCard = () => (
  <Svg>
    <rect x="3" y="5.5" width="18" height="13" rx="3" />
    <path d="M3 10h18" />
    <path d="M7 15h4" />
  </Svg>
);

export const IcoPlug = () => (
  <Svg>
    <path d="M9 7V3.5M15 7V3.5" />
    <path d="M7 7h10v4a5 5 0 0 1-10 0z" />
    <path d="M12 16v4.5" />
  </Svg>
);

export const IcoTeam = () => (
  <Svg>
    <circle cx="9" cy="9" r="3.2" />
    <path d="M3.5 19.5c.6-2.9 2.9-4.6 5.5-4.6s4.9 1.7 5.5 4.6" />
    <circle cx="17" cy="10" r="2.5" />
    <path d="M16 15.2c2.3.2 4 1.7 4.5 4.3" />
  </Svg>
);

export const IcoBolt = () => (
  <Svg>
    <path d="M13 2.5L5 13.5h6l-1 8 9-11.5h-6z" />
  </Svg>
);

export const IcoSpark = () => (
  <Svg>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M18.5 15.5l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z" />
  </Svg>
);

export const IcoUpload = () => (
  <Svg>
    <path d="M12 16V5" />
    <path d="M7.5 9L12 4.5 16.5 9" />
    <path d="M4 16.5v1.5A2.5 2.5 0 0 0 6.5 20.5h11a2.5 2.5 0 0 0 2.5-2.5v-1.5" />
  </Svg>
);

export const IcoCopy = () => (
  <Svg>
    <rect x="8.5" y="8.5" width="12" height="12" rx="2.5" />
    <path d="M15.5 8.5V6a2.5 2.5 0 0 0-2.5-2.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5" />
  </Svg>
);

export const IcoPlay = () => (
  <Svg fill>
    <path d="M8 5.5l11 6.5-11 6.5z" />
  </Svg>
);

export const IcoFace = () => (
  <Svg>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M8.5 10.2v1.2M15.5 10.2v1.2" />
    <path d="M8.5 15c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8" />
  </Svg>
);

export const IcoShirt = () => (
  <Svg>
    <path d="M8 4L4 7.5l2 3 2-1.2V20h8v-10.7l2 1.2 2-3L16 4c-1 1.2-2.4 1.8-4 1.8S9 5.2 8 4z" />
  </Svg>
);

export const IcoPin = () => (
  <Svg>
    <path d="M12 21s-6.5-5.6-6.5-10.5A6.5 6.5 0 0 1 12 4a6.5 6.5 0 0 1 6.5 6.5C18.5 15.4 12 21 12 21z" />
    <circle cx="12" cy="10.5" r="2.3" />
  </Svg>
);

export const IcoText = () => (
  <Svg>
    <path d="M4 6h16M4 12h16M4 18h9" />
  </Svg>
);

export const IcoGrid2 = () => (
  <Svg>
    <rect x="3" y="3" width="7" height="18" rx="2" />
    <rect x="14" y="3" width="7" height="18" rx="2" />
  </Svg>
);

export const IcoFlow = () => (
  <Svg>
    <rect x="3" y="4" width="6" height="5" rx="1.5" />
    <rect x="15" y="4" width="6" height="5" rx="1.5" />
    <rect x="9" y="15" width="6" height="5" rx="1.5" />
    <path d="M6 9v2.5a2 2 0 0 0 2 2h1M18 9v2.5a2 2 0 0 1-2 2h-1" />
  </Svg>
);

export const IcoDownload = () => (
  <Svg>
    <path d="M12 4v11" />
    <path d="M7.5 10.5L12 15l4.5-4.5" />
    <path d="M4 18.5h16" />
  </Svg>
);

export const IcoZoom = () => (
  <Svg>
    <circle cx="11" cy="11" r="7" />
    <path d="M16 16l4.5 4.5M8.5 11h5M11 8.5v5" />
  </Svg>
);

export const IcoClip = () => (
  <Svg>
    <path d="M20 11.5l-8 8a5 5 0 0 1-7-7l8.5-8.5a3 3 0 0 1 4.3 4.3L9 12.7a1.2 1.2 0 0 1-1.7-1.7L15 3.5" />
  </Svg>
);

export const IcoSendArrow = () => (
  <Svg>
    <path d="M5 12l15-7-6 16-3-6z" />
    <path d="M11 15l3-6" />
  </Svg>
);

export const IcoLayers = () => (
  <Svg>
    <path d="M12 3.5L21 8.5l-9 5-9-5z" />
    <path d="M4 13l8 4.5 8-4.5" />
    <path d="M4 17l8 4.5 8-4.5" opacity=".45" />
  </Svg>
);

export const IcoTg = () => (
  <Svg>
    <path
      d="M21 4.5L3.5 11.2c-.9.35-.85 1.6.1 1.85l4.4 1.2 1.7 5.2c.3.85 1.4 1 1.9.3l2.4-3.1 4.5 3.3c.75.55 1.8.15 2-.75L23 6c.25-1.1-.85-2-1.9-1.5z"
      transform="scale(.92) translate(1 .5)"
    />
  </Svg>
);

export const IcoWave = () => (
  <Svg>
    <path d="M3 12c2-4.5 4-4.5 6 0s4 4.5 6 0 4-4.5 6 0" />
  </Svg>
);

export const IcoBell = () => (
  <Svg>
    <path d="M12 4a5.5 5.5 0 0 0-5.5 5.5c0 4-1.5 5.5-2.5 6.5h16c-1-1-2.5-2.5-2.5-6.5A5.5 5.5 0 0 0 12 4z" />
    <path d="M10 19.5a2 2 0 0 0 4 0" />
  </Svg>
);

export const IcoCam = () => (
  <Svg>
    <rect x="3" y="7" width="18" height="13" rx="3" />
    <path d="M8.5 7L10 4h4l1.5 3" />
    <circle cx="12" cy="13" r="3.4" />
  </Svg>
);

export const IcoGlobe = () => (
  <Svg>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M3.5 12h17M12 3.5c2.4 2.3 3.6 5.3 3.6 8.5s-1.2 6.2-3.6 8.5c-2.4-2.3-3.6-5.3-3.6-8.5S9.6 5.8 12 3.5z" />
  </Svg>
);

export const IcoGift = () => (
  <Svg>
    <rect x="4" y="9" width="16" height="11" rx="2" />
    <path d="M12 9v11M4 13.5h16" />
    <path d="M12 9c-1.5-2.5-4-3.8-5.5-2.3S7.5 9 9.5 9zM12 9c1.5-2.5 4-3.8 5.5-2.3S16.5 9 14.5 9z" />
  </Svg>
);

/** Приоткрытая дверь + стрелка наружу. */
export const IcoLogout = () => (
  <Svg>
    <path d="M3 21V5a2 2 0 0 1 2-2h7v18H5a2 2 0 0 1-2-2z" />
    <path d="M12 3l7 2.2v13.6L12 21" />
    <path d="M15.5 12H22" />
    <path d="M19.5 9.5L22 12l-2.5 2.5" />
  </Svg>
);
