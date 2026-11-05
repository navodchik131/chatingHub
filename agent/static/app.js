/* Persona Studio — интерфейс (Lumen). Ванильный JS, без сборки. */
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const ls = {get(k, d){try{const v = localStorage.getItem('ps_' + k); return v === null ? d : JSON.parse(v)}catch(e){return d}}, set(k, v){try{localStorage.setItem('ps_' + k, JSON.stringify(v))}catch(e){}}};

/* Адреса относительно страницы: локально «/», в кабинете model-mate — «/workspace/agent/». */
const BASE = location.pathname.replace(/[^/]*$/, '');
const U = u => (typeof u === 'string' && u.startsWith('/') ? BASE + u.slice(1) : u);
function authH(){ try { const t = localStorage.getItem('chating_token'); return t ? {Authorization: 'Bearer ' + t} : {}; } catch(e){ return {}; } }
const xfetch = (u, o = {}) => fetch(U(u), {credentials: 'same-origin', ...o, headers: {...authH(), ...(o.headers || {})}});
const HOSTED = () => !!S.cfg?.hosted;
async function api(url, opt = {}){
  const r = await xfetch(url, {...opt, headers: {'Content-Type': 'application/json', ...(opt.headers || {})}});
  if (r.headers.get('content-type')?.includes('zip')) return r;
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && j.login){ location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search); throw new Error('Нужно войти'); }
  if (r.status === 403 && j.reason){ gate(j.error); throw new Error(j.error); }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function gate(text){
  $('#app').innerHTML = `<div class="empty" style="margin:auto;max-width:440px;padding:40px 20px"><h2>Новый кабинет · демо</h2><p>${esc(text)}</p>
    <p><a class="btn p" href="/workspace/">Вернуться в кабинет</a></p></div>`;
}
const post = (url, body, method = 'POST') => api(url, {method, body: JSON.stringify(body || {})});

/* ---------- icons ---------- */
const P = {
  plus: '<path d="M12 5v14M5 12h14"/>', search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  sliders: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10h14V9M10 13h4"/>', trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  chevR: '<path d="m9 6 6 6-6 6"/>', chevL: '<path d="m15 6-6 6 6 6"/>', chevD: '<path d="m6 9 6 6 6-6"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>', menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  rollback: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>', regen: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/>',
  check: '<path d="m5 12 5 5 9-10"/>', warn: '<path d="M12 8v5M12 16.5v.5"/>', x: '<path d="M6 6l12 12M18 6 6 18"/>',
  star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>', expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  face: '<circle cx="12" cy="9" r="4"/><path d="M5 20c1.5-3.5 4-5 7-5s5.5 1.5 7 5"/>', body: '<circle cx="12" cy="4.5" r="2"/><path d="M12 7v7M8 10h8M12 14l-3 7M12 14l3 7"/>',
  clip: '<path d="m20 11-8.5 8.5a5 5 0 0 1-7-7L13 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L14 7"/>', send: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>', play: '<path d="M8 5v14l11-7z"/>', eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>', upload: '<path d="M12 16V5M7 10l5-5 5 5M5 20h14"/>',
  compare: '<rect x="3" y="5" width="8" height="14" rx="1.5"/><rect x="13" y="5" width="8" height="14" rx="1.5"/>', select: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 12 3 3 5-6"/>',
  thread: '<path d="M4 6h16M4 12h10M4 18h7"/>', pin: '<path d="M12 17v5M5 17h14l-2-4V5H7v8z"/>',
};
const ic = (n, cls = '', st = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true" style="${st}">${P[n] || ''}</svg>`;

/* ---------- state ---------- */
const S = {
  chats: [], cur: ls.get('cur', null), chat: null, view: 'chat', cfg: null,
  q: '', sort: ls.get('sort', 'recent'), panel: ls.get('panel', true),
  attach: [], engine: 'auto', menu: null,
  gal: {filter: 'all', engine: 'all', order: 'new', select: false, sel: new Set()},
  cardTab: 'card', jobSel: 0, promptOpen: false, balance: null, spend: null,
  settingsTab: 'system', promptsCache: {}, lastSig: '',
};
const ENG = {gpt: 'GPT Image 2.5', seedream: 'Seedream V5.0 Pro'};
const ENGX = {...ENG, seedance: 'Seedance 2.5'};
const vUrl = (id, chat = S.chat) => chat?.videos?.[id] ? `${BASE}files/${chat.id}/${chat.videos[id].file}` : '';
const vThUrl = (id, chat = S.chat) => chat?.videos?.[id] ? `${BASE}thumbs/${chat.id}/${chat.videos[id].file}` : '';
const VSRC = {user: 'исходник', trim: 'обрезка', lineart: 'силуэт', gen: 'Seedance'};
function vplayer(id, opts = {}){
  const r = S.chat.videos?.[id]; if (!r) return '<span class="meta">видео удалено</span>';
  return `<div class="vbox ${opts.small ? 'sm' : ''}"><video src="${vUrl(id)}" poster="${vThUrl(id)}" controls playsinline preload="none"></video>
    <div class="vcap"><span class="badge">${VSRC[r.source] || r.source}</span><span>${r.dur} с · ${r.w}×${r.h}${r.resolution ? ' · ' + r.resolution : ''}</span><span style="flex:1"></span>
      <a class="ib" href="${vUrl(id)}" download="${esc(S.chat.name)}_${id}.${r.file.split('.').pop()}" title="Скачать" aria-label="Скачать">${ic('download')}</a>
      <button class="ib" data-act="vlb" data-id="${id}" title="Подробнее" aria-label="Подробнее">${ic('expand')}</button></div></div>`;
}
const isVid = f => f.type.startsWith('video/') || /\.(mp4|mov|webm|m4v|mkv|avi)$/i.test(f.name || '');
const isMedia = f => f.type.startsWith('image/') || isVid(f);
const imgUrl = (id, chat = S.chat) => chat?.images?.[id] ? `${BASE}files/${chat.id}/${chat.images[id].file}` : '';
const thUrl = (id, chat = S.chat) => chat?.images?.[id] ? `${BASE}thumbs/${chat.id}/${chat.images[id].file}` : '';
const usd = v => '$' + (Number(v) || 0).toFixed(2);
const cr = v => { const n = Number(v) || 0; return (n > 0 ? Math.max(1, Math.ceil(n * (S.cfg?.multiplier || 2) * 100 - 1e-9)) : 0) + ' кр.'; };
/* потрачено в чате (Grok + генерации) */
const money = v => HOSTED() ? cr(v) : usd(v);
/* цена генерации WaveSpeed: на своём ключе (Pro) — в долларах с ключа пользователя */
const wsMoney = v => HOSTED() ? (S.cfg.ws_mode === 'platform' ? cr(v) : usd(v) + ' WaveSpeed') : usd(v);
function when(t){
  if (!t) return '';
  const d = (Date.now() / 1000 - t);
  if (d < 60) return 'сейчас';
  if (d < 3600) return Math.floor(d / 60) + ' мин';
  if (d < 86400) return Math.floor(d / 3600) + ' ч';
  if (d < 172800) return 'вчера';
  return new Date(t * 1000).toLocaleDateString('ru', {day: 'numeric', month: 'short'});
}
const mmss = s => { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
function toast(t){ const el = $('#toast'); el.textContent = t; el.classList.add('on'); clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove('on'), 2600); }
function md(src){
  const inl = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const out = []; let list = null;
  const flush = () => { if (list){ out.push(`<${list.t}>${list.items.map(i => `<li>${inl(i)}</li>`).join('')}</${list.t}>`); list = null; } };
  let para = [];
  const fp = () => { if (para.length){ out.push(`<p>${para.map(inl).join('<br>')}</p>`); para = []; } };
  for (const raw of String(src || '').split('\n')){
    const l = raw.trimEnd();
    let m;
    if ((m = l.match(/^\s*[-*•]\s+(.*)/))){ fp(); if (!list || list.t !== 'ul'){ flush(); list = {t: 'ul', items: []}; } list.items.push(m[1]); }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))){ fp(); if (!list || list.t !== 'ol'){ flush(); list = {t: 'ol', items: []}; } list.items.push(m[1]); }
    else if ((m = l.match(/^#{1,6}\s+(.*)/))){ fp(); flush(); out.push(`<h4>${inl(m[1])}</h4>`); }
    else if (!l.trim()){ fp(); flush(); }
    else { flush(); para.push(l); }
  }
  fp(); flush();
  return out.join('');
}
function chatStatus(c){
  if (c.running && c.status !== 'awaiting') return ['s-run', 'генерирует'];
  if (c.status === 'awaiting') return ['s-wait', 'ждёт подтверждения'];
  if (c.status === 'error') return ['s-err', 'ошибка API'];
  if (c.refs > 0 || c.persona?.faces?.length) return ['s-ok', 'готова'];
  return ['s-idle', 'нет эталонов'];
}

/* ---------- data ---------- */
async function loadChats(){
  S.chats = await api('/api/chats');
  if (HOSTED()) { try { const b = await api('/api/balance'); S.cfg.balance = b.credits; } catch(e){} }
  renderSide();
}
async function loadChat(id, force){
  if (!id) { S.chat = null; render(); return; }
  try { S.chat = await api('/api/chats/' + id); }
  catch(e){ S.cur = null; ls.set('cur', null); S.chat = null; render(); return; }
  const sig = JSON.stringify([S.chat.messages.length, S.chat.messages.at(-1)?.id, S.chat.status, S.chat.status_text, S.chat.pending, S.chat.jobs, S.chat.running, S.chat.persona, S.chat.name, S.chat.spent, Object.keys(S.chat.images).length, Object.values(S.chat.images).filter(i => i.fav).length]);
  if (force || sig !== S.lastSig){ S.lastSig = sig; render(); }
  schedulePoll();
}
let pollT = null;
function schedulePoll(){
  clearTimeout(pollT);
  const busy = S.chat && (S.chat.running || S.chat.status === 'running');
  pollT = setTimeout(async () => {
    if (S.cur) await loadChat(S.cur);
    if (!busy) loadChats();
  }, busy ? 1500 : 6000);
}
async function openChat(id){
  S.cur = id; ls.set('cur', id); S.attach = []; S.jobSel = 0; S.promptOpen = false; S.lastSig = '';
  S.gal.sel.clear(); S.gal.select = false;
  if (S.view === 'settings') S.view = 'chat';
  $('#app').classList.remove('side-on');
  await loadChat(id, true); renderSide();
}
async function loadMeta(){
  try { S.cfg = await api('/api/config'); } catch(e){}
  try { S.spend = await api('/api/spend'); } catch(e){}
  api('/api/balance').then(b => { S.balance = b; renderSide(); }).catch(() => {});
}

/* ---------- render: root ---------- */
function render(){
  const app = $('#app');
  app.classList.toggle('nopanel', !S.panel || S.view !== 'chat' || !S.chat);
  renderSide();
  if (S.view === 'settings') renderSettings();
  else if (S.view === 'gallery' && S.chat) renderGallery();
  else renderChat();
  renderPanel();
}

/* ---------- sidebar ---------- */
function renderSide(){
  const q = S.q.trim().toLowerCase();
  let list = S.chats.filter(c => !q || c.name.toLowerCase().includes(q));
  if (S.sort === 'name') list.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  const ids = new Set(list.map(c => c.id));
  const top = list.filter(c => !c.archived && !(c.parent && ids.has(c.parent)));
  const arch = list.filter(c => c.archived);
  top.sort((a, b) => (b.pinned - a.pinned));
  const kids = p => list.filter(c => c.parent === p && !c.archived);
  const curRoot = S.chats.find(c => c.id === S.cur)?.parent || S.cur;
  const card = c => {
    const [st, stt] = chatStatus(c);
    const active = c.id === curRoot;
    const th = kids(c.id);
    return `<div class="mc ${active ? 'act' : ''} ${S.menu === c.id ? 'mopen' : ''}">
      <button class="mc-main" data-act="open" data-id="${c.id}">
        ${c.thumb ? `<img class="av" src="${U(c.thumb)}" alt="">` : `<div class="av noimg">${esc((c.name[0] || '?').toUpperCase())}</div>`}
        <div class="mc-body">
          <div class="mc-l1"><span class="mc-name">${c.pinned ? ic('pin', '', 'width:12px;height:12px;margin-right:4px;color:var(--faint)') : ''}${esc(c.name)}</span><span class="mc-when">${when(c.updated)}</span></div>
          <div class="mc-l2"><span class="pill ${st}">${stt}</span><span class="cost" style="font-size:11.5px">${money(c.spent)}</span></div>
        </div>
      </button>
      <button class="ib mc-more" data-act="menu" data-id="${c.id}" aria-label="Действия с моделью">${ic('more')}</button>
      ${S.menu === c.id ? modelMenu(c) : ''}
      ${active && th.length ? `<div class="thrs">
        <button class="thr ${S.cur === c.id ? 'on' : ''}" data-act="open" data-id="${c.id}"><span style="flex:1">Основной чат</span></button>
        ${th.map(t => `<button class="thr ${S.cur === t.id ? 'on' : ''}" data-act="open" data-id="${t.id}"><span style="flex:1">${esc(t.name.replace(c.name + ' · ', ''))}</span><span class="meta" style="font-size:11px">${t.images}</span></button>`).join('')}
        <button class="thr add" style="color:var(--faint)" data-act="newthread" data-id="${c.id}">+ чат в другой локации</button></div>` : ''}
    </div>`;
  };
  const sp = S.spend || {}; const bal = S.balance;
  $('#side').innerHTML = `
    <div class="brand"><div class="logo"><i></i></div><b>Persona Studio</b>
      <button class="ib ${S.view === 'settings' ? 'on' : ''}" data-act="settings" aria-label="Настройки" title="Настройки">${ic('sliders')}</button></div>
    <div class="side-top">
      <button class="btn p w" data-act="create">${ic('plus')}Новая модель</button>
      <div class="search">${ic('search')}<label class="sr" for="q">Поиск по имени</label><input id="q" class="field" placeholder="Поиск по имени" value="${esc(S.q)}"></div>
      <div class="row-sb"><span class="lbl">Модели · ${S.chats.filter(c => !c.archived && !c.parent).length}</span>
        <div class="seg"><button class="${S.sort === 'recent' ? 'on' : ''}" data-act="sort" data-v="recent">Недавние</button><button class="${S.sort === 'name' ? 'on' : ''}" data-act="sort" data-v="name">А–Я</button></div></div>
    </div>
    <div class="mlist scroll">
      ${top.length ? top.map(card).join('') : `<div class="empty" style="padding:30px 10px"><div class="plus">${ic('plus')}</div><h2 style="font-size:15px">${q ? 'Ничего не найдено' : 'Здесь будут твои модели'}</h2>${q ? '' : '<p>Создай с нуля по 2–3 фото лиц или импортируй готовую папку</p>'}</div>`}
      ${arch.length ? `<details class="arch" ${ls.get('archOpen', false) ? 'open' : ''}><summary data-act="archtoggle">${ic('archive')}Архив · ${arch.length}</summary>
        ${arch.map(c => `<div style="position:relative"><button class="arch-row" data-act="open" data-id="${c.id}">${c.thumb ? `<img src="${U(c.thumb)}" alt="">` : `<div class="av noimg" style="width:28px;height:28px">${esc(c.name[0] || '?')}</div>`}<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.name)}</span><span style="font-size:11px">${when(c.updated)}</span></button>
          <button class="ib mc-more" style="top:2px;opacity:1" data-act="menu" data-id="${c.id}">${ic('more')}</button>${S.menu === c.id ? modelMenu(c) : ''}</div>`).join('')}</details>` : ''}
    </div>
    ${HOSTED() ? `<div class="side-foot">
      <div><small>Баланс</small><span class="cost" style="font-weight:600">${(S.cfg.balance ?? 0)} кр.</span></div>
      <div><small>${S.cfg.ws_mode === 'platform' ? 'Генерации и Grok — из кредитов' : 'Генерации — ваш WaveSpeed, Grok — кредиты'}</small><a class="cost" href="${esc(S.cfg.billing_url)}" target="_top">Пополнить</a></div>
    </div>` : `<div class="side-foot">
      <div><small>Баланс WaveSpeed</small><span class="cost" style="font-weight:600">${bal?.wavespeed !== undefined ? money(bal.wavespeed) : '—'}</span></div>
      <div><small>Сегодня</small><span class="cost">${money(sp.today)}${sp.limit ? ' / ' + money(sp.limit).replace('.00', '') : ''}</span></div>
    </div>`}`;
  const qi = $('#q');
  qi.oninput = () => { S.q = qi.value; const pos = qi.selectionStart; renderSide(); const n = $('#q'); n.focus(); n.setSelectionRange(pos, pos); };
}
function modelMenu(c){
  return `<div class="menu-catch" data-act="closemenu"></div><div class="menu" style="top:46px;right:4px">
    <button data-act="rename" data-id="${c.id}">${ic('edit')}Переименовать</button>
    <button data-act="duplicate" data-id="${c.id}">${ic('copy')}Дублировать</button>
    <button data-act="newthread" data-id="${c.parent || c.id}">${ic('thread')}Новый чат с этой моделью</button>
    <button data-act="pin" data-id="${c.id}">${ic('pin')}${c.pinned ? 'Открепить' : 'Закрепить сверху'}</button>
    <button data-act="archive" data-id="${c.id}">${ic('archive')}${c.archived ? 'Вернуть из архива' : 'В архив'}</button>
    <hr><button class="dz" data-act="delete" data-id="${c.id}">${ic('trash')}Удалить…</button></div>`;
}

/* ---------- chat ---------- */
function renderChat(){
  const m = $('#main');
  if (!S.chat){
    m.innerHTML = `<div class="hdr"><button class="ib mob" data-act="sidebar">${ic('menu')}</button></div>
      <div class="empty"><div class="plus">${ic('plus')}</div><h2>Создай первую модель</h2><p>С нуля по 2–3 фото лиц или импортом готовой папки с card.md, faces/ и body/.</p>
      <div style="display:flex;gap:8px"><button class="btn p" data-act="create">Новая модель</button><button class="btn" data-act="create" data-mode="import">Импорт папки</button></div></div>`;
    return;
  }
  const c = S.chat;
  const keepScroll = $('.msgs');
  const nearBottom = !keepScroll || keepScroll.scrollHeight - keepScroll.scrollTop - keepScroll.clientHeight < 120;
  const prevTop = keepScroll?.scrollTop;
  const draft = $('#inp')?.value ?? ls.get('draft_' + c.id, '');
  const hadFocus = document.activeElement?.id === 'inp';
  const nImg = Object.keys(c.images).length;
  m.innerHTML = `
    <div class="hdr">
      <button class="ib mob" data-act="sidebar" aria-label="Модели">${ic('menu')}</button>
      <span class="name">${esc(c.name)}</span>
      <span class="sp"></span>
      <span class="meta hide-m">в этом чате <span class="cost">${money(c.spent)}</span></span>
      <button class="btn sm" data-act="gallery">${ic('grid')}<span class="hide-m">Галерея · </span>${nImg}</button>
      <button class="ib ${S.panel ? 'on' : ''}" data-act="panel" aria-label="Панель модели">${ic('panel')}</button>
    </div>
    <div class="msgs scroll"><div class="msgs-in" id="msgs">${renderMessages()}</div></div>
    <div class="jobs" id="jobs"></div>
    <div class="comp">
      <div class="comp-in">
        <div class="chips chips-row" id="chips"></div>
        <div class="box">
          <div class="atts" id="atts" ${S.attach.length ? '' : 'hidden'}></div>
          <label class="sr" for="inp">Сообщение</label>
          <textarea id="inp" rows="1" placeholder="Напиши Grok… Можно вставить фото из буфера или перетащить"></textarea>
          <div class="box-f">
            <button class="ib" data-act="attach" aria-label="Прикрепить фото" title="Прикрепить фото">${ic('clip')}</button>
            <div class="seg" title="Движок для следующего запроса">
              ${['auto', 'gpt', 'seedream'].map(e => `<button class="${S.engine === e ? 'on' : ''}" data-act="engine" data-v="${e}">${{auto: 'Авто', gpt: 'GPT', seedream: 'Seedream'}[e]}</button>`).join('')}</div>
            <span style="flex:1"></span>
            <span class="meta hide-m">${S.engine === 'auto' ? 'Grok выберет сам' : (ENG[S.engine] + ' · ≈ ' + wsMoney(S.cfg?.prices?.[S.engine]) + (HOSTED() ? ' + Grok' : ''))}</span>
            <button class="send" id="sendBtn" data-act="send" aria-label="Отправить">${ic('send')}</button>
          </div>
        </div>
      </div>
    </div>
    <div class="drop-ov">Отпусти, чтобы прикрепить фото</div>`;
  const inp = $('#inp'); inp.value = draft; autosize(inp);
  if (hadFocus){ inp.focus(); }
  inp.oninput = () => { autosize(inp); ls.set('draft_' + c.id, inp.value); updateSend(); };
  inp.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing){ e.preventDefault(); send(); } };
  renderChips(); renderAtts(); renderJobs(); updateSend();
  const sc = $('.msgs');
  if (nearBottom) sc.scrollTop = sc.scrollHeight; else sc.scrollTop = prevTop;
  bindPendingDnD();
}
function autosize(t){ t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 220) + 'px'; }
function updateSend(){
  const b = $('#sendBtn'); if (!b) return;
  const busy = S.chat?.running || S.chat?.status === 'running';
  b.disabled = busy || (!($('#inp')?.value.trim()) && !S.attach.length);
}

function renderMessages(){
  const c = S.chat;
  const res = {}; c.messages.forEach(m => { if (m.role === 'tool') res[m.tool_call_id] = m; });
  const lastA = [...c.messages].reverse().find(m => m.role === 'assistant');
  const visible = c.messages.filter(m => !m.hidden && m.role !== 'tool');
  if (!visible.length) return emptyChat();
  const out = [];
  for (const m of visible){
    if (m.role === 'user'){
      const imgs = (m.images || []).filter(i => c.images[i]);
      const vids = (m.videos || []).filter(v => c.videos?.[v]);
      out.push(`<div class="msg mu">
        ${vids.map(v => vplayer(v)).join('')}
        ${imgs.length ? `<div class="uimgs ${imgs.length === 1 ? 'one' : ''}">${imgs.map((i, k) => `<div class="uimg" data-act="lb" data-id="${i}"><img src="${thUrl(i)}" alt="" loading="lazy">${imgs.length > 1 ? `<span class="inp-n">${k + 1}</span>` : ''}</div>`).join('')}</div>` : ''}
        ${m.text ? `<div class="bubble">${esc(m.text)}</div>` : ''}
        ${m.engine && m.engine !== 'auto' ? `<span class="meta">движок: ${ENG[m.engine]}</span>` : ''}
        <div class="acts">
          <button class="ib" data-act="copy" data-mid="${m.id}" title="Копировать" aria-label="Копировать">${ic('copy')}</button>
          <button class="ib" data-act="rollback" data-mid="${m.id}" title="Откатить чат до этого сообщения и ответить заново" aria-label="Откатить">${ic('rollback')}</button>
          <button class="ib" data-act="delmsg" data-mid="${m.id}" title="Удалить сообщение" aria-label="Удалить">${ic('trash')}</button>
        </div></div>`);
    } else if (m.role === 'assistant'){
      const parts = [];
      if (m.text) parts.push(`<div class="md">${md(m.text)}</div>`);
      const calls = m.tool_calls || [];
      const isPending = c.pending && m === c.messages.at(-1);
      const genIdx = [];
      calls.forEach((tc, idx) => {
        let a = {}; try { a = JSON.parse(tc.function.arguments || '{}'); } catch(e){}
        const r = res[tc.id]; const nm = tc.function.name;
        if (isPending) { if (nm === 'generate_image') genIdx.push(idx); return; }
        parts.push(renderTool(nm, a, r, tc));
      });
      if (isPending) parts.push(renderConfirm());
      if (m === lastA && !isPending && !(c.running)){
        // ничего
      }
      out.push(`<div class="msg ma"><div class="gav" aria-hidden="true">G</div><div class="ma-body">${parts.join('')}
        <div class="acts">
          ${m.text ? `<button class="ib" data-act="copy" data-mid="${m.id}" title="Копировать текст" aria-label="Копировать">${ic('copy')}</button>` : ''}
          ${m === lastA && !c.running ? `<button class="ib" data-act="regen" title="Перегенерировать ответ" aria-label="Перегенерировать">${ic('regen')}</button>` : ''}
          <button class="ib" data-act="delmsg" data-mid="${m.id}" title="Удалить сообщение" aria-label="Удалить">${ic('trash')}</button>
        </div></div></div>`);
    } else if (m.role === 'error'){
      const lim = m.code === 'limit_exceeded';
      out.push(`<div class="msg err"><span class="st-i e">${ic('warn')}</span><div class="t"><b>${lim ? 'Лимит трат' : 'Ошибка'}</b>${esc(friendlyErr(m.text))}</div>
        ${lim ? `<button class="btn sm" data-act="settings">Лимиты</button>` : `<button class="btn sm" data-act="retry">${ic('regen')}Повторить</button>`}</div>`);
    }
  }
  if (c.running && !c.jobs?.length && !c.pending){
    out.push(`<div class="msg ma"><div class="gav">G</div><div class="ma-body"><div class="res-h"><span class="spin"></span>${esc(c.status_text || 'Grok думает…')}</div></div></div>`);
  }
  return out.join('');
}
function friendlyErr(t){
  t = String(t || '');
  if (/HTTP 401|Incorrect API key|invalid.*key/i.test(t)) return 'Неверный ключ API. Проверь ключи в настройках.\n\n' + t;
  if (/HTTP 429/.test(t)) return 'Слишком много запросов — подожди минуту и нажми «Повторить».\n\n' + t;
  if (/insufficient|balance/i.test(t)) return 'Похоже, закончился баланс.\n\n' + t;
  return t;
}
function emptyChat(){
  const c = S.chat; const has = c.persona.faces.length;
  if (has) return `<div class="empty"><div style="display:flex;gap:6px">${c.persona.faces.slice(0, 3).map(i => `<img src="${thUrl(i)}" style="width:64px;height:80px;object-fit:cover;border-radius:10px" alt="">`).join('')}</div>
    <h2>${esc(c.name)} готова</h2><p>${c.persona.faces.length} портрета · ${c.persona.body.length} ракурсов тела${c.persona.card ? ' · карточка' : ''}. Кинь фото для замены или опиши кадр.</p></div>`;
  return `<div class="empty"><div class="plus">${ic('face')}</div><h2>Шаг 1 из 3 · загрузи 2–3 фото лиц</h2>
    <p>Фото лица своей модели — Grok сделает эталоны. Разные девушки — смешает черты в новое лицо: анфас, 3/4, профиль. Потом предложит тело и запишет карточку.</p>
    <div class="steps3"><span class="on">● Лицо</span><span>○ Тело</span><span>○ Карточка</span></div>
    <div style="display:flex;gap:8px"><button class="btn p" data-act="attach">${ic('upload')}Выбрать файлы</button>${HOSTED() ? '' : `<button class="btn" data-act="importPrompt">${ic('folder')}Импорт папки</button>`}</div></div>`;
}
function renderTool(nm, a, r, tc){
  const c = S.chat;
  const failed = r && r.text.startsWith('ОШИБКА');
  const flagged = failed && /flag|moderat|content|policy|safety|sensitive/i.test(r.text);
  const running = !r && c.jobs?.some(j => j.id === tc.id && j.state === 'running');
  const dt = r?.dt ? mmss(r.dt) : '';
  if (nm === 'review'){
    return `<div class="review"><span class="lbl">Проверка Grok${(a.video_ids || []).length ? ' · видео ' + a.video_ids.map(esc).join(', ') : ''}</span>
      <div style="display:flex;flex-direction:column;gap:5px">
        ${(a.ok || []).map(t => `<div class="li"><i style="color:var(--ok)">✓</i>${esc(t)}</div>`).join('')}
        ${(a.issues || []).map(t => `<div class="li"><i style="color:var(--danger)">✕</i>${esc(t)}</div>`).join('')}</div>
      ${(a.suggestions || []).length ? `<div class="chips">${a.suggestions.map(s => `<button class="chip" data-act="chip" data-v="${esc(s)}">${esc(s)}</button>`).join('')}</div>` : ''}</div>`;
  }
  if (nm === 'add_reference' || nm === 'remove_reference'){
    const cat = a.category ? ({faces: 'Лицо', body: 'Тело'}[a.category] || a.category) : '';
    const ids = (a.image_ids || []).filter(i => c.images[i]);
    return `<div class="res-h"><span class="st-i ${r && r.text.startsWith('ОШИБКА') ? 'e' : 'ok'}">${ic(r && r.text.startsWith('ОШИБКА') ? 'warn' : 'check')}</span><b>${nm === 'add_reference' ? 'В модель' : 'Убрано из модели'} · ${esc(cat)}</b>
      ${ids.map(i => `<img src="${thUrl(i)}" data-act="lb" data-id="${i}" alt="" style="width:28px;height:34px;object-fit:cover;border-radius:6px;cursor:zoom-in">`).join('')}
      ${a.note ? `<span>${esc(a.note)}</span>` : ''}</div>`;
  }
  if (nm === 'set_persona'){
    return `<div class="res-h"><span class="st-i ok">${ic('check')}</span><b>Модель сохранена</b>${r ? `<span>${esc(r.text.replace('Модель сохранена: ', ''))}</span>` : ''}</div>`;
  }
  if (nm === 'edit_video'){
    const lab = `Seedance 2.5 · ${a.resolution || '480p'}${a.label ? ' · ' + esc(a.label) : ''}`;
    if (running || (!r && c.running)){
      const j = c.jobs?.find(x => x.id === tc.id);
      return `<div style="display:flex;flex-direction:column;gap:8px"><div class="res-h"><span class="spin"></span><b>${lab}</b><span class="tmr" data-job="${tc.id}"></span><span class="meta">обычно 3–8 мин${j?.ws_id ? ' · задача ' + esc(j.ws_id.slice(0, 8)) : ''}</span></div>
        <div class="vbox shim" style="aspect-ratio:9/16;max-width:260px"></div></div>`;
    }
    if (!r) return `<div class="res-h"><span class="st-i q"></span><b>${lab}</b><span>не запущено</span></div>`;
    const det = `<div class="step-body col">${a.video_id && c.videos?.[a.video_id] ? `<div class="meta">Основа: ${esc(a.video_id)} (${VSRC[c.videos[a.video_id].source] || ''}) · звук: ${a.generate_audio ? 'новый' : 'исходный'}</div>` : ''}${inputsRow(a.image_ids, a.image_roles, '@image')}${promptBlock(a)}</div>`;
    if (failed){
      return `<details class="step" ${flagged ? 'open' : ''}><summary><span class="st-i ${flagged ? 'w' : 'e'}">${ic('warn')}</span><span style="flex:1">${lab} — ${flagged ? 'отказ фильтра' : 'ошибка'}</span><span class="meta">${dt}</span>${ic('chevR', 'chev')}</summary>
        <div class="step-body col"><div>${esc(r.text.replace('ОШИБКА: ', ''))}</div></div>${det}</details>`;
    }
    const vids = r.videos || [];
    return `<div style="display:flex;flex-direction:column;gap:8px">
      <details class="step"><summary><span class="st-i ok">${ic('check')}</span><span style="flex:1"><b style="font-weight:500">${lab}</b></span><span class="meta">${dt}${r.cost ? ` · <span class="cost">${wsMoney(r.cost)}</span>` : ''}</span>${ic('chevR', 'chev')}</summary>${det}</details>
      ${vids.length ? vids.map(v => vplayer(v)).join('') : `<span class="meta">${esc(r.text)}</span>`}</div>`;
  }
  if (nm === 'lineart_video' || nm === 'trim_video'){
    const name = nm === 'lineart_video' ? 'Силуэт видео' : `Обрезка видео ${a.start ?? ''}–${a.end ?? ''} с`;
    if (!r) return `<div class="res-h">${c.running ? '<span class="spin"></span>' : '<span class="st-i q"></span>'}<b>${esc(name)}</b><span class="tmr" data-job="${tc.id}"></span>${c.jobs?.find(x => x.id === tc.id)?.progress ? `<span class="meta">${esc(c.jobs.find(x => x.id === tc.id).progress)}</span>` : ''}</div>`;
    return `<details class="step" ${failed ? 'open' : ''}><summary><span class="st-i ${failed ? 'e' : 'ok'}">${ic(failed ? 'warn' : 'check')}</span><span style="flex:1">${esc(name)}</span><span class="meta">локально · ${dt || '—'} · бесплатно</span>${ic('chevR', 'chev')}</summary>
      <div class="step-body col">${failed ? `<div class="step-prompt">${esc(r.text)}</div>` : (r.videos || []).map(v => vplayer(v, {small: true})).join('')}</div></details>`;
  }
  if (nm === 'generate_image'){
    const eng = ENG[a.engine] || a.engine;
    if (running || (!r && c.running)){
      return `<div style="display:flex;flex-direction:column;gap:8px"><div class="res-h"><span class="spin"></span><b>${esc(eng)}${a.label ? ' · ' + esc(a.label) : ''}</b><span class="tmr" data-job="${tc.id}"></span></div>
        <div class="rgrid n1"><div class="gi shim"></div></div></div>`;
    }
    if (failed){
      return `<details class="step" ${flagged ? 'open' : ''}><summary><span class="st-i ${flagged ? 'w' : 'e'}">${ic('warn')}</span><span style="flex:1">${esc(eng)} — ${flagged ? 'отказ фильтра' : 'ошибка'}${a.label ? ' · ' + esc(a.label) : ''}</span><span class="meta">${dt}${flagged ? ' · деньги не списаны' : ''}</span>${ic('chevR', 'chev')}</summary>
        <div class="step-body col"><div>${esc(r.text.replace('ОШИБКА: ', ''))}</div>${promptBlock(a)}</div></details>`;
    }
    if (!r) return `<div class="res-h"><span class="st-i q"></span><b>${esc(eng)}${a.label ? ' · ' + esc(a.label) : ''}</b><span>не запущено</span></div>`;
    const ids = (r.images || []).filter(i => c.images[i]);
    if (!(r.images || []).length) return `<div class="res-h"><span class="st-i q"></span><b>${esc(eng)}${a.label ? ' · ' + esc(a.label) : ''}</b><span>${esc(r.text)}</span></div>`;
    return `<div style="display:flex;flex-direction:column;gap:8px">
      <details class="step"><summary><span class="st-i ok">${ic('check')}</span><span style="flex:1"><b style="font-weight:500">${esc(eng)}</b>${a.label ? ' · ' + esc(a.label) : ''}</span><span class="meta">${dt}${r.cost ? ` · <span class="cost">${wsMoney(r.cost)}</span>` : ''}</span>${ic('chevR', 'chev')}</summary>
        <div class="step-body col">${inputsRow(a.image_ids, a.image_roles)}${promptBlock(a)}</div></details>
      ${ids.length ? `<div class="rgrid ${ids.length === 1 ? 'n1' : ids.length === 2 ? 'n2' : ''}">${ids.map(i => tile(i)).join('')}</div>` : '<span class="meta">картинка удалена</span>'}</div>`;
  }
  // lineart / crop / other
  const OPN = {color_match: 'цвет', matte: 'матовая кожа', grain: 'шум', upscale: 'увеличение', gray_mask: 'маска'};
  const name = {lineart: 'Силуэт (lineart)', video_frames: `Кадры из видео ${(a.times || []).map(t => t + ' с').join(', ')}`, crop: `Обрезка ${a.aspect_ratio || ''}`, postprocess: 'Доводка: ' + (a.ops || []).map(o => OPN[o.op] || o.op).join(', ')}[nm] || nm;
  if (!r) return `<div class="res-h">${c.running ? '<span class="spin"></span>' : '<span class="st-i q"></span>'}<b>${esc(name)}</b><span class="tmr" data-job="${tc.id}"></span></div>`;
  const ids = (r.images || []).filter(i => c.images[i]);
  return `<details class="step" ${failed ? 'open' : ''}><summary><span class="st-i ${failed ? 'e' : 'ok'}">${ic(failed ? 'warn' : 'check')}</span><span style="flex:1">${esc(name)}</span><span class="meta">локально · ${dt || '—'} · бесплатно</span>${ic('chevR', 'chev')}</summary>
    <div class="step-body">${ids.map(i => `<img src="${thUrl(i)}" data-act="lb" data-id="${i}" alt="">`).join('')}<div class="step-prompt">${esc(r.text)}</div></div></details>
    ${!failed && ids.length && (nm === 'crop' || nm === 'postprocess') ? `<div class="rgrid n1">${ids.map(i => tile(i)).join('')}</div>` : ''}`;
}
function inputsRow(ids = [], roles = [], pre = '图'){
  const c = S.chat;
  if (!ids?.length) return '';
  return `<div class="inputs">${ids.map((i, k) => `<div class="inp" style="cursor:default"><div class="th">${c.images[i] ? `<img src="${thUrl(i)}" data-act="lb" data-id="${i}" alt="" style="cursor:zoom-in">` : '<div style="width:64px;height:80px;border-radius:8px;background:#2a2c31"></div>'}<span class="inp-n">${pre}${k + 1}</span></div><small>${esc(roles?.[k] || refRole(i))}</small></div>`).join('')}</div>`;
}
/* категории эталонов: faces, body + свои (persona.extra) */
function groups(p = S.chat.persona){
  return [{key: 'faces', name: 'Лицо', ids: p.faces, note: p.notes?.faces || '', builtin: true, max: 6},
          {key: 'body', name: 'Тело', ids: p.body, note: p.notes?.body || '', builtin: true, max: 8},
          ...Object.entries(p.extra || {}).map(([k, v]) => ({key: 'x:' + k, name: k, ids: v.ids || [], note: v.note || '', builtin: false, max: 12}))];
}
const gIds = (p, key) => key === 'faces' || key === 'body' ? p[key] : (p.extra?.[key.slice(2)]?.ids || []);
function gPatch(p, changes){
  // changes: {key: ids}; возвращает патч для /persona
  const out = {}; let extra = null;
  for (const [key, ids] of Object.entries(changes)){
    if (key === 'faces' || key === 'body') out[key] = ids;
    else { extra = extra || JSON.parse(JSON.stringify(p.extra || {})); const n = key.slice(2); extra[n] = {...(extra[n] || {note: ''}), ids}; }
  }
  if (extra) out.extra = extra;
  return out;
}
const allRefs = (p = S.chat.persona) => new Set(groups(p).flatMap(g => g.ids));
function refRole(i){
  const c = S.chat; const r = c.images[i];
  if (c.persona.faces.includes(i)) return 'лицо' + (r?.label ? ' ' + r.label.replace(/^face_?/, '') : '');
  if (c.persona.body.includes(i)) return 'тело';
  const g = groups().find(x => !x.builtin && x.ids.includes(i)); if (g) return g.name.toLowerCase();
  return {lineart: 'силуэт', user: 'исходник', gen: 'кадр', crop: 'кадр', frame: 'кадр видео'}[r?.source] || '';
}
function promptBlock(a){
  return a.prompt ? `<div class="step-prompt" style="max-height:none">${esc(a.prompt)}</div>` : '';
}
function tile(i, opts = {}){
  const r = S.chat.images[i]; if (!r) return '';
  const sel = S.gal.select && opts.gallery;
  return `<div class="gi ${sel && S.gal.sel.has(i) ? 'sel' : ''}" data-tile="${i}">
    <img src="${thUrl(i)}" alt="${esc(r.label || '')}" loading="lazy" data-act="${sel ? 'gsel' : 'lb'}" data-id="${i}">
    ${sel ? `<span class="sel-box">${S.gal.sel.has(i) ? ic('check', '', 'width:12px;height:12px;stroke-width:2.6') : ''}</span>` : ''}
    ${r.fav ? `<span class="favd">${ic('star', '', 'width:14px;height:14px;fill:var(--wait);stroke:var(--wait)')}</span>` : ''}
    ${opts.gallery && (r.label || r.engine) ? `<div class="cap">${r.source === 'ref' || allRefs().has(i) ? '<span class="badge">эталон</span>' : ''}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.label || ENG[r.engine] || '')}</span></div>` : ''}
    ${sel ? '' : `<div class="tp">
      <button class="gb i ${r.fav ? 'fav' : ''}" data-act="fav" data-id="${i}" title="В избранное" aria-label="В избранное">${ic('star')}</button>
      <a class="gb i" href="${imgUrl(i)}" download="${esc(S.chat.name)}_${i}.${r.file.split('.').pop()}" title="Скачать" aria-label="Скачать">${ic('download')}</a>
      <button class="gb i" data-act="lb" data-id="${i}" title="Увеличить" aria-label="Увеличить">${ic('expand')}</button></div>
    <div class="bt">
      <button class="gb i" data-act="toface" data-id="${i}" title="В эталоны лица" aria-label="В эталоны лица">${ic('face')}</button>
      <button class="gb i" data-act="tobody" data-id="${i}" title="В эталоны тела" aria-label="В эталоны тела">${ic('body')}</button>
      <button class="gb i" data-act="attachimg" data-id="${i}" title="Прикрепить к сообщению" aria-label="Прикрепить">${ic('clip')}</button>
      <span style="flex:1"></span>
      <button class="gb" data-act="variations" data-id="${i}" title="Сделать вариации">Вариации</button>
      <button class="gb" data-act="editimg" data-id="${i}" title="Локальная правка">Правка</button></div>`}
  </div>`;
}

/* confirm card */
function renderConfirm(){
  const c = S.chat, p = c.pending; if (!p) return '';
  const jobs = p.jobs; const sel = Math.min(S.jobSel, jobs.length - 1); const j = jobs[sel];
  const lim = S.cfg?.limits || {};
  const over = (lim.per_message && p.cost > lim.per_message) || (lim.per_day && (S.spend?.today || 0) + p.cost > lim.per_day);
  const vj = j.kind === 'video';
  const lang = j.engine === 'seedream' || vj ? '中文' : 'EN';
  const pre = vj ? '@image' : (j.engine === 'seedream' ? '图' : 'img');
  return `<section class="confirm" aria-label="Подтверждение генерации">
    <div class="confirm-h"><span class="pill s-wait">Ждёт подтверждения</span>${p.edited ? '<span class="pill s-wait" style="opacity:.8">изменено</span>' : ''}<span style="flex:1"></span>
      ${vj ? `<span class="meta">Seedance 2.5 Video Edit</span><div class="seg">${['480p', '720p', '1080p'].map(k => `<button class="${j.resolution === k ? 'on' : ''}" data-act="pres" data-v="${k}">${k}</button>`).join('')}</div>`
        : `<div class="seg">${Object.entries(ENG).map(([k, v]) => `<button class="${j.engine === k ? 'on' : ''}" data-act="penv" data-v="${k}">${v}</button>`).join('')}</div>`}</div>
    <div class="confirm-b">
      ${jobs.length > 1 ? `<div class="chips">${jobs.map((x, k) => `<button class="chip ${k === sel ? 'on' : ''}" data-act="pjob" data-v="${k}">${k + 1} · ${esc(x.label || (ENG[x.engine] || x.engine))}</button>`).join('')}</div>` : (j.label ? `<b style="font-weight:600">${esc(j.label)}</b>` : '')}
      ${vj ? `<div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap">${vplayer(j.video, {small: true})}
        <div style="display:flex;flex-direction:column;gap:8px;min-width:180px"><span class="lbl">Видео-основа</span>
          <span class="meta">${esc(j.video)} · ${c.videos?.[j.video] ? (VSRC[c.videos[j.video].source] || '') + ' · ' + c.videos[j.video].dur + ' с' : ''}</span>
          <label class="sr" for="pvid">Видео-основа</label><select id="pvid" class="field" style="height:30px">${Object.entries(c.videos || {}).filter(([, r]) => r.source !== 'gen').map(([k, r]) => `<option value="${k}" ${k === j.video ? 'selected' : ''}>${k} · ${VSRC[r.source] || r.source} · ${r.dur} с</option>`).join('')}</select>
          <div class="row-sb" style="gap:10px"><span>Звук</span><div class="seg"><button class="${!j.audio ? 'on' : ''}" data-act="paudio" data-v="0">исходный</button><button class="${j.audio ? 'on' : ''}" data-act="paudio" data-v="1">новый</button></div></div>
          <span class="meta">Цена = (сек входа + выхода) × цена ${esc(j.resolution)}</span></div></div>` : ''}
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;align-items:center;gap:8px"><span class="lbl">${vj ? 'Референсы' : 'Входы'} — порядок важен</span><span class="meta">перетащи, чтобы поменять</span></div>
        <div class="inputs" id="pinputs">${(j.inputs || []).map((i, k) => `<div class="inp" draggable="true" data-k="${k}"><div class="th">${c.images[i] ? `<img src="${thUrl(i)}" alt="" draggable="false">` : ''}<span class="inp-n">${pre}${k + 1}</span><button class="x" data-act="pinrm" data-v="${k}" aria-label="Убрать вход">${ic('x', '', 'width:11px;height:11px')}</button></div><small>${esc(j.roles?.[k] || refRole(i))}</small></div>`).join('')}
          <button class="addt" style="width:64px;height:80px;aspect-ratio:auto" data-act="pinpick" title="Добавить вход: эталон, картинка из чата или файл">${ic('plus')}вход</button></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;align-items:center;gap:8px"><span class="lbl">Промпт · ${lang}</span>${!vj && j.mode && j.mode !== 'free' ? (j.manual ? `<span class="meta">вручную</span><button class="btn g sm" data-act="prebuild" title="Собрать заново по рецепту под текущие входы">Пересобрать</button>` : `<span class="meta" title="Обновляется сам при смене входов и движка">по рецепту</span>`) : ''}<span style="flex:1"></span>
          <button class="btn g sm" data-act="ptoggle">${S.promptOpen ? 'Свернуть' : 'Показать и править'}${ic('chevD', '', S.promptOpen ? 'transform:rotate(180deg)' : '')}</button></div>
        ${S.promptOpen ? `<label class="sr" for="pr">Промпт</label><textarea id="pr" class="ta mono" style="min-height:160px;font-size:12.5px">${esc(j.prompt)}</textarea><span class="meta">Изменения сохраняются, когда уходишь из поля</span>` : `<div class="clamp">${esc(j.prompt)}</div>`}
      </div>
    </div>
    <div class="confirm-f">
      <button class="btn p" data-act="approve">${ic('play', '', 'fill:currentColor;stroke:none;width:12px;height:12px')}Запустить · ${wsMoney(p.cost)}</button>
      <button class="btn g" data-act="reject">Отмена</button>
      <span style="flex:1"></span>
      <button class="btn g sm" data-act="approveAuto" title="Больше не спрашивать подтверждение">Запускать без подтверждения дальше</button>
    </div>
    ${over ? `<div style="padding:0 16px 12px" class="meta"><span style="color:var(--wait)">Превышает лимит трат</span> — запуск будет отклонён. Поменяй лимит в настройках.</div>` : ''}
  </section>`;
}
function bindPendingDnD(){
  const box = $('#pinputs'); if (!box) return;
  let from = null;
  box.querySelectorAll('.inp').forEach(el => {
    el.ondragstart = e => { from = +el.dataset.k; el.classList.add('drag'); e.dataTransfer.effectAllowed = 'move'; };
    el.ondragend = () => el.classList.remove('drag');
    el.ondragover = e => { e.preventDefault(); el.classList.add('over'); };
    el.ondragleave = () => el.classList.remove('over');
    el.ondrop = e => { e.preventDefault(); el.classList.remove('over'); const to = +el.dataset.k; if (from === null || from === to) return;
      const j = curJob(); const arr = [...j.inputs]; const [x] = arr.splice(from, 1); arr.splice(to, 0, x); patchJob({inputs: arr}); };
  });
  const pr = $('#pr');
  if (pr) pr.onchange = () => patchJob({prompt: pr.value});
  const pv = $('#pvid');
  if (pv) pv.onchange = () => patchJob({video: pv.value});
}
const curJob = () => S.chat.pending.jobs[Math.min(S.jobSel, S.chat.pending.jobs.length - 1)];
async function patchJob(ch){
  const j = curJob();
  try { S.chat = await post(`/api/chats/${S.cur}/pending`, {jobs: [{i: j.i, ...ch}]}, 'PATCH'); S.lastSig = ''; render(); }
  catch(e){ toast(e.message); }
}

/* chips + attachments + jobs */
function renderChips(){
  const c = S.chat; const has = c.persona.faces.length;
  const lastImg = Object.entries(c.images).filter(([, r]) => r.source === 'gen' || r.source === 'crop').sort((a, b) => b[1].t - a[1].t)[0];
  const chips = !has ? ['Создай новую девушку по этим фото', 'Это фото лица моей модели — сделай эталоны', 'Предложи тело']
    : !c.persona.body.length ? ['Предложи тело', 'Сделай эталоны тела в 5 ракурсах', 'Заполни карточку RU/EN/中文']
    : ['Сделай фото, где она ', 'Замени девушку на фото на неё', 'Замени девушку в видео на неё', 'Карусель 4', 'Это эталон ног — сохрани в модель', 'Локальная правка: '];
  $('#chips').innerHTML = chips.map(t => `<button class="chip" data-act="chip" data-v="${esc(t)}">${esc(t)}</button>`).join('');
}
function renderAtts(){
  const el = $('#atts'); if (!el) return;
  el.hidden = !S.attach.length;
  el.innerHTML = S.attach.map((a, k) => `<div class="att" draggable="true" data-k="${k}"><img src="${a.url}" alt="" draggable="false">${a.kind === 'video' ? `<span class="vbadge">${ic('play', '', 'fill:currentColor;stroke:none;width:9px;height:9px')}${S.chat.videos?.[a.id]?.dur ?? ''} с</span>` : `<span class="inp-n">${k + 1}</span>`}<button class="x" data-act="unattach" data-v="${k}" aria-label="Убрать">${ic('x', '', 'width:11px;height:11px')}</button></div>`).join('')
    + (S.attach.length > 1 ? '<span class="meta" style="align-self:center">перетащи, чтобы поменять порядок</span>' : '');
  let from = null;
  el.querySelectorAll('.att').forEach(a => {
    a.ondragstart = e => { from = +a.dataset.k; a.classList.add('drag'); e.dataTransfer.setData('text/x-att', '1'); };
    a.ondragend = () => a.classList.remove('drag');
    a.ondragover = e => { e.preventDefault(); a.classList.add('over'); };
    a.ondragleave = () => a.classList.remove('over');
    a.ondrop = e => { e.preventDefault(); e.stopPropagation(); a.classList.remove('over'); const to = +a.dataset.k; if (from === null) return;
      const [x] = S.attach.splice(from, 1); S.attach.splice(to, 0, x); renderAtts(); };
  });
  updateSend();
}
function renderJobs(){
  const el = $('#jobs'); if (!el || !S.chat) return;
  const c = S.chat; const jobs = c.jobs || [];
  const busy = c.running || c.status === 'running';
  if (!busy){ el.innerHTML = ''; return; }
  const now = Date.now() / 1000;
  const run = jobs.filter(j => j.state === 'running');
  const sum = run.reduce((s, j) => s + (j.cost || 0), 0);
  el.innerHTML = `<div class="jobs-in">
    ${jobs.length ? jobs.map(j => `<div class="job">${j.state === 'running' ? '<span class="spin"></span>' : j.state === 'done' ? `<span class="st-i ok">${ic('check')}</span>` : `<span class="st-i e">${ic('warn')}</span>`}
      <span class="t">${j.engine ? `<b style="font-weight:500">${ENGX[j.engine]}</b> · ` : ''}${esc(j.label || j.name)}${j.progress ? ` <span class="meta">${esc(j.progress)}</span>` : ''}</span>
      <span class="tm">${mmss((j.ended || now) - j.started)}</span></div>`).join('')
      : `<div class="job"><span class="spin"></span><span class="t">${esc(c.status_text || 'Grok думает…')}</span><span class="tm" id="thinkT"></span></div>`}
    <div class="job" style="border-top:1px solid var(--line);margin-top:4px;padding-top:6px">
      <button class="btn sm" data-act="stop">${ic('stop')}Стоп</button>
      ${sum ? `<span class="meta"><span class="cost">${wsMoney(sum)}</span> в работе</span>` : ''}<span style="flex:1"></span>
      <span class="meta">Можно переключиться на другую модель — работа продолжится</span></div></div>`;
}
let thinkStart = null;
setInterval(() => {
  if (!S.chat) return;
  const busy = S.chat.running || S.chat.status === 'running';
  if (busy && S.view === 'chat'){
    if (!thinkStart) thinkStart = Date.now();
    renderJobs();
    const t = $('#thinkT'); if (t) t.textContent = mmss((Date.now() - thinkStart) / 1000);
    $$('.tmr').forEach(el => { const j = S.chat.jobs?.find(x => x.id === el.dataset.job); if (j) el.textContent = mmss(Date.now() / 1000 - j.started); });
  } else thinkStart = null;
}, 1000);

/* ---------- panel ---------- */
let cardSaveT = null;
function renderPanel(){
  const el = $('#panel');
  if (!S.chat || S.view !== 'chat'){ el.innerHTML = ''; return; }
  const c = S.chat, p = c.persona;
  if (document.activeElement && el.contains(document.activeElement) && ['TEXTAREA', 'INPUT'].includes(document.activeElement.tagName)) return; // не мешать вводу
  const gens = Object.values(c.images).filter(r => r.source === 'gen');
  const last = gens.sort((a, b) => b.t - a.t)[0];
  const refGrid = g => {
    const k = esc(g.key); const ids = g.ids.filter(i => c.images[i]);
    const def = n => g.key === 'faces' ? ['анфас', '3/4', 'профиль'][n] || 'ракурс' : g.key === 'body' ? ['анфас', '3/4', 'бок', 'спина', 'спина 3/4'][n] || 'ракурс' : '';
    return `<div class="refs" data-group="${k}">${ids.map((i, n) => `<div class="ref" draggable="true" data-group="${k}" data-id="${i}">
      <img src="${thUrl(i)}" alt="" draggable="false" data-act="lb" data-id="${i}">${n === 0 ? `<span class="main-star" title="Главный эталон">${ic('star')}</span>` : ''}
      <button class="x" data-act="unref" data-group="${k}" data-id="${i}" aria-label="Убрать из эталонов">${ic('x', '', 'width:12px;height:12px')}</button>
      <div class="cap" data-act="relabel" data-id="${i}" title="Подпись ракурса — нажми, чтобы изменить">${esc(c.images[i].label || def(n) || 'подпись')}</div></div>`).join('')}
      ${ids.length < g.max ? `<button class="addt" data-act="refadd" data-group="${k}">${ic('plus')}фото</button>` : ''}</div>`;
  };
  const sec = g => `<div><div class="sec-h"><h3>${g.builtin ? 'Эталоны ' + (g.key === 'faces' ? 'лица' : 'тела') : esc(g.name)}</h3>
      <div style="display:flex;align-items:center;gap:2px"><span class="meta">${g.ids.length}${g.builtin ? ' из ' + (g.key === 'faces' ? 4 : 5) : ''}</span>
      <button class="ib" style="width:26px;height:26px" data-act="catnote" data-group="${esc(g.key)}" title="Описание категории для Grok">${ic('edit', '', 'width:13px;height:13px')}</button>
      ${g.builtin ? '' : `<button class="ib" style="width:26px;height:26px" data-act="delcat" data-group="${esc(g.key)}" title="Удалить категорию">${ic('trash', '', 'width:13px;height:13px')}</button>`}</div></div>
      ${refGrid(g)}${g.note ? `<div class="hint" style="margin-top:6px">${esc(g.note)}</div>` : ''}</div>`;
  const tabs = {card: 'RU', card_en: 'EN', card_zh: '中文'};
  el.innerHTML = `
    <div class="pn scroll">
      <div><div class="row-sb" style="margin-bottom:6px"><span class="lbl">Модель</span><button class="ib" data-act="panel" aria-label="Скрыть панель">${ic('chevR')}</button></div>
        <label class="sr" for="pname">Имя модели</label><input class="pn-name" id="pname" value="${esc(c.name)}"></div>
      <div class="stats">
        <div class="stat"><small>Кадров</small><b>${gens.length}</b></div>
        <div class="stat"><small>Потрачено</small><b class="cost">${money(c.spent)}</b></div>
        <div class="stat"><small>Последняя</small><b>${last ? when(last.t) : '—'}</b></div></div>
      ${groups(p).map(sec).join('')}
      <div><button class="btn sm w" data-act="newcat">${ic('plus')}Категория эталонов</button>
        <div class="hint">Ноги, руки, тату, образ… Можно и в чате: «это эталон ног — сохрани». Перетаскивай фото — порядок и перенос между категориями, первый — главный.</div></div>
      <div><div class="sec-h"><h3>Карточка внешности</h3><span class="pill s-ok" id="cardState" style="opacity:0">сохранено</span></div>
        <div class="tabs">${Object.entries(tabs).map(([k, v]) => `<button class="${S.cardTab === k ? 'on' : ''}" data-act="cardtab" data-v="${k}">${v}</button>`).join('')}</div>
        <label class="sr" for="cardTa">Карточка</label>
        <textarea class="card-ta" id="cardTa" placeholder="${{card: 'Внешность по-русски — Grok заполнит сам после создания', card_en: 'Identity paragraph for GPT Image (English)', card_zh: '人物身份 — 给 Seedream 的中文描述'}[S.cardTab]}">${esc(p[S.cardTab] || '')}</textarea></div>
    </div>
    ${HOSTED() ? '' : `<div class="pn-foot"><button class="btn sm" data-act="export">${ic('folder')}Экспорт в папку</button><button class="btn g sm" data-act="importPrompt">${ic('upload')}Импорт</button></div>`}`;
  const nm = $('#pname');
  nm.onchange = async () => { if (nm.value.trim()){ await post(`/api/chats/${S.cur}/persona`, {name: nm.value.trim()}); await loadChats(); loadChat(S.cur, true); } };
  nm.onkeydown = e => { if (e.key === 'Enter') nm.blur(); };
  const ta = $('#cardTa');
  ta.oninput = () => { clearTimeout(cardSaveT); const st = $('#cardState'); st.textContent = 'сохраняю…'; st.className = 'pill s-wait'; st.style.opacity = 1;
    cardSaveT = setTimeout(async () => { await post(`/api/chats/${S.cur}/persona`, {[S.cardTab]: ta.value}); S.chat.persona[S.cardTab] = ta.value; st.textContent = 'сохранено'; st.className = 'pill s-ok'; }, 700); };
  bindRefDnD();
}
function bindRefDnD(){
  let drag = null;
  $$('#panel .ref').forEach(el => {
    el.ondragstart = e => { drag = {group: el.dataset.group, id: el.dataset.id}; el.classList.add('drag'); e.dataTransfer.setData('text/x-ref', el.dataset.id); };
    el.ondragend = () => el.classList.remove('drag');
    el.ondragover = e => { e.preventDefault(); el.classList.add('over'); };
    el.ondragleave = () => el.classList.remove('over');
    el.ondrop = e => { e.preventDefault(); e.stopPropagation(); el.classList.remove('over'); if (drag) moveRef(drag, el.dataset.group, el.dataset.id); drag = null; };
  });
  $$('#panel .refs').forEach(g => {
    g.ondragover = e => { e.preventDefault(); g.classList.add('over'); };
    g.ondragleave = () => g.classList.remove('over');
    g.ondrop = async e => {
      e.preventDefault(); g.classList.remove('over');
      if (drag){ moveRef(drag, g.dataset.group, null); drag = null; return; }
      const files = [...(e.dataTransfer.files || [])].filter(f => f.type.startsWith('image/'));
      if (files.length) addRefsFromFiles(files, g.dataset.group);
    };
  });
}
async function moveRef(drag, toGroup, beforeId){
  const p = S.chat.persona;
  const ch = {};
  if (drag.group !== toGroup) ch[drag.group] = gIds(p, drag.group).filter(i => i !== drag.id);
  const arr = gIds(p, toGroup).filter(i => i !== drag.id);
  const at = beforeId ? arr.indexOf(beforeId) : -1;
  if (at >= 0) arr.splice(at, 0, drag.id); else arr.push(drag.id);
  ch[toGroup] = arr;
  await setPersona(gPatch(p, ch));
}
async function setPersona(patch){
  S.chat = await post(`/api/chats/${S.cur}/persona`, patch); S.lastSig = ''; render(); loadChats();
}
async function addRefsFromFiles(files, group){
  const ids = [];
  for (const f of files){ const r = await uploadFile(f); if (r) ids.push(r.id); }
  if (!ids.length) return;
  S.chat = await api('/api/chats/' + S.cur);
  await setPersona(gPatch(S.chat.persona, {[group]: [...gIds(S.chat.persona, group), ...ids]}));
  toast(`Добавлено в «${groups().find(g => g.key === group)?.name || group}»: ${ids.length}`);
}

/* ---------- gallery ---------- */
function galItems(){
  const c = S.chat; const g = S.gal;
  const refs = allRefs(c.persona);
  let items = Object.entries(c.images).map(([id, r]) => ({id, ...r}));
  const f = {
    all: r => r.source !== 'frame', gen: r => ['gen', 'crop', 'post'].includes(r.source), user: r => r.source === 'user',
    frames: r => r.source === 'frame',
    lineart: r => r.source === 'lineart', fav: r => r.fav, refs: r => refs.has(r.id) || r.source === 'ref',
  };
  const counts = Object.fromEntries(Object.entries(f).map(([k, fn]) => [k, items.filter(fn).length]));
  counts.video = Object.keys(c.videos || {}).length;
  items = items.filter(f[g.filter] || f.all);
  if (g.engine !== 'all') items = items.filter(r => r.engine === g.engine);
  items.sort((a, b) => g.order === 'new' ? b.t - a.t : a.t - b.t);
  return {items, counts};
}
function renderGallery(){
  const c = S.chat; const g = S.gal;
  const {items, counts} = galItems();
  const F = {all: 'Все', gen: 'Результаты', user: 'Мои загрузки', lineart: 'Силуэты', fav: 'Избранное', refs: 'Эталоны', video: 'Видео', frames: 'Кадры видео'};
  const vids = Object.entries(c.videos || {}).sort((a, b) => g.order === 'new' ? b[1].t - a[1].t : a[1].t - b[1].t);
  $('#main').innerHTML = `
    <div class="gal-h">
      <button class="btn g sm" data-act="tochat">${ic('chevL')}К чату</button>
      ${c.persona.faces[0] ? `<img class="av" style="width:32px;height:32px;border-radius:9px" src="${thUrl(c.persona.faces[0])}" alt="">` : ''}
      <div style="display:flex;flex-direction:column"><b style="font-size:15px;font-weight:600">Галерея · ${esc(c.name)}</b><span class="meta">${Object.keys(c.images).length} картинок</span></div>
      <span style="flex:1"></span>
      <div class="seg">${[['all', 'Все движки'], ['gpt', 'GPT'], ['seedream', 'Seedream']].map(([k, v]) => `<button class="${g.engine === k ? 'on' : ''}" data-act="gengine" data-v="${k}">${v}</button>`).join('')}</div>
      <label class="sr" for="gorder">Порядок</label><select id="gorder" class="field" style="width:auto;height:32px"><option value="new" ${g.order === 'new' ? 'selected' : ''}>Сначала новые</option><option value="old" ${g.order === 'old' ? 'selected' : ''}>Сначала старые</option></select>
      <button class="btn sm ${g.select ? 'p' : ''}" data-act="gselect">${ic('select')}${g.select ? 'Готово' : 'Выбрать'}</button>
    </div>
    <div class="gal-f chips-row">${Object.entries(F).map(([k, v]) => `<button class="chip ${g.filter === k ? 'on' : ''}" data-act="gfilter" data-v="${k}">${v} <span class="n">${counts[k]}</span></button>`).join('')}
      ${g.select ? `<span style="flex:1"></span><button class="btn g sm" data-act="gselall">Выбрать все ${items.length}</button>` : ''}</div>
    <div class="gal scroll">${g.filter === 'video' ? (vids.length ? `<div class="ggrid">${vids.map(([v, r]) => `<div class="gi vtile" data-act="vlb" data-id="${v}"><img src="${vThUrl(v)}" alt="" loading="lazy"><span class="vplay">${ic('play', '', 'fill:#fff;stroke:none;width:20px;height:20px')}</span>
        <div class="cap"><span class="badge">${VSRC[r.source] || r.source}</span><span>${r.dur} с${r.label ? ' · ' + esc(r.label) : ''}</span></div></div>`).join('')}</div>` : `<div class="empty"><h2>Видео нет</h2><p>Перетащи ролик в чат — Grok разберёт его и заменит девушку на модель.</p></div>`)
      : items.length ? `<div class="ggrid">${items.map(r => tile(r.id, {gallery: true})).join('')}</div>` : `<div class="empty"><h2>Пусто</h2><p>В этом фильтре картинок нет.</p></div>`}</div>
    ${g.select && g.sel.size ? `<div class="selbar"><b style="font-weight:600">${g.sel.size} выбрано</b>
      <button class="btn sm" data-act="gzip">${ic('download')}Скачать zip</button>
      <button class="btn sm" data-act="gattach">${ic('clip')}В чат</button>
      <button class="btn sm" data-act="gcarousel">Карусель</button>
      <button class="btn sm d" data-act="gdelete">${ic('trash')}Удалить</button></div>` : ''}`;
  $('#gorder').onchange = e => { g.order = e.target.value; renderGallery(); };
}

/* ---------- lightbox ---------- */
let LB = null;
function openLB(id, list){
  const c = S.chat;
  list = list || (S.view === 'gallery' ? galItems().items.map(r => r.id) : Object.entries(c.images).sort((a, b) => a[1].t - b[1].t).map(([i]) => i));
  LB = {id, list, cmp: false}; renderLB();
}
function renderLB(){
  const el = $('#lightbox');
  if (!LB){ el.innerHTML = ''; return; }
  const c = S.chat, r = c.images[LB.id];
  if (!r){ LB = null; el.innerHTML = ''; return; }
  const k = LB.list.indexOf(LB.id);
  const ref = c.persona.faces[0];
  const inFace = c.persona.faces.includes(LB.id), inBody = c.persona.body.includes(LB.id);
  el.innerHTML = `<div class="lb" role="dialog" aria-label="Просмотр">
    <div class="lb-img ${LB.cmp && ref ? 'cmp' : ''}" data-act="lbbg">
      ${LB.cmp && ref ? `<img src="${imgUrl(ref)}" alt="эталон">` : ''}<img src="${imgUrl(LB.id)}" alt="">
      ${k > 0 ? `<button class="lb-nav l" data-act="lbprev" aria-label="Предыдущая">${ic('chevL')}</button>` : ''}
      ${k >= 0 && k < LB.list.length - 1 ? `<button class="lb-nav r" data-act="lbnext" aria-label="Следующая">${ic('chevR')}</button>` : ''}
    </div>
    <div class="lb-side"><div class="in scroll">
      <div class="row-sb"><b style="font-size:15px;font-weight:600">${esc(r.label || ENG[r.engine] || {user: 'Загрузка', lineart: 'Силуэт', ref: 'Эталон'}[r.source] || 'Картинка')}</b><button class="ib" data-act="lbclose" aria-label="Закрыть">${ic('x')}</button></div>
      <div class="kv"><span>Источник</span><span>${{gen: 'генерация', crop: 'обрезка', post: 'доводка', user: 'моя загрузка', lineart: 'силуэт', ref: 'эталон (импорт)'}[r.source] || r.source}</span>
        ${r.engine ? `<span>Движок</span><span>${ENG[r.engine] || r.engine}</span>` : ''}
        <span>Размер</span><span>${r.w}×${r.h}</span><span>Когда</span><span>${new Date(r.t * 1000).toLocaleString('ru', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'})}</span>
        <span>ID</span><span class="mono" style="font-size:11.5px">${LB.id}</span></div>
      <div class="lb-acts">
        <button class="btn sm ${r.fav ? 'p' : ''}" data-act="fav" data-id="${LB.id}">${ic('star')}${r.fav ? 'В избранном' : 'В избранное'}</button>
        <a class="btn sm" href="${imgUrl(LB.id)}" download="${esc(c.name)}_${LB.id}.${r.file.split('.').pop()}">${ic('download')}Скачать</a>
        <button class="btn sm" data-act="toface" data-id="${LB.id}" ${inFace ? 'disabled' : ''}>${ic('face')}${inFace ? 'Это лицо' : 'В лица'}</button>
        <button class="btn sm" data-act="tobody" data-id="${LB.id}" ${inBody ? 'disabled' : ''}>${ic('body')}${inBody ? 'Это тело' : 'В тело'}</button>
        <select class="field" style="height:30px;font-size:12.5px;grid-column:1/-1" data-tocat="1" data-id="${LB.id}" aria-label="Добавить в категорию эталонов">
          <option value="">В категорию эталонов…</option>${groups().filter(g => !g.builtin).map(g => `<option value="${esc(g.key)}">${esc(g.name)}${g.ids.includes(LB.id) ? ' ✓' : ''}</option>`).join('')}<option value="__new">+ Новая категория…</option></select>
        <button class="btn sm" data-act="attachimg" data-id="${LB.id}">${ic('clip')}Прикрепить</button>
        <button class="btn sm ${LB.cmp ? 'p' : ''}" data-act="lbcmp" ${ref && ref !== LB.id ? '' : 'disabled'}>${ic('compare')}С эталоном</button>
        <button class="btn sm" data-act="editimg" data-id="${LB.id}">${ic('edit')}Правка</button>
        <button class="btn sm d" data-act="delimg" data-id="${LB.id}">${ic('trash')}Удалить</button></div>
      ${r.inputs?.length ? `<div><span class="lbl">Входы</span><div class="lb-inputs" style="margin-top:8px">${r.inputs.filter(i => c.images[i]).map((i, n) => `<div style="position:relative"><img src="${thUrl(i)}" data-act="lbgo" data-id="${i}" alt=""><span class="inp-n">图${n + 1}</span></div>`).join('')}</div></div>` : ''}
      ${r.prompt ? `<div><div class="row-sb"><span class="lbl">Промпт</span><button class="btn g sm" data-act="copyprompt">${ic('copy')}Копировать</button></div><div class="step-prompt" style="margin-top:8px;max-height:none">${esc(r.prompt)}</div></div>` : ''}
    </div></div></div>`;
}

/* ---------- settings ---------- */
async function renderSettings(){
  const cfg = S.cfg || await api('/api/config'); S.cfg = cfg;
  if (cfg.hosted) return renderHostedSettings(cfg);
  const sp = S.spend || {};
  if (!S.promptsCache[S.settingsTab]) { try { S.promptsCache[S.settingsTab] = await api('/api/prompts/' + S.settingsTab); } catch(e){ S.promptsCache[S.settingsTab] = {text: '', modified: false}; } }
  const pr = S.promptsCache[S.settingsTab];
  const pct = sp.limit ? Math.min(100, (sp.today || 0) / sp.limit * 100) : 0;
  $('#main').innerHTML = `<div class="set scroll">
    <div class="set-h"><button class="btn g sm" data-act="tochat">${ic('chevL')}К студии</button><b>Настройки</b><span style="flex:1"></span><span class="meta hide-m">Сохраняется в <code class="mono">data/config.json</code> на этом компьютере</span></div>
    <div class="set-wrap">
      <nav class="set-nav"><a href="#s-keys" class="on">Ключи API</a><a href="#s-grok">Grok</a><a href="#s-gen">Генерация и лимиты</a><a href="#s-prompts">Инструкции Grok</a></nav>
      <div class="set-col">
        <section class="scard" id="s-keys"><h3>Ключи API</h3>
          ${keyField('xai', 'xAI · Grok', cfg.xai_key, 'xai-…')}
          ${keyField('wavespeed', 'WaveSpeed', cfg.wavespeed_key, '')}
          <span class="meta">Ключи уходят только в api.x.ai и api.wavespeed.ai.</span></section>
        <section class="scard" id="s-grok"><h3>Grok</h3>
          <label class="lab" for="sModel">Модель для чата
            <select id="sModel" class="field"><option>${esc(cfg.chat_model)}</option></select></label>
          <span class="meta">Список из /api/models · Grok ведёт чат, разбирает фото и пишет промпты, а картинки рисует WaveSpeed.</span></section>
        <section class="scard" id="s-gen"><h3>Генерация и лимиты</h3>
          <div class="row-sb"><div><div>Подтверждать каждую генерацию</div><span class="meta">Карточка с ценой и промптом перед запуском</span></div>
            <button class="toggle ${cfg.autorun ? '' : 'on'}" id="sConfirm" role="switch" aria-checked="${!cfg.autorun}" aria-label="Подтверждать генерацию"></button></div>
          <div class="grid2">
            <label class="lab">Лимит за сообщение<div class="money-in"><span>$</span><input class="field" id="lMsg" type="number" step="0.5" min="0" value="${cfg.limits?.per_message || ''}" placeholder="без лимита"></div></label>
            <label class="lab">Лимит за день<div class="money-in"><span>$</span><input class="field" id="lDay" type="number" step="1" min="0" value="${cfg.limits?.per_day || ''}" placeholder="без лимита"></div></label></div>
          <div><div class="row-sb" style="margin-bottom:6px"><span class="meta">Сегодня потрачено</span><span class="cost">${money(sp.today)}${sp.limit ? ' из ' + money(sp.limit) : ''}</span></div><div class="bar"><i style="width:${pct}%"></i></div></div>
          <span class="lbl" style="margin-top:4px">Цена за кадр — для оценки</span>
          <div class="grid2">
            <label class="lab">GPT Image 2.5<div class="money-in"><span>$</span><input class="field" id="pGpt" type="number" step="0.01" value="${cfg.prices.gpt}"></div></label>
            <label class="lab">Seedream V5.0 Pro<div class="money-in"><span>$</span><input class="field" id="pSd" type="number" step="0.01" value="${cfg.prices.seedream}"></div></label></div>
          <span class="lbl" style="margin-top:4px">Seedance 2.5 видео — цена за секунду (вход + выход)</span>
          <div class="grid2" style="grid-template-columns:repeat(3,1fr)">
            ${[['pV480', '480p', 'seedance_480p'], ['pV720', '720p', 'seedance_720p'], ['pV1080', '1080p', 'seedance_1080p']].map(([i, t, k]) => `<label class="lab">${t}<div class="money-in"><span>$</span><input class="field" id="${i}" type="number" step="0.01" value="${cfg.prices[k] ?? ''}"></div></label>`).join('')}</div>
          <span class="meta">Замена в видео всегда спрашивает подтверждение, даже если подтверждение картинок выключено.</span>
          <div class="row-sb"><span class="meta" id="genState"></span><button class="btn p sm" data-act="saveGen">Сохранить</button></div></section>
      </div>
      <div class="set-col">
        <section class="scard" id="s-prompts" style="flex:1"><h3>Инструкции Grok</h3>
          <div class="tabs"><button class="${S.settingsTab === 'system' ? 'on' : ''}" data-act="ptab" data-v="system">Как работать <small>system.md</small></button><button class="${S.settingsTab === 'rules' ? 'on' : ''}" data-act="ptab" data-v="rules">Мои правила <small>rules.md</small></button></div>
          <label class="sr" for="promptTa">Текст инструкции</label>
          <textarea class="ta prompt-ta" id="promptTa" spellcheck="false">${esc(pr.text)}</textarea>
          <div class="row-sb"><span class="pill ${pr.modified ? 's-wait' : 's-ok'}" id="promptState">${pr.modified ? 'изменён относительно исходного' : 'исходный'}</span>
            <div style="display:flex;gap:8px"><button class="btn g sm" data-act="presetDefault">Сбросить к исходному</button><button class="btn p sm" data-act="psave">Сохранить</button></div></div>
          <span class="meta">Grok перечитывает оба файла на каждый запрос — перезапуск не нужен.</span></section>
      </div>
    </div></div>`;
  $('#sConfirm').onclick = e => e.currentTarget.classList.toggle('on');
  api('/api/models').then(r => { if (!r.models?.length) return; const s = $('#sModel'); if (!s) return;
    s.innerHTML = [...new Set([cfg.chat_model, ...r.models])].map(m => `<option ${m === cfg.chat_model ? 'selected' : ''}>${esc(m)}</option>`).join(''); }).catch(() => {});
  $('#sModel').onchange = async e => { S.cfg = await post('/api/config', {chat_model: e.target.value}); toast('Модель Grok: ' + e.target.value); };
  $('#promptTa').oninput = () => { const st = $('#promptState'); st.textContent = 'не сохранено'; st.className = 'pill s-wait'; };
  $$('.set-nav a').forEach(a => a.onclick = e => { e.preventDefault(); $$('.set-nav a').forEach(x => x.classList.remove('on')); a.classList.add('on'); $(a.getAttribute('href')).scrollIntoView({behavior: 'smooth', block: 'start'}); });
}
function renderHostedSettings(cfg){
  const own = cfg.ws_mode !== 'platform';
  const row = (t, v) => `<div class="row-sb"><span>${t}</span><span class="cost">${v}</span></div>`;
  $('#main').innerHTML = `<div class="set scroll">
    <div class="set-h"><button class="btn g sm" data-act="tochat">${ic('chevL')}К студии</button><b>Настройки</b></div>
    <div class="set-wrap one"><div class="set-col">
      <section class="scard"><h3>Баланс</h3>
        ${row('Сейчас на счёте', (cfg.balance ?? 0) + ' кр.')}
        <span class="meta">${own ? 'Картинки и видео идут через ваш ключ WaveSpeed (тариф Pro) — WaveSpeed списывает с него напрямую. Кредиты тратятся только на Grok: разбор фото, промпты, проверку результата.'
          : 'Кредиты тратятся на генерации WaveSpeed и на работу Grok (разбор фото, промпты, проверка результата) — по факту, только за то, что реально выполнено.'}</span>
        <div><a class="btn p sm" href="${esc(cfg.billing_url)}" target="_top">Пополнить баланс</a></div></section>
      <section class="scard"><h3>Примерная цена</h3>
        ${row('Кадр Seedream V5.0 Pro', wsMoney(cfg.prices.seedream))}
        ${row('Кадр GPT Image 2.5', wsMoney(cfg.prices.gpt))}
        ${row('Видео Seedance 2.5, 5 с 720p', wsMoney((5 + 5) * (cfg.prices.seedance_720p || 0)))}
        ${row('Ход Grok (разбор, промпт, проверка)', '≈ ' + cr(0.05).replace(' кр.', '') + '–' + cr(cfg.grok_reserve || 0.15))}
        <span class="meta">Одна замена на фото — обычно 2–3 хода Grok и один кадр.</span></section>
      <section class="scard"><h3>Генерация</h3>
        <div class="row-sb"><div><div>Подтверждать каждую генерацию</div><span class="meta">Карточка с ценой и промптом перед запуском. Видео спрашивает всегда.</span></div>
          <button class="toggle ${cfg.autorun ? '' : 'on'}" id="sConfirm" role="switch" aria-checked="${!cfg.autorun}" aria-label="Подтверждать генерацию"></button></div></section>
    </div></div></div>`;
  $('#sConfirm').onclick = async e => { e.currentTarget.classList.toggle('on'); S.cfg = await post('/api/config', {autorun: !e.currentTarget.classList.contains('on')}); toast('Сохранено'); };
}
function keyField(svc, title, val, ph){
  return `<div class="lab"><span>${title}</span><div class="keyrow"><div class="wrap"><label class="sr" for="k_${svc}">${title}</label><input class="field" id="k_${svc}" type="password" autocomplete="off" placeholder="${val ? val : ph || 'вставь ключ'}" style="padding-right:38px">
    <button class="ib" data-act="keyeye" data-v="${svc}" aria-label="Показать ключ">${ic('eye')}</button></div><button class="btn" data-act="keycheck" data-v="${svc}">Проверить</button></div>
    <div class="kst" id="kst_${svc}">${val ? `<span class="pill s-idle">сохранён ключ ${esc(val)}</span>` : '<span class="pill s-wait">не задан</span>'}</div></div>`;
}

/* ---------- modals ---------- */
function modal(html){ $('#modal').innerHTML = `<div class="mod-bg" data-act="modbg"><div class="mod" role="dialog">${html}</div></div>`; const f = $('#modal input,#modal textarea'); if (f) setTimeout(() => f.focus(), 30); }
function closeModal(){ $('#modal').innerHTML = ''; }
function createModal(mode = 'photos'){
  modal(`<h2>Новая модель</h2>
    <label class="lab" for="cName">Имя<input class="field" id="cName" placeholder="Ника"></label>
    <div style="display:flex;flex-direction:column;gap:8px" id="cOpts">
      ${[['photos', 'С нуля по фото', 'Загрузишь 2–3 фото лиц — Grok соберёт лицо, потом тело и карточку'], ...(HOSTED() ? [] : [['import', 'Импорт из папки', 'Папка с card.md, faces/ и body/']]), ['empty', 'Пустая', 'Просто чат, эталоны добавишь потом']].map(([k, t, d]) =>
        `<button class="opt ${mode === k ? 'on' : ''}" data-act="copt" data-v="${k}"><span class="radio"></span><div><b>${t}</b><span>${d}</span></div></button>`).join('')}</div>
    <label class="lab" for="cPath" id="cPathL" ${mode === 'import' ? '' : 'hidden'}>Путь к папке<input class="field mono" id="cPath" placeholder="C:\\Users\\…\\.models\\Nika"></label>
    <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="cgo">Создать</button></div>`);
  $('#modal').dataset.mode = mode;
}
function renameModal(c){
  modal(`<h2>Переименовать</h2><label class="lab" for="rName">Имя<input class="field" id="rName" value="${esc(c.name)}"></label>
    <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="rgo" data-id="${c.id}">Сохранить</button></div>`);
  const i = $('#rName'); i.select(); i.onkeydown = e => { if (e.key === 'Enter') $('[data-act=rgo]').click(); };
}
async function deleteModal(c){
  let u = {images: '…', refs: '…', messages: '…', bytes: 0, spent: c.spent};
  try { u = await api(`/api/chats/${c.id}/usage`); } catch(e){}
  modal(`<h2>Удалить «${esc(c.name)}»?</h2><p>Удалятся переписка, эталоны, карточка и все картинки этого чата. Отменить нельзя.</p>
    <div class="usage"><div><small>Картинок</small><b>${u.images}</b></div><div><small>Эталонов</small><b>${u.refs}</b></div>
      <div><small>Сообщений</small><b>${u.messages}</b></div><div><small>На диске</small><b>${(u.bytes / 1048576).toFixed(1)} МБ</b></div></div>
    <p style="font-size:12.5px">Сначала можно сохранить эталоны: «Экспорт в папку» в панели модели.</p>
    <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn d" data-act="dgo" data-id="${c.id}">${ic('trash')}Удалить навсегда</button></div>`);
}
function pathModal(title, act, ph, val = ''){
  modal(`<h2>${title}</h2><label class="lab" for="pPath">Путь к папке<input class="field mono" id="pPath" placeholder="${esc(ph)}" value="${esc(val)}"></label>
    <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="${act}">Готово</button></div>`);
  $('#pPath').onkeydown = e => { if (e.key === 'Enter') $(`[data-act=${act}]`).click(); };
}
function videoModal(id){
  const c = S.chat, r = c.videos?.[id]; if (!r) return;
  const src = r.inputs_video && c.videos[r.inputs_video] ? r.inputs_video : null;
  modal(`<div class="row-sb"><h2 style="margin:0">${esc(r.label || (VSRC[r.source] || 'Видео'))}</h2><button class="ib" data-act="modclose" aria-label="Закрыть">${ic('x')}</button></div>
    <div class="vmod">${vplayer(id)}${src ? `<div><span class="lbl">Основа</span>${vplayer(src, {small: true})}</div>` : ''}</div>
    <div class="kv"><span>Источник</span><span>${VSRC[r.source] || r.source}</span><span>Длительность</span><span>${r.dur} с · ${r.fps || '?'} fps</span><span>Размер</span><span>${r.w}×${r.h}${r.resolution ? ' · ' + r.resolution : ''}</span>
      <span>Звук</span><span>${r.audio ? 'есть' : 'нет'}${r.source === 'gen' ? (r.gen_audio ? ' (новый)' : ' (исходный)') : ''}</span>${r.cuts?.length ? `<span>Склейки</span><span>${r.cuts.join(', ')} с</span>` : ''}<span>ID</span><span class="mono" style="font-size:11.5px">${id}</span></div>
    ${r.inputs?.length ? `<div><span class="lbl">Референсы</span><div class="lb-inputs" style="margin-top:8px">${r.inputs.filter(i => c.images[i]).map((i, n) => `<div style="position:relative"><img src="${thUrl(i)}" alt=""><span class="inp-n">@image${n + 1}</span></div>`).join('')}</div></div>` : ''}
    ${r.frames?.length ? `<div><span class="lbl">Кадры</span><div class="lb-inputs" style="margin-top:8px">${r.frames.filter(i => c.images[i]).map(i => `<img src="${thUrl(i)}" data-act="lb" data-id="${i}" alt="" title="${esc(c.images[i].label)}">`).join('')}</div></div>` : ''}
    ${r.prompt ? `<div><span class="lbl">Промпт</span><div class="step-prompt" style="margin-top:8px;max-height:220px">${esc(r.prompt)}</div></div>` : ''}
    <div class="mod-f"><button class="btn sm d" data-act="vdel" data-id="${id}">${ic('trash')}Удалить</button><span style="flex:1"></span>
      <button class="btn sm ${r.fav ? 'p' : ''}" data-act="vfav" data-id="${id}">${ic('star')}${r.fav ? 'В избранном' : 'В избранное'}</button>
      <a class="btn sm" href="${vUrl(id)}" download="${esc(c.name)}_${id}.${r.file.split('.').pop()}">${ic('download')}Скачать</a>
      <button class="btn sm p" data-act="vattach" data-id="${id}">${ic('clip')}В сообщение</button></div>`);
  $('#modal .mod').classList.add('wide');
}
function labelModal(id){
  const r = S.chat.images[id];
  modal(`<h2>Подпись ракурса</h2><label class="lab" for="lName">Например: анфас, 3/4, профиль, спина<input class="field" id="lName" value="${esc(r.label || '')}"></label>
    <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="lgo" data-id="${id}">Сохранить</button></div>`);
  $('#lName').onkeydown = e => { if (e.key === 'Enter') $('[data-act=lgo]').click(); };
}

/* ---------- actions ---------- */
async function uploadFile(f){
  if (!isMedia(f)) return null;
  if (isVid(f)) toast('Загружаю видео и нарезаю кадры…');
  const r = await xfetch(`/api/chats/${S.cur}/upload`, {method: 'POST', headers: {'X-Filename': encodeURIComponent(f.name || 'paste')}, body: f});
  const j = await r.json(); if (!r.ok){ toast(j.error); return null; }
  return j;
}
async function attachFiles(files){
  if (!S.cur){ toast('Сначала создай или выбери модель'); return; }
  for (const f of files){ const j = await uploadFile(f); if (j) S.attach.push({id: j.id, kind: j.kind || 'image', url: j.kind === 'video' ? '' : URL.createObjectURL(f)}); }
  S.chat = await api('/api/chats/' + S.cur);
  S.attach.forEach(a => { if (a.kind === 'video' && !a.url) a.url = vThUrl(a.id); });
  if (S.view !== 'chat'){ S.view = 'chat'; render(); } else { renderAtts(); if (S.chat.pending) render(); }
}
function attachImg(id){
  if (S.attach.some(a => a.id === id)) return toast('Уже прикреплено');
  S.attach.push({id, url: thUrl(id)});
  if (S.view !== 'chat'){ S.view = 'chat'; LB = null; renderLB(); render(); } else { renderAtts(); if (S.chat.pending) render(); }
  toast('Прикреплено к сообщению');
}
function setInput(text, focusEnd = true){
  if (S.view !== 'chat'){ S.view = 'chat'; render(); }
  const i = $('#inp'); if (!i) return;
  i.value = text; autosize(i); ls.set('draft_' + S.cur, text); i.focus(); if (focusEnd) i.setSelectionRange(text.length, text.length); updateSend();
}
async function send(){
  if (!S.cur) return;
  const inp = $('#inp'); const text = inp.value.trim();
  if (!text && !S.attach.length) return;
  if (S.chat?.running) return toast('Grok ещё работает — дождись или нажми «Стоп»');
  try {
    await post(`/api/chats/${S.cur}/message`, {text, images: S.attach.filter(a => a.kind !== 'video').map(a => a.id), videos: S.attach.filter(a => a.kind === 'video').map(a => a.id), engine: S.engine});
    inp.value = ''; ls.set('draft_' + S.cur, ''); S.attach = []; S.engine = 'auto'; S.lastSig = ''; S.jobSel = 0; S.promptOpen = false;
    setTimeout(() => loadChat(S.cur, true), 250);
  } catch(e){
    if (/xAI/.test(e.message)){ toast(e.message); S.view = 'settings'; render(); } else toast(e.message);
  }
}
async function act(a, el, ev){
  const id = el.dataset.id, v = el.dataset.v, c = S.chat;
  switch (a){
    case 'open': S.menu = null; S.view = S.view === 'settings' ? 'chat' : S.view; return openChat(id);
    case 'menu': ev.stopPropagation(); S.menu = S.menu === id ? null : id; return renderSide();
    case 'closemenu': S.menu = null; return renderSide();
    case 'sort': S.sort = v; ls.set('sort', v); return renderSide();
    case 'archtoggle': setTimeout(() => ls.set('archOpen', el.parentElement.open), 0); return;
    case 'create': S.menu = null; return createModal(el.dataset.mode || 'photos');
    case 'copt': $$('#cOpts .opt').forEach(o => o.classList.toggle('on', o === el)); $('#modal').dataset.mode = v; $('#cPathL').hidden = v !== 'import'; if (v === 'import') $('#cPath').focus(); return;
    case 'cgo': {
      const mode = $('#modal').dataset.mode; const name = $('#cName').value.trim(); const path = $('#cPath')?.value.trim();
      if (mode === 'import' && !path) return toast('Укажи путь к папке');
      const n = await post('/api/chats', {name});
      if (mode === 'import'){ try { const r = await post(`/api/chats/${n.id}/import`, {path}); toast(`Импорт: лиц ${r.faces}, тело ${r.body}, карточка ${r.card ? 'да' : 'нет'}`); } catch(e){ toast(e.message); } }
      closeModal(); await loadChats(); await openChat(n.id);
      if (mode === 'photos') $('#file').click();
      return;
    }
    case 'rename': S.menu = null; renderSide(); return renameModal(S.chats.find(x => x.id === id));
    case 'rgo': { const name = $('#rName').value.trim(); if (!name) return; await post(`/api/chats/${id}/meta`, {name}); closeModal(); await loadChats(); if (id === S.cur) loadChat(id, true); return; }
    case 'duplicate': { S.menu = null; const n = await post(`/api/chats/${id}/duplicate`, {}); await loadChats(); toast('Копия создана: эталоны и карточка без переписки'); return openChat(n.id); }
    case 'newthread': {
      S.menu = null; const root = S.chats.find(x => x.id === id);
      modal(`<h2>Новый чат с моделью «${esc(root.name)}»</h2><p>Эталоны и карточка скопируются, переписка начнётся с чистого листа. Удобно разделять локации: «Стадион», «Кафе»…</p>
        <label class="lab" for="tName">Название чата<input class="field" id="tName" placeholder="Кафе"></label>
        <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="tgo" data-id="${id}">Создать</button></div>`);
      $('#tName').onkeydown = e => { if (e.key === 'Enter') $('[data-act=tgo]').click(); };
      return;
    }
    case 'tgo': { const root = S.chats.find(x => x.id === id); const t = $('#tName').value.trim() || 'Новый чат'; const n = await post(`/api/chats/${id}/duplicate`, {name: `${root.name} · ${t}`}); closeModal(); await loadChats(); return openChat(n.id); }
    case 'pin': { S.menu = null; const x = S.chats.find(y => y.id === id); await post(`/api/chats/${id}/meta`, {pinned: !x.pinned}); return loadChats(); }
    case 'archive': { S.menu = null; const x = S.chats.find(y => y.id === id); await post(`/api/chats/${id}/meta`, {archived: !x.archived}); toast(x.archived ? 'Возвращено из архива' : 'Перенесено в архив'); return loadChats(); }
    case 'delete': { S.menu = null; renderSide(); return deleteModal(S.chats.find(x => x.id === id)); }
    case 'dgo': {
      await api('/api/chats/' + id, {method: 'DELETE'}); closeModal(); localStorage.removeItem('ps_draft_' + id);
      await loadChats(); toast('Модель удалена');
      if (id === S.cur){ const nx = S.chats.find(x => !x.archived); S.cur = null; S.chat = null; if (nx) openChat(nx.id); else render(); }
      return;
    }
    case 'modclose': return closeModal();
    case 'modbg': if (ev.target === el) closeModal(); return;
    case 'settings': S.view = 'settings'; S.menu = null; $('#app').classList.remove('side-on'); await loadMeta(); return render();
    case 'tochat': S.view = 'chat'; return render();
    case 'gallery': S.view = 'gallery'; return render();
    case 'panel': {
      if (matchMedia('(max-width:1200px)').matches){ $('#app').classList.toggle('panel-on'); if (!S.panel){ S.panel = true; render(); } return; }
      S.panel = !S.panel; ls.set('panel', S.panel); return render();
    }
    case 'sidebar': return $('#app').classList.toggle('side-on');
    case 'attach': return $('#file').click();
    case 'unattach': S.attach.splice(+v, 1); renderAtts(); if (c?.pending) render(); return;
    case 'engine': S.engine = v; return renderChat();
    case 'send': return send();
    case 'chip': return setInput(v);
    case 'stop': await post(`/api/chats/${S.cur}/stop`); return toast('Останавливаю после текущего шага…');
    case 'copy': { const m = c.messages.find(x => x.id === el.dataset.mid); await navigator.clipboard.writeText(m?.text || ''); return toast('Скопировано'); }
    case 'rollback': {
      const m = c.messages.find(x => x.id === el.dataset.mid);
      if (!confirm('Откатить чат до этого сообщения? Всё, что после, удалится, и Grok ответит заново.')) return;
      S.chat = await post(`/api/chats/${S.cur}/rollback`, {mid: m.id}); S.lastSig = ''; return loadChat(S.cur, true);
    }
    case 'delmsg': S.chat = await api(`/api/chats/${S.cur}/messages/${el.dataset.mid}`, {method: 'DELETE'}); S.lastSig = ''; return render();
    case 'regen': await post(`/api/chats/${S.cur}/regenerate`); S.lastSig = ''; return loadChat(S.cur, true);
    case 'retry': await post(`/api/chats/${S.cur}/retry`); S.lastSig = ''; return loadChat(S.cur, true);
    case 'approve': case 'approveAuto': {
      const pr = $('#pr'); if (pr && pr.value !== curJob().prompt) await patchJob({prompt: pr.value});
      await post(`/api/chats/${S.cur}/approve`, {ok: true, autorun: a === 'approveAuto'});
      if (a === 'approveAuto'){ S.cfg = await api('/api/config'); toast('Дальше без подтверждения — включить обратно можно в настройках'); }
      S.lastSig = ''; S.promptOpen = false; return loadChat(S.cur, true);
    }
    case 'reject': await post(`/api/chats/${S.cur}/approve`, {ok: false}); S.lastSig = ''; return loadChat(S.cur, true);
    case 'pjob': S.jobSel = +v; return renderChat();
    case 'penv': if (v !== curJob().engine) toast('Пересобираю входы и промпт под ' + (ENG[v] || v) + '…'); return patchJob({engine: v});
    case 'prebuild': return patchJob({rebuild: true});
    case 'ptoggle': S.promptOpen = !S.promptOpen; return renderChat();
    case 'pinrm': { const j = curJob(); const arr = [...j.inputs]; arr.splice(+v, 1); return patchJob({inputs: arr}); }
    case 'pinpick': {
      const j = curJob(); const used = new Set(j.inputs);
      const cell = i => `<button class="gi" style="aspect-ratio:4/5;border:0;padding:0;cursor:pointer;${used.has(i) ? 'opacity:.35' : ''}" data-act="pinpickgo" data-id="${i}" ${used.has(i) ? 'disabled' : ''} title="${esc(c.images[i].label || i)}"><img src="${thUrl(i)}" alt="" style="pointer-events:none"><div class="cap" style="display:flex">${esc(c.images[i].label || refRole(i) || '')}</div></button>`;
      const grid = ids => `<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px">${ids.map(cell).join('')}</div>`;
      const refsHtml = groups().filter(g => g.ids.length).map(g => `<span class="lbl">${esc(g.name)}</span>${grid(g.ids.filter(i => c.images[i]))}`).join('');
      const rest = Object.entries(c.images).filter(([i]) => !allRefs().has(i)).sort((a2, b) => b[1].t - a2[1].t).map(([i]) => i);
      modal(`<h2>Добавить вход</h2><p>Картинка встанет в конец списка — потом перетащи, чтобы поменять порядок.</p>
        ${refsHtml}${rest.length ? `<span class="lbl">Картинки чата</span>${grid(rest.slice(0, 40))}` : ''}
        <div class="mod-f"><button class="btn" data-act="pinupload">${ic('upload')}С компьютера</button><span style="flex:1"></span><button class="btn g" data-act="modclose">Готово</button></div>`);
      $('#modal .mod').style.width = 'min(640px,100%)';
      return;
    }
    case 'pinpickgo': { const j = curJob(); closeModal(); return patchJob({inputs: [...j.inputs.filter(x => x !== id), id]}); }
    case 'pinupload': { closeModal(); const f = $('#file'); f.dataset.pending = '1'; return f.click(); }
    case 'pinadd': { const j = curJob(); const arr = [...j.inputs, ...S.attach.map(x => x.id).filter(i => !j.inputs.includes(i))]; S.attach = []; return patchJob({inputs: arr}); }
    case 'lb': return openLB(id);
    case 'vlb': return videoModal(id);
    case 'vattach': { if (!S.attach.some(x => x.id === id)) S.attach.push({id, kind: 'video', url: vThUrl(id)}); closeModal(); S.view = 'chat'; render(); return toast('Видео прикреплено к сообщению'); }
    case 'vfav': { await post(`/api/chats/${S.cur}/videos/${id}`, {fav: !c.videos[id].fav}); S.chat = await api('/api/chats/' + S.cur); return videoModal(id); }
    case 'vdel': { if (!confirm('Удалить видео и его кадры?')) return; await post(`/api/chats/${S.cur}/videos`, {ids: [id]}, 'DELETE'); closeModal(); S.chat = await api('/api/chats/' + S.cur); S.lastSig = ''; return render(); }
    case 'pres': return patchJob({resolution: v});
    case 'paudio': return patchJob({audio: v === '1'});
    case 'lbgo': LB.id = id; return renderLB();
    case 'lbprev': ev.stopPropagation(); LB.id = LB.list[LB.list.indexOf(LB.id) - 1]; return renderLB();
    case 'lbnext': ev.stopPropagation(); LB.id = LB.list[LB.list.indexOf(LB.id) + 1]; return renderLB();
    case 'lbclose': LB = null; return renderLB();
    case 'lbbg': if (ev.target === el){ LB = null; renderLB(); } return;
    case 'lbcmp': LB.cmp = !LB.cmp; return renderLB();
    case 'copyprompt': await navigator.clipboard.writeText(c.images[LB.id].prompt || ''); return toast('Промпт скопирован');
    case 'fav': { const r = c.images[id]; r.fav = !r.fav; await post(`/api/chats/${S.cur}/images/${id}`, {fav: r.fav}); toast(r.fav ? 'В избранном' : 'Убрано из избранного'); S.lastSig = ''; render(); if (LB) renderLB(); return; }
    case 'toface': case 'tobody': {
      const k = a === 'toface' ? 'faces' : 'body', o = a === 'toface' ? 'body' : 'faces';
      await setPersona({[k]: [...new Set([...c.persona[k], id])], [o]: c.persona[o].filter(i => i !== id)});
      toast(a === 'toface' ? 'Добавлено в эталоны лица' : 'Добавлено в эталоны тела'); if (LB) renderLB(); return;
    }
    case 'unref': { const k = el.dataset.group; return setPersona(gPatch(c.persona, {[k]: gIds(c.persona, k).filter(i => i !== id)})); }
    case 'newcat': case 'tocatnew': {
      modal(`<h2>Новая категория эталонов</h2><p>Например: Ноги, Руки, Ногти, Тату, Спина, Образ: спорт, Телефон. Grok будет брать эти фото в генерацию, когда они нужны в кадре.</p>
        <label class="lab" for="ncName">Название<input class="field" id="ncName" placeholder="Ноги"></label>
        <label class="lab" for="ncNote">Что видно на эталонах (необязательно)<textarea class="ta" id="ncNote" rows="3" placeholder="длинные стройные ноги, полные бёдра, без тату"></textarea></label>
        <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="ncgo" data-id="${a === 'tocatnew' ? id : ''}">Создать</button></div>`);
      return;
    }
    case 'ncgo': {
      const n = $('#ncName').value.trim(); if (!n) return toast('Введи название');
      if (/^(лицо|лица|тело|фигура|faces?|body)$/i.test(n)) return toast('Лицо и тело уже есть');
      const extra = JSON.parse(JSON.stringify(c.persona.extra || {}));
      const exist = Object.keys(extra).find(k => k.toLowerCase() === n.toLowerCase()) || n;
      extra[exist] = {ids: [...(extra[exist]?.ids || []), ...(id ? [id] : [])], note: $('#ncNote').value.trim() || extra[exist]?.note || ''};
      closeModal(); await setPersona({extra}); if (LB) renderLB(); return toast(id ? `Добавлено в «${exist}»` : `Категория «${exist}» создана`);
    }
    case 'delcat': {
      const n = el.dataset.group.slice(2); if (!confirm(`Удалить категорию «${n}»? Фото останутся в галерее.`)) return;
      const extra = JSON.parse(JSON.stringify(c.persona.extra || {})); delete extra[n]; return setPersona({extra});
    }
    case 'catnote': {
      const g = groups().find(x => x.key === el.dataset.group);
      modal(`<h2>${esc(g.builtin ? 'Эталоны ' + (g.key === 'faces' ? 'лица' : 'тела') : g.name)}</h2><p>Что видно на этих эталонах — Grok учитывает это, когда пишет промпт.</p>
        <label class="lab" for="cnNote">Описание<textarea class="ta" id="cnNote" rows="4">${esc(g.note)}</textarea></label>
        <div class="mod-f"><button class="btn g" data-act="modclose">Отмена</button><button class="btn p" data-act="cngo" data-v="${esc(g.key)}">Сохранить</button></div>`);
      return;
    }
    case 'cngo': {
      const key = v, note = $('#cnNote').value.trim(); closeModal();
      if (key === 'faces' || key === 'body') return setPersona({notes: {...(c.persona.notes || {}), [key]: note}});
      const extra = JSON.parse(JSON.stringify(c.persona.extra || {})); extra[key.slice(2)].note = note; return setPersona({extra});
    }
    case 'tocat': {
      const key = el.value; el.value = ''; if (!key) return;
      if (key === '__new') return act('tocatnew', {dataset: {id: el.dataset.id}}, ev);
      const ch = {[key]: [...new Set([...gIds(c.persona, key), el.dataset.id])]};
      await setPersona(gPatch(c.persona, ch)); if (LB) renderLB();
      return toast(`Добавлено в «${groups().find(g => g.key === key).name}»`);
    }
    case 'relabel': return labelModal(id);
    case 'lgo': { await post(`/api/chats/${S.cur}/images/${id}`, {label: $('#lName').value.trim()}); closeModal(); S.chat = await api('/api/chats/' + S.cur); S.lastSig = ''; return render(); }
    case 'refadd': { const g = el.dataset.group; const f = $('#file'); f.dataset.group = g; return f.click(); }
    case 'attachimg': return attachImg(id);
    case 'variations': attachImg(id); LB = null; renderLB(); return setInput('Сделай 3 вариации этого кадра: та же локация и одежда, другие позы и ракурсы');
    case 'editimg': attachImg(id); LB = null; renderLB(); return setInput('Локальная правка этого кадра: ');
    case 'delimg': {
      if (!confirm('Удалить картинку? Она уберётся из эталонов, если там была.')) return;
      const list = LB?.list || []; const k = list.indexOf(id);
      await post(`/api/chats/${S.cur}/images`, {ids: [id]}, 'DELETE'); S.chat = await api('/api/chats/' + S.cur);
      if (LB){ LB.list = list.filter(x => x !== id); LB.id = LB.list[Math.min(k, LB.list.length - 1)]; if (!LB.id) LB = null; renderLB(); }
      S.lastSig = ''; return render();
    }
    case 'cardtab': S.cardTab = v; return renderPanel();
    case 'export': return pathModal('Экспорт модели в папку', 'exgo', 'C:\\Users\\…\\.models\\' + c.name, ls.get('exportDir', '') ? ls.get('exportDir', '') + '\\' + c.name : '');
    case 'exgo': { const p = $('#pPath').value.trim(); if (!p) return; try { const r = await post(`/api/chats/${S.cur}/export`, {path: p}); ls.set('exportDir', p.replace(/[\\/][^\\/]+$/, '')); closeModal(); toast(`Экспортировано: ${r.files} фото + card.md`); } catch(e){ toast(e.message); } return; }
    case 'importPrompt': return pathModal('Импорт модели из папки', 'imgo', 'C:\\Users\\…\\.models\\Nika');
    case 'imgo': { const p = $('#pPath').value.trim(); if (!p) return; try { const r = await post(`/api/chats/${S.cur}/import`, {path: p}); closeModal(); toast(`Импорт: лиц ${r.faces}, тело ${r.body}, карточка ${r.card ? 'да' : 'нет'}`); await loadChats(); return loadChat(S.cur, true); } catch(e){ toast(e.message); } return; }
    // gallery
    case 'gfilter': S.gal.filter = v; return renderGallery();
    case 'gengine': S.gal.engine = v; return renderGallery();
    case 'gselect': S.gal.select = !S.gal.select; S.gal.sel.clear(); return renderGallery();
    case 'gsel': S.gal.sel.has(id) ? S.gal.sel.delete(id) : S.gal.sel.add(id); return renderGallery();
    case 'gselall': galItems().items.forEach(r => S.gal.sel.add(r.id)); return renderGallery();
    case 'gzip': {
      const r = await xfetch(`/api/chats/${S.cur}/zip`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: [...S.gal.sel]})});
      const b = await r.blob(); const u = URL.createObjectURL(b); const a2 = document.createElement('a'); a2.href = u; a2.download = `${c.name}.zip`; a2.click(); setTimeout(() => URL.revokeObjectURL(u), 5000); return;
    }
    case 'gattach': [...S.gal.sel].forEach(i => { if (!S.attach.some(x => x.id === i)) S.attach.push({id: i, url: thUrl(i)}); }); S.gal.select = false; S.gal.sel.clear(); S.view = 'chat'; render(); return toast('Прикреплено к сообщению');
    case 'gcarousel': { const ids = [...S.gal.sel]; ids.forEach(i => { if (!S.attach.some(x => x.id === i)) S.attach.push({id: i, url: thUrl(i)}); }); S.gal.select = false; S.gal.sel.clear(); S.view = 'chat'; render(); return setInput(`Карусель ${Math.max(4, ids.length)} по этим кадрам, обрежь до 4:5`); }
    case 'gdelete': {
      if (!confirm(`Удалить ${S.gal.sel.size} картинок?`)) return;
      const r = await post(`/api/chats/${S.cur}/images`, {ids: [...S.gal.sel]}, 'DELETE'); S.gal.sel.clear(); S.chat = await api('/api/chats/' + S.cur); toast(`Удалено: ${r.deleted}`); return renderGallery();
    }
    // settings
    case 'keyeye': { const i = $('#k_' + v); i.type = i.type === 'password' ? 'text' : 'password'; return; }
    case 'keycheck': {
      const i = $('#k_' + v); const st = $('#kst_' + v);
      if (i.value.trim()){ S.cfg = await post('/api/config', {[v === 'xai' ? 'xai_key' : 'wavespeed_key']: i.value.trim()}); i.value = ''; i.placeholder = S.cfg[v === 'xai' ? 'xai_key' : 'wavespeed_key']; }
      st.innerHTML = '<span class="spin"></span><span class="meta">проверяю…</span>';
      const r = await post('/api/config/check', {service: v});
      st.innerHTML = r.ok ? `<span class="pill s-ok">работает</span><span class="meta">${esc(r.info || '')}</span>` : `<span class="pill s-err">ошибка</span><span class="meta">${esc(r.error || '')}</span>`;
      if (r.ok) loadMeta();
      return;
    }
    case 'saveGen': {
      S.cfg = await post('/api/config', {autorun: !$('#sConfirm').classList.contains('on'),
        limits: {per_message: $('#lMsg').value || 0, per_day: $('#lDay').value || 0},
        prices: {gpt: $('#pGpt').value, seedream: $('#pSd').value, seedance_480p: $('#pV480').value, seedance_720p: $('#pV720').value, seedance_1080p: $('#pV1080').value}});
      await loadMeta(); $('#genState').innerHTML = '<span class="pill s-ok">сохранено</span>'; renderSide(); return;
    }
    case 'ptab': S.settingsTab = v; return renderSettings();
    case 'psave': { S.promptsCache[S.settingsTab] = await post('/api/prompts/' + S.settingsTab, {text: $('#promptTa').value}, 'PUT'); toast('Сохранено — действует со следующего сообщения'); return renderSettings(); }
    case 'presetDefault': { if (!confirm('Вернуть исходный текст? Твои правки в этом файле пропадут.')) return; S.promptsCache[S.settingsTab] = await post(`/api/prompts/${S.settingsTab}/reset`); toast('Возвращено к исходному'); return renderSettings(); }
  }
}

/* ---------- global events ---------- */
document.addEventListener('click', e => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  if (el.tagName === 'A' && !el.dataset.act) return;
  const a = el.dataset.act;
  if (a === 'archtoggle'){ act(a, el, e); return; }
  e.preventDefault();
  act(a, el, e).catch(err => toast(err.message));
});
document.addEventListener('change', e => { if (e.target.dataset?.tocat) act('tocat', e.target, e).catch(err => toast(err.message)); });
$('#scrim').onclick = () => $('#app').classList.remove('side-on', 'panel-on');
$('#file').onchange = async e => {
  const files = [...e.target.files]; const g = e.target.dataset.group; const pend = e.target.dataset.pending; e.target.value = ''; delete e.target.dataset.group; delete e.target.dataset.pending;
  if (g) return addRefsFromFiles(files, g);
  if (pend && S.chat?.pending){ const ids = []; for (const f of files.filter(f => !isVid(f))){ const r = await uploadFile(f); if (r) ids.push(r.id); } if (ids.length){ S.chat = await api('/api/chats/' + S.cur); return patchJob({inputs: [...curJob().inputs, ...ids]}); } return; }
  attachFiles(files);
};
document.addEventListener('paste', e => {
  const fs = [...(e.clipboardData?.files || [])].filter(isMedia);
  if (fs.length && S.view !== 'settings'){ e.preventDefault(); attachFiles(fs); }
});
let dragDepth = 0;
document.addEventListener('dragenter', e => { if (![...e.dataTransfer.types].includes('Files')) return; dragDepth++; if (S.view === 'chat' && S.chat) $('#main').classList.add('dragging'); });
document.addEventListener('dragleave', e => { if (![...e.dataTransfer.types].includes('Files')) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $('#main').classList.remove('dragging'); });
document.addEventListener('dragover', e => { if ([...e.dataTransfer.types].includes('Files')) e.preventDefault(); });
document.addEventListener('drop', e => {
  dragDepth = 0; $('#main').classList.remove('dragging');
  if (e.defaultPrevented || ![...e.dataTransfer.types].includes('Files')) return;
  e.preventDefault();
  if (e.target.closest('#panel')) return;
  attachFiles([...e.dataTransfer.files].filter(isMedia));
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape'){ if (LB){ LB = null; renderLB(); } else if ($('#modal').innerHTML){ closeModal(); } else if (S.menu){ S.menu = null; renderSide(); } else $('#app').classList.remove('side-on', 'panel-on'); }
  if (LB && !e.target.closest('input,textarea')){
    const k = LB.list.indexOf(LB.id);
    if (e.key === 'ArrowLeft' && k > 0){ LB.id = LB.list[k - 1]; renderLB(); }
    if (e.key === 'ArrowRight' && k < LB.list.length - 1){ LB.id = LB.list[k + 1]; renderLB(); }
  }
});

/* ---------- boot ---------- */
(async () => {
  await loadMeta();
  await loadChats();
  const pick = S.chats.find(c => c.id === S.cur) || S.chats.find(c => !c.archived);
  if (pick) await openChat(pick.id); else render();
  if (!S.cfg?.xai_key){ S.view = 'settings'; render(); toast('Впиши ключи xAI и WaveSpeed'); }
  setInterval(loadMeta, 60000);
})();
