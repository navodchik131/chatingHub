const SW = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
const FILL = 'fill="currentColor" stroke="none"'
const svg = (b: string, a = SW) =>
  `<svg viewBox="0 0 24 24" width="20" height="20" ${a} xmlns="http://www.w3.org/2000/svg">${b}</svg>`

export const I = {
  check: svg('<path d="M4.6 12.7 9 17.1 19.4 6.7"/>', 'fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"'),
  checks: svg('<path d="M1.8 12.7 6.1 17 14.3 7.6"/><path d="m10.6 16.3 1 1.1L22.2 6.9"/>', 'fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"'),
  send: svg('<path d="M2.4 3.3 21.6 12 2.4 20.7l2.3-7.4L14.4 12 4.7 10.7z"/>', FILL),
  mic: svg('<rect x="9" y="2.4" width="6" height="11.2" rx="3"/><path d="M5.4 11.2a6.6 6.6 0 0 0 13.2 0"/><path d="M12 17.8v3.1"/><path d="M8.6 20.9h6.8"/>'),
  smile: svg('<circle cx="12" cy="12" r="8.8"/><path d="M8.6 14.1a4.3 4.3 0 0 0 6.8 0"/><path d="M9.1 9.6h.02"/><path d="M14.9 9.6h.02"/>'),
  clip: svg('<path d="M20.1 11.6 11.7 20a5.4 5.4 0 0 1-7.6-7.6l8.5-8.5a3.6 3.6 0 0 1 5.1 5.1l-8.4 8.4a1.8 1.8 0 0 1-2.5-2.5l7.7-7.7"/>'),
  search: svg('<circle cx="10.8" cy="10.8" r="6.9"/><path d="m20.4 20.4-4.8-4.8"/>'),
  dots: svg('<circle cx="12" cy="5.2" r="1.75"/><circle cx="12" cy="12" r="1.75"/><circle cx="12" cy="18.8" r="1.75"/>', FILL),
  back: svg('<path d="M20 12H4.4"/><path d="m10.6 5.4-6.2 6.6 6.2 6.6"/>'),
  close: svg('<path d="m6.2 6.2 11.6 11.6"/><path d="M17.8 6.2 6.2 17.8"/>'),
  down: svg('<path d="M12 4.6v14.8"/><path d="m5.4 12.9 6.6 6.5 6.6-6.5"/>'),
  up: svg('<path d="M12 19.4V4.6"/><path d="m5.4 11.1 6.6-6.5 6.6 6.5"/>'),
  plus: svg('<path d="M12 5v14"/><path d="M5 12h14"/>'),
  chevL: svg('<path d="m14.4 5.6-6.4 6.4 6.4 6.4"/>'),
  chevR: svg('<path d="m9.6 5.6 6.4 6.4-6.4 6.4"/>'),
  folderPlus: svg('<path d="M3.4 7a2.2 2.2 0 0 1 2.2-2.2h3.2l2.3 2.7h7.3a2.2 2.2 0 0 1 2.2 2.2v7.6a2.2 2.2 0 0 1-2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2z"/><path d="M12 11.4v4.4M9.8 13.6h4.4"/>'),
  folder: svg('<path d="M3.4 7a2.2 2.2 0 0 1 2.2-2.2h3.2l2.3 2.7h7.3a2.2 2.2 0 0 1 2.2 2.2v7.6a2.2 2.2 0 0 1-2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2z"/>'),
  globe: svg('<circle cx="12" cy="12" r="8.8"/><path d="M3.4 12h17.2"/><path d="M12 3.2a13.6 13.6 0 0 1 0 17.6"/><path d="M12 3.2a13.6 13.6 0 0 0 0 17.6"/>'),
  note: svg('<path d="M6.4 3.4h8.2l5 5v12.2H6.4z"/><path d="M14.6 3.4v5h5"/><path d="M9.2 12.4h6M9.2 16h4"/>'),
  moon: svg('<path d="M20.4 14.3A8.6 8.6 0 0 1 9.7 3.6a8.6 8.6 0 1 0 10.7 10.7z"/>'),
  info: svg('<circle cx="12" cy="12" r="8.8"/><path d="M12 11v5.4"/><path d="M12 7.6h.02"/>'),
  link: svg('<path d="M10.4 13.6a4.4 4.4 0 0 0 6.4 0l2.4-2.4a4.4 4.4 0 1 0-6.2-6.2l-1.3 1.3"/><path d="M13.6 10.4a4.4 4.4 0 0 0-6.4 0l-2.4 2.4a4.4 4.4 0 1 0 6.2 6.2l1.3-1.3"/>'),
  photo: svg('<rect x="3" y="5" width="18" height="14" rx="2.6"/><circle cx="8.8" cy="10.2" r="1.6"/><path d="m4.4 17.6 4.9-4.9 3.5 3.5 2.7-2.3 4.5 3.9"/>'),
  file: svg('<path d="M13.8 3.2H7.4a2.4 2.4 0 0 0-2.4 2.4v12.8a2.4 2.4 0 0 0 2.4 2.4h9.2a2.4 2.4 0 0 0 2.4-2.4V8.4z"/><path d="M13.8 3.2v5.2H19"/>'),
  trash: svg('<path d="M4.6 6.7h14.8"/><path d="M9.6 6.7V4.4h4.8v2.3"/><path d="M6.9 6.7 8.1 20.2h7.8L17.1 6.7"/><path d="M10.4 10.4v6M13.6 10.4v6"/>'),
  reply: svg('<path d="M9.5 13.5 4 18v-4.5H2.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H13a1 1 0 0 1 1 1v5.5a1 1 0 0 1-1 1H12l-3.5 3.5z"/>'),
  copy: svg('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 0 1 2-2h10"/>'),
  bell: svg('<path d="M12 3a5 5 0 0 1 5 5v3.5l1.5 2.5H5.5L7 11.5V8a5 5 0 0 1 5-5z"/><path d="M10 18a2 2 0 0 0 4 0"/>'),
  pin: svg('<path d="M14 4.5 9.5 9l-4.5 1 6 6 1-4.5L16.5 7z"/><path d="M6 18l3-3"/>'),
}
