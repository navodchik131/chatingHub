// Runtime smoke test: mounts the real app in JSDOM, visits every page in both
// languages and at both viewports, and fails on any React error/warning.
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
});

global.window = dom.window;
global.document = dom.window.document;
Object.defineProperty(global, 'navigator', {
  value: dom.window.navigator,
  configurable: true,
  writable: true,
});
global.HTMLElement = dom.window.HTMLElement;
global.Element = dom.window.Element;
global.Node = dom.window.Node;
global.getComputedStyle = dom.window.getComputedStyle;
global.requestAnimationFrame = (cb) => setTimeout(cb, 0);
global.cancelAnimationFrame = (id) => clearTimeout(id);
global.IS_REACT_ACT_ENVIRONMENT = true;

// Capture console noise as failures.
const problems = [];
for (const level of ['error', 'warn']) {
  const orig = console[level];
  console[level] = (...args) => {
    problems.push(`[${level}] ${args.map(String).join(' ')}`);
    orig(...args);
  };
}

const React = (await import('react')).default;
const { act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { AppProvider, useApp } = await import('../src/hooks/useApp.jsx');

// Import every page directly so each is exercised even if routing changes.
const Overview = (await import('../src/pages/Overview.jsx')).default;
const GuideMod = await import('../src/pages/Guide.jsx');
const Dialogs = (await import('../src/pages/Dialogs.jsx')).default;
const ImagesMod = await import('../src/pages/Images.jsx');
const Video = (await import('../src/pages/Video.jsx')).default;
const Characters = (await import('../src/pages/Characters.jsx')).default;
const Donations = (await import('../src/pages/Donations.jsx')).default;
const Billing = (await import('../src/pages/Billing.jsx')).default;
const Connections = (await import('../src/pages/Connections.jsx')).default;
const TeamMod = await import('../src/pages/Team.jsx');
const Workflow = (await import('../src/pages/Workflow.jsx')).default;
const Sidebar = (await import('../src/components/Sidebar.jsx')).default;
const MobileNavMod = await import('../src/components/MobileNav.jsx');

const PAGES = {
  overview: Overview,
  guide: GuideMod.default,
  dialogs: Dialogs,
  images: ImagesMod.default,
  video: Video,
  characters: Characters,
  donations: Donations,
  billing: Billing,
  connections: Connections,
  team: TeamMod.default,
  newOperator: TeamMod.NewOperator,
  workflow: Workflow,
};

// Drives state into a target shape, then renders the chosen page + chrome.
function Harness({ page, patch, mobile }) {
  const { setS, s } = useApp();
  const Page = PAGES[page];
  const applied = React.useRef(false);

  // Patch in an effect — calling setS during render is a harness bug, not an app one.
  React.useEffect(() => {
    if (!applied.current) {
      applied.current = true;
      if (patch) setS(patch);
    }
  }, []);

  return React.createElement(
    'div',
    null,
    mobile
      ? React.createElement(MobileNavMod.MobileTopBar)
      : React.createElement(Sidebar),
    React.createElement(Page),
    React.createElement(ImagesMod.Lightbox),
    React.createElement(GuideMod.MediaModal),
    mobile ? React.createElement(MobileNavMod.MobileNav) : null,
    s.moreOpen ? React.createElement(MobileNavMod.MoreSheet) : null,
  );
}

async function render(label, page, patch, { mobile = false, lang = 'ru' } = {}) {
  const before = problems.length;
  const host = document.createElement('div');
  document.body.appendChild(host);
  const root = createRoot(host);

  await act(async () => {
    root.render(
      React.createElement(
        AppProvider,
        { forceMobile: mobile },
        React.createElement(Harness, { page, patch: { ...patch, lang }, mobile }),
      ),
    );
  });

  const text = host.textContent || '';
  const html = host.innerHTML || '';
  await act(async () => root.unmount());
  host.remove();

  const newProblems = problems.slice(before);
  const ok = html.length > 200 && newProblems.length === 0;
  results.push({ label, ok, chars: html.length, textLen: text.length, problems: newProblems });
  return ok;
}

const results = [];

// Every page, desktop, both languages.
for (const lang of ['ru', 'en']) {
  for (const page of Object.keys(PAGES)) {
    await render(`${page} [${lang}]`, page, null, { lang });
  }
}

// Interactive / conditional states that plain page loads never reach.
await render('images: carousel + nsfw + archive-slot + error', 'images', {
  imgMode: 'carousel', contentMode: 'nsfw', aiModel: 'seedream',
  showGenError: true, slotSource: { 'carousel:0': 'archive' },
});
await render('images: outfit (2 slots)', 'images', { imgMode: 'outfit' });
await render('images: lightbox open', 'images', { lightbox: 2 });
await render('video: generate-first-frame loading', 'video', { hasFirstFrame: 'no', ffState: 'loading' });
await render('video: first-frame done + 4k/10s', 'video', {
  hasFirstFrame: 'no', ffState: 'done', vidQuality: '4k', vidTime: '10',
});
await render('dialogs: blocked chat + reactions + emoji', 'dialogs', {
  chatOpen: 2, reactions: { 0: '🔥' }, emojiOpen: true, noteFormOpen: true,
});
await render('dialogs: msg react popover', 'dialogs', { msgReact: 1 });
await render('dialogs: filter with no matches', 'dialogs', { chatFilter: 'vip', chatPlatform: 'FANVUE' });
await render('characters: detail persona', 'characters', { charDetail: 'mia', charTab: 'persona' });
await render('characters: detail exif', 'characters', { charDetail: 'mia', charTab: 'exif' });
await render('characters: detail history', 'characters', { charDetail: 'mia', charTab: 'history' });
await render('characters: photo menu open', 'characters', { charDetail: 'mia', charTab: 'photos', photoMenu: 1 });
await render('guide: media modal open', 'guide', { mediaStep: 3 });
await render('donations: create tab', 'donations', { donTab: 'create' });
await render('billing: pro + year', 'billing', { tier: 'pro', period: 'year' });
for (const id of ['tg', 'wavespeed', 'fanvue', 'tribute', 'ig', 'push']) {
  await render(`connections: detail ${id}`, 'connections', { connDetail: id });
}
await render('newOperator: error state', 'newOperator', {
  opError: true, opRights: { chat: false, studio: false, models: false, keys: false, billing: false },
});

// Mobile viewport: nav chrome, thread view, more sheet.
await render('mobile: overview', 'overview', null, { mobile: true });
await render('mobile: dialogs list', 'dialogs', { mobileChat: false }, { mobile: true });
await render('mobile: dialogs thread', 'dialogs', { mobileChat: true }, { mobile: true });
await render('mobile: more sheet', 'overview', { moreOpen: true }, { mobile: true });
await render('mobile: images', 'images', null, { mobile: true });

const failed = results.filter((r) => !r.ok);
console.log('\n================ RESULTS ================');
for (const r of results) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.label.padEnd(42)} html=${r.chars}`);
  for (const p of r.problems) console.log(`        ↳ ${p.slice(0, 300)}`);
}
console.log('=========================================');
console.log(`${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
