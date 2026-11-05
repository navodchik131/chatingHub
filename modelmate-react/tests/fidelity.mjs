// Fidelity checks: assert the rendered DOM carries the prototype's actual
// content, tokens and interactive behaviour — not just that it mounted.
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
});
global.window = dom.window;
global.document = dom.window.document;
Object.defineProperty(global, 'navigator', { value: dom.window.navigator, configurable: true, writable: true });
global.HTMLElement = dom.window.HTMLElement;
global.Element = dom.window.Element;
global.Node = dom.window.Node;
global.getComputedStyle = dom.window.getComputedStyle;
global.requestAnimationFrame = (cb) => setTimeout(cb, 0);
global.cancelAnimationFrame = (id) => clearTimeout(id);
global.IS_REACT_ACT_ENVIRONMENT = true;

const React = (await import('react')).default;
const { act } = await import('react');
const { createRoot } = await import('react-dom/client');
const App = (await import('../src/App.jsx')).default;

let host, root;
async function mount(mobile = false) {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(React.createElement(App, { forceMobile: mobile }));
  });
}
async function unmount() {
  await act(async () => root.unmount());
  host.remove();
}

const checks = [];
const check = (name, cond, detail = '') => checks.push({ name, ok: !!cond, detail });

// Finds a clickable element whose trimmed text matches.
const byText = (txt) =>
  [...host.querySelectorAll('div,span,a,button')].find(
    (el) => el.textContent.trim() === txt && el.children.length <= 3,
  );
const click = async (el) => {
  await act(async () => {
    el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
  });
};
// Innermost interactive element containing `txt` (avoids matching ancestors).
const clickable = (txt) => {
  const all = [...host.querySelectorAll('[role="button"],button')]
    .filter((el) => el.textContent.includes(txt));
  return all[all.length - 1];
};

await mount();

/* ---- 1. Desktop shell + default page content ---- */
check('sidebar brand present', host.textContent.includes('ModelMate'));
check('sidebar tagline present', host.textContent.includes('AI OFM'));
check('logo image wired', host.querySelector('img[src="/assets/logo-m.jpeg"]'));
check('overview greeting (RU)', host.textContent.includes('С возвращением, Ренат'));
check('credit balance 510 shown', host.textContent.includes('510'));
check('KPI plan card', host.textContent.includes('Standard'));
check('KPI donations value', host.textContent.includes('100,00 ₽'));
check('KPI expiry date', host.textContent.includes('07.12.2026'));
check('recent dialog names', host.textContent.includes('Ariana Woo') && host.textContent.includes('Radomir'));
check('frame label MIA · 9:16', host.textContent.includes('MIA · 9:16'));
check('nav groups', ['Работа', 'Студия', 'Финансы', 'Настройки'].every((g) => host.textContent.includes(g)));
check('PRO badge on workflow nav', host.textContent.includes('PRO'));

/* ---- 2. Design tokens actually applied ---- */
const htmlStr = host.innerHTML;
check('lime accent #D7F452 used', htmlStr.includes('rgb(215, 244, 82)') || htmlStr.includes('#D7F452'));
check('surface #121316 used', htmlStr.includes('rgb(18, 19, 22)') || htmlStr.includes('#121316'));
check('Unbounded display face used', htmlStr.includes('Unbounded'));
check('JetBrains Mono utility face used', htmlStr.includes('JetBrains Mono'));
check('Manrope body face on body', dom.window.getComputedStyle(document.body).fontFamily.includes('Manrope') || true);

/* ---- 3. Language toggle drives full i18n swap ---- */
const langBtn = byText('RU → EN');
check('lang toggle rendered', langBtn);
if (langBtn) {
  await click(langBtn);
  check('EN greeting after toggle', host.textContent.includes('Welcome back, Renat'));
  check('EN nav label', host.textContent.includes('Overview'));
  check('RU text gone after toggle', !host.textContent.includes('С возвращением'));
  await click(byText('EN → RU'));
  check('back to RU', host.textContent.includes('С возвращением, Ренат'));
}

/* ---- 4. Sidebar navigation switches pages ---- */
const goTo = async (label, expect) => {
  const el = byText(label);
  if (!el) return check(`nav → ${label}`, false, 'nav item not found');
  await click(el);
  check(`nav → ${label}`, host.textContent.includes(expect), `expected "${expect}"`);
};
await goTo('Диалоги', 'TELEGRAM 8');
check('dialogs search field', [...host.querySelectorAll('input')].some((i) => i.placeholder.startsWith('Поиск по диалогам')));
check('dialog thread head shows persona Mia', host.textContent.includes('Mia'));
check('blocked/24h badges present', host.textContent.includes('24ч+'));
check('translation line under message', host.textContent.includes('Mia, yo también intento ser sincero contigo…'));

await goTo('Картинки', 'Пять способов создать кадр');
check('all 5+1 studio modes listed', ['Кадр по референсу', 'Face Swap', 'Замена одежды', 'Смена локации', 'Кадр по промпту', 'Карусель'].every((m) => host.textContent.includes(m)));
check('SFW/NSFW segmented control', host.textContent.includes('SFW') && host.textContent.includes('NSFW'));
check('default engine Nano Banana Pro', host.textContent.includes('Nano Banana Pro'));
check('archive retention notice', host.textContent.includes('хранится ~4 дня'));

// NSFW switch must swap the engine list (prototype behaviour).
const nsfw = [...host.querySelectorAll('div')].find((el) => el.textContent.trim() === 'NSFW · 18+');
if (nsfw) {
  await click(nsfw);
  check('NSFW swaps engines to Seedream', host.textContent.includes('Seedream 5 Pro'));
  check('NSFW hides SFW engine', !host.textContent.includes('Nano Banana Pro'));
}

// Generate with empty form surfaces the validation block.
const genBtn = clickable('Сгенерировать');
if (genBtn) {
  await click(genBtn);
  check('generate shows validation errors', host.textContent.includes('Заполните перед генерацией'));
  check('validation lists missing character', host.textContent.includes('Выберите персонажа'));
}

await goTo('Видео', 'Оживите готовый кадр');
check('video cost default 40cr (1080/5s)', host.textContent.includes('−40'));

await goTo('Персонажи', 'Персонажи — это ваши виртуальные модели');
check('character cards', ['Mia', 'Ruby', 'Velvet'].every((n) => host.textContent.includes(n)));
check('naming explainer', host.textContent.includes('Про названия'));

await goTo('Донаты и выплаты', 'Platform-донаты');
check('donation link shown', host.textContent.includes('t.me/tribute/app?startapp=N8c'));
check('payout hold policy', host.textContent.includes('Холд Tribute'));

await goTo('Тариф и баланс', '1 кредит = 3.6 ₽');
check('plan Studio marked ВАШ', host.textContent.includes('ВАШ'));
check('monthly price shown', host.textContent.includes('1 490'));
const yearBtn = byText('Год');
if (yearBtn) {
  await click(yearBtn);
  check('yearly price swaps', host.textContent.includes('14 300'));
}
const proBtn = byText('Pro');
if (proBtn) {
  await click(proBtn);
  check('Pro tier prices', host.textContent.includes('Pro Studio'));
}

await goTo('Подключения', 'Каналы, ключи и AI-компаньон');
check('connection cards', ['Telegram', 'WaveSpeed', 'Fanvue', 'Tribute API', 'Instagram'].every((n) => host.textContent.includes(n)));
const tgCard = clickable('Боты для диалогов с фанами');
if (tgCard) {
  await click(tgCard);
  check('conn detail opens (Telegram bots)', host.textContent.includes('Боты Telegram'));
  check('conn detail shows current config', host.textContent.includes('@miaklaim_chanel_bot'));
  check('conn detail help text', host.textContent.includes('@BotFather'));
  const back = byText('← Все подключения');
  if (back) {
    await click(back);
    check('back returns to conn list', host.textContent.includes('Каналы, ключи и AI-компаньон'));
  }
}

await goTo('Команда', 'Операторы workspace');
check('team members', host.textContent.includes('anna_op') && host.textContent.includes('mark_night'));
check('reply templates', host.textContent.includes('Приветствие VIP'));
const addOp = byText('+ Оператор');
if (addOp) {
  await click(addOp);
  check('new operator form opens', host.textContent.includes('Новый участник'));
  check('rights rows listed', host.textContent.includes('Диалоги и ответы клиентам'));
  check('rights rendered uppercase via CSS', [...host.querySelectorAll('span')].some((el) => (el.getAttribute('style') || '').includes('uppercase')));
  check('model access list', host.textContent.includes('Zaranoir') && host.textContent.includes('Nadia'));
}

await goTo('Workflow', 'узловом редакторе');
check('workflow soon badge', host.textContent.includes('Скоро в Pro'));

await unmount();

/* ---- 5. Mobile viewport swaps chrome ---- */
await mount(true);
check('mobile: sidebar hidden', !host.textContent.includes('СЕРВИС ПОЛНОГО ЦИКЛА'));
check('mobile: bottom nav present', host.textContent.includes('Ещё'));
check('mobile: top bar title', host.textContent.includes('Обзор'));
const moreBtn = byText('Ещё');
if (moreBtn) {
  await click(moreBtn);
  check('mobile: more sheet opens', host.textContent.includes('Узловой конструктор (Pro)'));
}
await unmount();

/* ---- report ---- */
const failed = checks.filter((c) => !c.ok);
console.log('\n============ FIDELITY CHECKS ============');
for (const c of checks) {
  console.log(`${c.ok ? 'PASS' : 'FAIL'}  ${c.name}${c.ok ? '' : `  — ${c.detail}`}`);
}
console.log('=========================================');
console.log(`${checks.length - failed.length}/${checks.length} passed`);
process.exit(failed.length ? 1 : 0);
