/**
 * Unibox UI — рендер и события, данные из ChatController + кэш медиа.
 */

import type { ChatController } from '../store/ChatController'
import type { PersonaFilter } from '../cache/threadCache'
import type { StudioModel, UiChat, UiMessage } from '../types'
import { esc, initials, avatarGradient, plural } from '../lib/format'
import { platformMeta, platformIconImg, SOURCE_TABS } from '../lib/platforms'
import { outboundLangOptions, replyLangDisplay, translationLineLabel } from '../lib/lang'
import { previewText, chatSubTitle, chatListPreview, chatListTime } from '../lib/mapMessage'
import { REACTION_EMOJIS } from '../lib/reactions'
import { loadUiSettings, saveUiSettings } from '../cache/threadCache'
import { pushPermission, pushSupported, registerChatPush, unregisterChatPush } from '../api/push'
import { I } from './icons'
import { ThreadScroll } from './scroll'

const $ = (s: string) => document.querySelector(s) as HTMLElement | null
const $$ = (s: string) => [...document.querySelectorAll(s)] as HTMLElement[]

const SYS_FOLDERS = [
  { id: 'all', n: 'Все' },
  { id: 'vip', n: 'VIP' },
  { id: 'hot', n: 'Без ответа' },
  { id: 'biz', n: 'Реклама' },
]

const ACCENTS = ['#3390ec', '#8774e1', '#4fae4e', '#e17076', '#f0a30a', '#00b0d0']

/** Режимы AI-компаньона — как в кабинете Dialogs. */
const COMPANION_MODES = [
  { id: 'off', label: 'Выкл' },
  { id: 'semi_auto', label: 'Полуавто' },
  { id: 'auto', label: 'Авто' },
] as const

/** Подпись режима AI-компаньона для шапки чата и меню. */
function companionModeLabel(mode: string | null | undefined): string {
  return COMPANION_MODES.find((m) => m.id === mode)?.label || 'Выкл'
}

/** Быстрые эмодзи для вставки в поле ввода. */
const EMOJI_QUICK = [
  '😀', '😃', '😄', '😁', '😂', '🙂', '😉', '😊', '🥰', '😍',
  '😘', '😎', '🤔', '😢', '😭', '🙏', '👍', '👎', '👏', '🔥', '❤️', '✨', '🎉',
]

type FindState = { q: string; hits: number[]; i: number }

export class UniboxApp {
  folder = 'all'
  src = 'all'
  query = ''
  reply: number | null = null
  theme: 'light' | 'dark' = 'light'
  accent = '#3390ec'
  pane = false
  ptab: 'info' | 'notes' = 'info'
  lastRenderedMsgId: number | null = null
  flashMsgId: number | null = null
  /** Поиск по тексту в открытом треде. */
  find: FindState | null = null
  /** Активный персонаж — фильтр диалогов (как аккаунты в Telegram). */
  activePersonaId: PersonaFilter = 'all'

  private scroll = new ThreadScroll()
  private unbindScroll: (() => void) | null = null
  private fileInput: HTMLInputElement | null = null
  /** Блокируем повторную подгрузку истории при скролле. */
  private olderLoadLock = false

  constructor(private ctrl: ChatController) {}

  async mount(): Promise<void> {
    document.querySelectorAll('.edge.l').forEach((b) => { b.innerHTML = I.chevL })
    document.querySelectorAll('.edge.r').forEach((b) => { b.innerHTML = I.chevR })
    $('#addFolder')!.innerHTML = I.folderPlus

    const saved = await loadUiSettings()
    if (saved) {
      this.theme = saved.theme === 'dark' ? 'dark' : 'light'
      this.accent = saved.accent || this.accent
      if (saved.activePersonaId != null) this.activePersonaId = saved.activePersonaId
    }
    this.applyTheme()

    this.ctrl.subscribe(() => this.renderAll())
    this.bindGlobal()
    this.initStrips()
    this.resolveActivePersona()
    this.renderAll()
  }

  /** После загрузки models — валидируем сохранённый персонаж. */
  resolveActivePersona(): void {
    const models = this.ctrl.models
    if (models.length === 1 && !this.hasUnassignedChats()) {
      this.activePersonaId = models[0].id
      return
    }
    if (typeof this.activePersonaId === 'number') {
      if (!models.some((m) => m.id === this.activePersonaId)) {
        this.activePersonaId = models.length > 1 ? 'all' : (models[0]?.id ?? 'all')
      }
    }
  }

  private hasUnassignedChats(): boolean {
    return this.ctrl.chats.some((c) => c.raw.studio_model_id == null)
  }

  private showPersonaSwitcher(): boolean {
    return this.ctrl.models.length > 1 || this.hasUnassignedChats()
  }

  /** Диалог принадлежит выбранному персонажу. */
  private inPersona(c: UiChat): boolean {
    if (!this.showPersonaSwitcher()) {
      if (this.ctrl.models.length === 1) {
        return c.raw.studio_model_id === this.ctrl.models[0].id
      }
      return true
    }
    if (this.activePersonaId === 'all') return true
    if (this.activePersonaId === 'none') return c.raw.studio_model_id == null
    return Number(c.raw.studio_model_id) === Number(this.activePersonaId)
  }

  private unreadForPersona(filter: PersonaFilter): number {
    return this.ctrl.chats
      .filter((c) => {
        if (filter === 'all') return true
        if (filter === 'none') return c.raw.studio_model_id == null
        return Number(c.raw.studio_model_id) === Number(filter)
      })
      .reduce((a, c) => a + c.unread, 0)
  }

  private currentPersonaLabel(): string {
    if (typeof this.activePersonaId === 'number') {
      return this.ctrl.models.find((m) => m.id === this.activePersonaId)?.name || 'Персонаж'
    }
    if (this.activePersonaId === 'none') return 'Без модели'
    return 'Все персонажи'
  }

  private personaAvaHtml(model: StudioModel, idx: number, sm = false): string {
    const img = model.images?.[0]?.url
    const inner = img ? `<img src="${esc(img)}" alt="">` : esc(initials(model.name))
    const cls = img ? `has-photo ${sm ? 'sm' : ''}` : sm ? 'sm' : ''
    return `<div class="ava ${cls}" style="${img ? '' : avatarGradient(idx % 7)}">${inner}</div>`
  }

  private async switchPersona(id: PersonaFilter): Promise<void> {
    this.activePersonaId = id
    void saveUiSettings(this.theme, this.accent, id)
    const active = this.ctrl.activeChat
    if (active && !this.inPersona(active)) {
      this.ctrl.activeChatId = null
      $('#app')?.classList.remove('open')
      this.pane = false
      $('#app')?.classList.remove('side-open')
    }
    this.drawer(false)
    this.renderAll()
  }

  /** Пользователь печатает в composer — нельзя пересоздавать textarea (сбросит курсор). */
  private isComposingMessage(): boolean {
    const el = document.activeElement
    return el instanceof HTMLTextAreaElement && el.id === 'inp'
  }

  private renderAll(): void {
    this.renderTabs()
    this.renderList()
    if (this.isComposingMessage()) {
      // WS/обновления списка — только лента сообщений, поле ввода не трогаем
      this.renderMsgs(true)
    } else {
      this.renderChat()
    }
    if (this.pane) this.renderPane()
  }

  private bindGlobal(): void {
    $('#q')?.addEventListener('input', (e) => {
      this.query = (e.target as HTMLInputElement).value
      this.renderList()
    })
    $('#burger')?.addEventListener('click', () => {
      this.renderDrawer()
      $('#drawer')?.classList.add('on')
      $('#scrim')?.classList.add('on')
    })
    $('#scrim')?.addEventListener('click', () => this.drawer(false))

    document.addEventListener('click', (e) => {
      const t = e.target as HTMLElement
      const pop = t.closest('.pop') as HTMLElement | null

      const qr = t.closest('[data-qr]') as HTMLElement | null
      if (qr && pop?.id === 'ctx') {
        void this.toggleReaction(Number(pop.dataset.msg), qr.dataset.qr || '')
        this.closePops()
        return
      }
      const act = t.closest('[data-act]') as HTMLElement | null
      if (act && pop?.id === 'ctx') {
        this.msgAct(act.dataset.act || '')
        this.closePops()
        return
      }
      const ca = t.closest('[data-chatact]') as HTMLElement | null
      if (ca) {
        this.chatAct(ca.dataset.chatact || '')
        this.closePops()
        return
      }
      const fp = t.closest('[data-folder-pick]') as HTMLElement | null
      if (fp) {
        void this.pickFolderForChat(Number(fp.dataset.folderPick), Number(fp.dataset.conv))
        return
      }
      const fa = t.closest('[data-folder-act]') as HTMLElement | null
      if (fa && pop?.id === 'ctx') {
        this.folderAct(fa.dataset.folderAct || '', Number(pop.dataset.folderId))
        this.closePops()
        return
      }
      const em = t.closest('[data-em]') as HTMLElement | null
      if (em) {
        const inp = $('#inp') as HTMLTextAreaElement | null
        if (inp) {
          inp.value += em.dataset.em || ''
          inp.dispatchEvent(new Event('input'))
          inp.focus()
        }
        this.closePops()
        return
      }

      if (!pop) this.closePops()

      if (t.closest('#addFolder')) {
        this.openFolderCreate()
        return
      }

      const chatEl = t.closest('[data-chat]')
      if (chatEl && !pop) {
        const id = Number((chatEl as HTMLElement).dataset.chat)
        void this.openChat(id)
        return
      }
      const f = t.closest('[data-f]') as HTMLElement | null
      if (f) {
        this.folder = f.dataset.f || 'all'
        this.renderTabs()
        this.renderList()
        return
      }
      const sr = t.closest('[data-src]') as HTMLElement | null
      if (sr) {
        this.src = sr.dataset.src || 'all'
        this.renderTabs()
        this.renderList()
        return
      }
      const acc = t.closest('[data-acc]') as HTMLElement | null
      if (acc) {
        this.accent = acc.dataset.acc || this.accent
        this.applyTheme()
        this.renderDrawer()
      }
      const pr = t.closest('[data-persona]') as HTMLElement | null
      if (pr) {
        const raw = pr.dataset.persona || 'all'
        const next: PersonaFilter = raw === 'all' ? 'all' : raw === 'none' ? 'none' : Number(raw)
        void this.switchPersona(next)
        return
      }
      const di = t.closest('.dr-item') as HTMLElement | null
      if (di) this.drawerAct(di.dataset.act || '')
      const st = t.closest('[data-strip]') as HTMLElement | null
      if (st) {
        const [wid, dir] = (st.dataset.strip || '').split(':')
        const strip = document.getElementById(wid)?.querySelector('.tabs') as HTMLElement | null
        if (strip) {
          const step = Number(dir) * Math.max(140, strip.clientWidth * 0.7)
          strip.scrollBy({ left: step, behavior: 'smooth' })
        }
      }
    })

    this.fileInput = document.createElement('input')
    this.fileInput.type = 'file'
    this.fileInput.accept = 'image/*'
    this.fileInput.hidden = true
    document.body.appendChild(this.fileInput)
    this.fileInput.addEventListener('change', () => {
      const file = this.fileInput?.files?.[0]
      const chat = this.ctrl.activeChat
      if (file && chat) void this.ctrl.sendImage(chat.id, '', file)
      if (this.fileInput) this.fileInput.value = ''
    })

    $('#list')?.addEventListener('contextmenu', (e) => {
      const row = (e.target as HTMLElement).closest('[data-chat]') as HTMLElement | null
      if (!row) return
      e.preventDefault()
      const c = this.ctrl.chats.find((x) => x.id === Number(row.dataset.chat))
      if (c) this.chatMenu(c, e.clientX, e.clientY)
    })

    // ПКМ по пользовательской вкладке папки — переименовать / удалить
    $('#folders')?.addEventListener('contextmenu', (e) => {
      const tab = (e.target as HTMLElement).closest('[data-f]') as HTMLElement | null
      if (!tab) return
      const id = tab.dataset.f || ''
      if (!/^\d+$/.test(id)) return
      e.preventDefault()
      this.folderTabMenu(Number(id), e.clientX, e.clientY)
    })

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closePops()
        this.drawer(false)
      }
    })
  }

  private closePops(): void {
    $$('.pop').forEach((p) => p.classList.remove('on'))
  }

  private showPop(el: HTMLElement, x: number, y: number): void {
    el.classList.add('on')
    const r = el.getBoundingClientRect()
    el.style.left = `${Math.max(8, Math.min(x, innerWidth - r.width - 8))}px`
    el.style.top = `${Math.max(8, Math.min(y, innerHeight - r.height - 8))}px`
  }

  private inFolder(c: UiChat): boolean {
    if (this.folder === 'all') return true
    if (this.folder === 'vip') return Boolean(c.pinned)
    if (this.folder === 'hot') return Boolean(c.raw.is_no_response)
    if (this.folder === 'biz') return Boolean(c.biz)
    const f = this.ctrl.folders.find((x) => String(x.id) === this.folder)
    if (f) return f.conversation_ids.includes(c.id)
    return true
  }

  private inSrc(c: UiChat): boolean {
    if (this.src === 'all') return true
    const tab = SOURCE_TABS.find((x) => x.id === this.src)
    if (!tab || !('platform' in tab)) return true
    return tab.platform.includes(String(c.raw.platform).toLowerCase())
  }

  private renderTabs(): void {
    const tab = (id: string, name: string, unread: number, on: boolean) =>
      `<button class="tab ${on ? 'on' : ''}" data-f="${esc(id)}" data-ftab="${esc(id)}">${esc(name)}${unread ? `<i>${unread > 99 ? '99+' : unread}</i>` : ''}</button>`

    const folderTabs = SYS_FOLDERS.map((f) => {
      const u = this.ctrl.chats.filter((c) => this.inPersona(c) && this.inSrc(c) && this.matchFolderId(c, f.id)).reduce((a, c) => a + c.unread, 0)
      return tab(f.id, f.n, u, this.folder === f.id)
    })
    const custom = this.ctrl.folders.map((f) => {
      const u = this.ctrl.chats.filter((c) => this.inPersona(c) && f.conversation_ids.includes(c.id) && this.inSrc(c)).reduce((a, c) => a + c.unread, 0)
      return tab(String(f.id), f.name, u, this.folder === String(f.id))
    })
    $('#folders')!.innerHTML = folderTabs.join('') + custom.join('')

    const srcTab = (id: string, name: string, color: string | null, unread: number, on: boolean) => {
      const glyph = color ? `<span class="s-ic" style="color:${color}">${platformIconImg(id === 'tg' ? 'telegram' : id === 'fv' ? 'fanvue' : 'instagram', 17)}</span>` : ''
      return `<button class="tab ${on ? 'on' : ''}" data-src="${esc(id)}" title="${esc(name)}">${glyph}${on || !color ? esc(name) : ''}${unread ? `<i>${unread > 99 ? '99+' : unread}</i>` : ''}</button>`
    }

    const srcUnread = (id: string) =>
      this.ctrl.chats.filter((c) => this.inPersona(c) && this.inFolder(c) && (id === 'all' || c.src === id)).reduce((a, c) => a + c.unread, 0)

    $('#sources')!.innerHTML =
      srcTab('all', 'Все сети', null, srcUnread('all'), this.src === 'all') +
      srcTab('tg', 'Telegram', '#2AABEE', srcUnread('tg'), this.src === 'tg') +
      srcTab('fv', 'Fanvue', '#7C4DFF', srcUnread('fv'), this.src === 'fv') +
      srcTab('ig', 'Instagram', '#E1306C', srcUnread('ig'), this.src === 'ig')

    ;['wrapF', 'wrapS'].forEach((id) => {
      const w = document.getElementById(id) as HTMLElement & { __upd?: () => void }
      w?.__upd?.()
    })
  }

  private matchFolderId(c: UiChat, folderId: string): boolean {
    if (folderId === 'all') return true
    if (folderId === 'vip') return Boolean(c.pinned)
    if (folderId === 'hot') return Boolean(c.raw.is_no_response)
    if (folderId === 'biz') return Boolean(c.biz)
    const f = this.ctrl.folders.find((x) => String(x.id) === folderId)
    return f ? f.conversation_ids.includes(c.id) : false
  }

  private avaHtml(c: UiChat, sm = false): string {
    const pm = platformMeta(c.raw.platform)
    const avUrl = this.ctrl.avatarUrls.get(c.id)
    const inner = avUrl
      ? `<img src="${avUrl}" alt="">`
      : esc(initials(c.name))
    const cls = avUrl ? `has-photo ${sm ? 'sm' : ''}` : sm ? 'sm' : ''
    return `<div class="ava ${cls}" style="${avUrl ? '' : avatarGradient(c.g)}">${inner}
      <span class="src-b" style="background:${pm.color}" title="${esc(pm.name)}">${platformIconImg(c.raw.platform, 11)}</span></div>`
  }

  private renderList(): void {
    const q = this.query.trim().toLowerCase()
    let list = this.ctrl.chats.filter((c) => this.inPersona(c) && this.inFolder(c) && this.inSrc(c))
    if (q) {
      list = list.filter((c) => {
        const last = chatListPreview(c).toLowerCase()
        return c.name.toLowerCase().includes(q) || c.handle.toLowerCase().includes(q) || last.includes(q)
      })
    }
    list = [...list].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))

    const activeId = this.ctrl.activeChatId
    const html = list.map((c) => {
      const m = c.msgs[c.msgs.length - 1] || null
      const ticks = m && m.out ? `<span class="ticks">${I.checks}</span>` : ''
      const listTime = chatListTime(c)
      return `<div class="row ${activeId === c.id ? 'on' : ''}" data-chat="${c.id}">
        ${this.avaHtml(c)}
        <div class="mid">
          <div class="r1"><span class="nm">${esc(c.name)}</span>
            <span class="time">${ticks}${listTime ? esc(listTime) : ''}</span></div>
          <div class="r2">
            <span class="last">${esc(chatListPreview(c))}</span>
            ${c.unread ? `<span class="badge">${c.unread > 99 ? '99+' : c.unread}</span>` : ''}
          </div>
        </div>
      </div>`
    }).join('')

    $('#list')!.innerHTML = html || '<div class="empty-s">Нет диалогов.<br>Подключите соцсети в кабинете.</div>'
  }

  async openChat(convId: number): Promise<void> {
    const chat = this.ctrl.chats.find((c) => c.id === convId)
    if (chat && !this.inPersona(chat)) {
      const mid = chat.raw.studio_model_id
      await this.switchPersona(mid == null ? 'none' : mid)
    }
    this.reply = null
    this.find = null
    this.scroll.onThreadOpen()
    $('#app')?.classList.add('open')
    await this.ctrl.openChat(convId)
    this.renderAll()
    // Не даём браузеру проскроллить document при фокусе на input — шапка уезжала вверх
    window.scrollTo(0, 0)
  }

  private renderChat(): void {
    const c = this.ctrl.activeChat
    const pane = $('#chatPane')!
    if (!c) {
      pane.innerHTML = `<div style="flex:1;display:grid;place-items:center;color:var(--txt-2);font-size:14px">Выберите диалог</div>`
      return
    }

    const sub = chatSubTitle(c)
    const trOn = !c.raw.auto_translate_disabled
    const replyLang = replyLangDisplay(c.raw)
    const companionMode = c.raw.companion_mode_override ?? c.raw.effective_companion_mode ?? 'off'
    const companionChip = companionMode !== 'off'
      ? `<span class="tr-chip bot-chip">AI · ${esc(companionModeLabel(companionMode))}</span>`
      : ''
    const head = this.find
      ? `<header class="head">
          <button class="ic" id="findClose" title="Закрыть поиск">${I.close}</button>
          <label class="searchbox">${I.search}
            <input id="findInp" placeholder="Поиск в этом чате" value="${esc(this.find.q)}" autocomplete="off">
          </label>
          <span class="find-n" id="findN"></span>
          <button class="ic" id="findUp" title="Выше">${I.up}</button>
          <button class="ic" id="findDown" title="Ниже">${I.down}</button>
        </header>`
      : `<header class="head">
          <button class="ic back" id="backBtn">${I.back}</button>
          <span id="headAva" style="cursor:pointer">${this.avaHtml(c, true)}</span>
          <div class="t" id="openPane">
            <div class="h-nm">${esc(c.name)}</div>
            <div class="h-sub">${esc(sub.t)} ${trOn ? `<span class="tr-chip">RU ⇄ ${esc(replyLang)}</span>` : ''}${companionChip}</div>
          </div>
          <button class="ic" id="companionBtn" title="AI-компаньон">${I.info}</button>
          <button class="ic" id="notesBtn" title="Заметки">${I.note}</button>
          <button class="ic" id="trBtn" title="Перевод">${I.globe}</button>
          <button class="ic" id="searchInChat" title="Поиск в чате">${I.search}</button>
          <button class="ic" id="chatMenuBtn" title="Ещё">${I.dots}</button>
        </header>`
    pane.innerHTML = `${head}
      <div class="msgs" id="msgs"></div>
      <button class="scroll-down" id="scrollDown">${I.down}</button>
      <div class="comp">
        ${this.reply ? this.replyBar(c) : ''}
        <div class="crow">
          <button class="ic" id="attachBtn" title="Фото">${I.clip}</button>
          <button class="ic" id="emojiBtn" title="Эмодзи">${I.smile}</button>
          <textarea class="inp" id="inp" rows="1" placeholder="Сообщение…">${esc(c.draft || '')}</textarea>
          <button class="send" id="sendBtn" title="Отправить">${I.send}</button>
        </div>
        ${trOn && replyLang !== 'Русский' && replyLang !== 'RU' ? `<div class="out-tr">${I.globe} Клиенту уйдёт на ${esc(replyLang)}</div>` : ''}
      </div>`

    this.renderMsgs(false)
    this.bindChat(c)
  }

  private replyBar(c: UiChat): string {
    const m = c.msgs.find((x) => x.id === this.reply)
    return `<div class="cbar"><div class="bar"></div>
      <div class="t"><b>Ответ</b><span>${esc(previewText(m || null).slice(0, 90))}</span></div>
      <button class="ic" id="cancelBar">${I.close}</button></div>`
  }

  private renderMsgs(keepPosition: boolean): void {
    const c = this.ctrl.activeChat
    const box = $('#msgs')
    if (!c || !box) return

    const anchor = this.ctrl.unreadAnchor[c.id]
    let html = ''
    let lastDay = ''
    c.msgs.forEach((m, i) => {
      if (m.day !== lastDay) {
        html += `<div class="day">${esc(m.day)}</div>`
        lastDay = m.day
      }
      if (anchor !== undefined && i === anchor) {
        html += '<div class="unread-line">Непрочитанные сообщения</div>'
      }
      const next = c.msgs[i + 1]
      const sameTail = next && next.out === m.out && next.day === m.day
      html += this.msgHtml(m, c, !sameTail, i)
    })

    box.innerHTML = html
    this.hydrateMedia(c)
    this.scroll.afterMessagesRender(box, { keepPosition: keepPosition })
    if (this.find) this.updateFindN()

    const last = c.msgs[c.msgs.length - 1]
    if (last && last.id !== this.lastRenderedMsgId && last.id > 0) {
      this.flashMsgId = last.id
      const row = document.getElementById(`msg-${last.id}`)
      row?.classList.add('flash')
      window.setTimeout(() => row?.classList.remove('flash'), 1200)
    }
    this.lastRenderedMsgId = last?.id ?? null

    if (anchor !== undefined) {
      window.setTimeout(() => {
        delete this.ctrl.unreadAnchor[c.id]
      }, 3000)
    }
  }

  private msgHtml(m: UiMessage, c: UiChat, tail: boolean, idx = -1): string {
    const findHit = this.find && idx >= 0 && this.find.hits[this.find.i] === m.id
    const cls = ['mrow', m.out ? 'out' : '', tail ? '' : '', m.pending ? 'pending' : '', findHit ? 'find-hit' : ''].filter(Boolean).join(' ')
    // Перевод: входящие → RU снизу; исходящие → сверху RU оператора, снизу текст клиенту
    const showTr = Boolean(m.ru && m.ru !== m.text && !c.raw.auto_translate_disabled)
    const trLb = translationLineLabel(m.out, c.raw)
    const meta = `<span class="meta">${esc(m.time)}${m.pending ? ' …' : ''}</span>`
    let inner = ''

    if (m.replyTo) {
      const r = c.msgs.find((x) => x.id === m.replyTo)
      inner += `<div class="reply"><div class="rb"></div><div><b>${esc(c.name)}</b><span>${esc(previewText(r || null).slice(0, 60))}</span></div></div>`
    }

    if (m.kind === 'photo' || m.kind === 'video_note') {
      const mediaSrc = m.mediaKey ? this.ctrl.mediaUrls.get(m.mediaKey) : m.attachmentUrl
      const isVn = m.kind === 'video_note'
      const mediaTag = mediaSrc
        ? (isVn
          ? `<video class="video-note" src="${mediaSrc}" autoplay loop muted playsinline></video>`
          : `<img src="${mediaSrc}" alt="" loading="lazy">`)
        : '<span style="padding:20px;display:block">…</span>'
      inner += `<div class="photo ${isVn ? 'vn' : ''}" data-msg-media="${m.id}" data-vn="${isVn ? '1' : '0'}">${mediaTag}</div>`
      if (m.text) {
        inner += `<div class="txt">${this.fmt(m.text)}</div>`
        if (showTr) inner += `<div class="tr tr-${m.out ? 'out' : 'in'}"><span class="lb">${esc(trLb)}</span>${this.fmt(m.ru!)}</div>`
        inner += meta
      } else inner += meta
    } else if (m.kind === 'voice') {
      inner += `<div class="voice"><button class="play">${I.send}</button><div style="flex:1"><div class="vdur">Голосовое</div></div></div>${meta}`
    } else if (m.kind === 'file') {
      inner += `<div class="file"><div class="fico">${esc(m.fext || 'FILE')}</div><div><b>${esc(m.fname || 'Файл')}</b></div></div>${meta}`
    } else {
      inner += `<div class="txt">${this.fmt(m.text)}${showTr ? '' : meta}</div>`
      if (showTr) inner += `<div class="tr tr-${m.out ? 'out' : 'in'}"><span class="lb">${esc(trLb)}</span>${this.fmt(m.ru!)}${meta}</div>`
    }

    const reacts = Object.entries(m.reactions || {}).filter(([, n]) => n > 0)
    if (reacts.length) {
      inner += `<div class="reacts">${reacts.map(([em, n]) =>
        `<button type="button" class="react ${m.mine.includes(em) ? 'mine' : ''}" data-react="${m.id}|${esc(em)}">${em}${n > 1 ? ` ${n}` : ''}</button>`,
      ).join('')}</div>`
    }

    return `<div class="${cls}" data-msg="${m.id}" id="msg-${m.id}">
      <div class="ava sm" style="${avatarGradient(c.g)}">${esc(initials(c.name))}</div>
      <div class="bub ${tail ? 'tail' : ''}">${inner}</div></div>`
  }

  private fmt(t: string): string {
    const q = this.find?.q.trim()
    if (q && q.length > 1) {
      const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
      return esc(t).replace(re, (x) => `<mark>${x}</mark>`)
    }
    return esc(t).replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
  }

  /** Подгрузка медиа из blob-кэша после render. */
  private hydrateMedia(c: UiChat): void {
    for (const m of c.msgs) {
      if (!m.attachmentUrl || !m.mediaKey) continue
      if (this.ctrl.mediaUrls.has(m.mediaKey)) continue
      void this.ctrl.resolveMedia(m.mediaKey, m.attachmentUrl).then((url) => {
        if (!url) return
        const el = document.querySelector(`[data-msg-media="${m.id}"]`)
        if (el && !el.querySelector('img,video')) {
          const isVn = el.getAttribute('data-vn') === '1'
          el.innerHTML = isVn
            ? `<video class="video-note" src="${url}" autoplay loop muted playsinline></video>`
            : `<img src="${url}" alt="" loading="lazy">`
          const box = $('#msgs')
          if (box && this.scroll.stickToBottom) this.scroll.afterMessagesRender(box)
        }
      })
    }
  }

  private bindChat(c: UiChat): void {
    this.unbindScroll?.()
    const box = $('#msgs')
    if (box) {
      const onScroll = () => {
        if (
          box.scrollTop < 120 &&
          !this.olderLoadLock &&
          this.ctrl.hasMoreMessages[c.id] &&
          !this.ctrl.loadingOlder[c.id]
        ) {
          this.olderLoadLock = true
          const snap = this.scroll.captureForPrepend(box)
          void this.ctrl.loadOlderMessages(c.id).then((loaded) => {
            if (loaded) {
              this.renderMsgs(true)
              this.scroll.restoreAfterPrepend(box, snap)
            }
          }).finally(() => {
            window.setTimeout(() => { this.olderLoadLock = false }, 400)
          })
        }
      }
      this.unbindScroll = this.scroll.bindScrollContainer(box, (show) => {
        $('#scrollDown')?.classList.toggle('show', show)
        onScroll()
      })
    }

    $('#backBtn')?.addEventListener('click', () => $('#app')?.classList.remove('open'))
    $('#headAva')?.addEventListener('click', () => {
      this.pane = true
      this.ptab = 'info'
      $('#app')?.classList.add('side-open')
      this.renderPane()
    })
    $('#searchInChat')?.addEventListener('click', () => {
      this.find = { q: '', hits: [], i: 0 }
      this.renderChat()
      $('#findInp')?.focus()
    })
    $('#findClose')?.addEventListener('click', () => {
      this.find = null
      this.renderChat()
    })
    $('#findInp')?.addEventListener('input', (e) => this.findRun((e.target as HTMLInputElement).value))
    $('#findInp')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        this.findGo((e as KeyboardEvent).shiftKey ? -1 : 1)
      }
    })
    $('#findUp')?.addEventListener('click', () => this.findGo(-1))
    $('#findDown')?.addEventListener('click', () => this.findGo(1))
    $('#chatMenuBtn')?.addEventListener('click', (e) => {
      e.stopPropagation()
      this.closePops()
      const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
      this.chatMenu(c, r.right - 230, r.bottom + 6)
    })
    $('#emojiBtn')?.addEventListener('click', (e) => {
      e.stopPropagation()
      this.closePops()
      this.renderEmojiPop()
      const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
      this.showPop($('#emojiPop')!, r.left - 280, r.top - 280)
    })
    $('#openPane')?.addEventListener('click', () => this.openInfoPane())
    $('#companionBtn')?.addEventListener('click', () => this.openInfoPane())
    $('#notesBtn')?.addEventListener('click', () => {
      this.pane = true
      this.ptab = 'notes'
      $('#app')?.classList.add('side-open')
      this.renderPane()
    })
    $('#trBtn')?.addEventListener('click', () => this.openTranslation(c))
    $('#scrollDown')?.addEventListener('click', () => {
      if (box) {
        this.scroll.stickToBottom = true
        this.scroll.scrollToBottom(box, 'smooth')
      }
    })
    $('#cancelBar')?.addEventListener('click', () => {
      this.reply = null
      this.renderChat()
    })
    $('#attachBtn')?.addEventListener('click', () => this.fileInput?.click())

    const inp = $('#inp') as HTMLTextAreaElement | null
    if (inp) {
      const fit = () => {
        inp.style.height = 'auto'
        inp.style.height = `${Math.min(inp.scrollHeight, 150)}px`
      }
      fit()
      inp.addEventListener('input', () => {
        fit()
        c.draft = inp.value
      })
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault()
          void this.send(c, inp)
        }
      })
      // Фокус только при открытии чата, не при каждой перерисовке (иначе скачет курсор)
      const mobile = window.matchMedia('(max-width:900px)').matches
      if (!mobile && document.activeElement !== inp) {
        try {
          inp.focus({ preventScroll: true })
        } catch {
          inp.focus()
        }
      }
    }
    $('#sendBtn')?.addEventListener('click', () => {
      if (inp) void this.send(c, inp)
    })

    box?.addEventListener('click', (e) => {
      const react = (e.target as HTMLElement).closest('[data-react]') as HTMLElement | null
      if (react) {
        e.preventDefault()
        const [id, em] = (react.dataset.react || '').split('|')
        void this.toggleReaction(Number(id), em)
        return
      }
    })

    box?.addEventListener('contextmenu', (e) => {
      const row = (e.target as HTMLElement).closest('[data-msg]') as HTMLElement | null
      if (!row) return
      e.preventDefault()
      const m = c.msgs.find((x) => x.id === Number(row.dataset.msg))
      if (m) this.msgMenu(m, e.clientX, e.clientY)
    })

    let pressTimer: ReturnType<typeof setTimeout> | undefined
    box?.addEventListener('touchstart', (e) => {
      const row = (e.target as HTMLElement).closest('[data-msg]') as HTMLElement | null
      if (!row) return
      pressTimer = window.setTimeout(() => {
        const m = c.msgs.find((x) => x.id === Number(row.dataset.msg))
        const t = e.touches[0]
        if (m && t) this.msgMenu(m, t.clientX - 100, t.clientY - 60)
      }, 450)
    }, { passive: true })
    box?.addEventListener('touchend', () => clearTimeout(pressTimer))
    box?.addEventListener('touchmove', () => clearTimeout(pressTimer), { passive: true })
  }

  private async send(c: UiChat, inp: HTMLTextAreaElement): Promise<void> {
    const text = inp.value.trim()
    if (!text) return
    const replyTo = this.reply
    inp.value = ''
    c.draft = ''
    this.reply = null
    try {
      await this.ctrl.sendText(c.id, text, replyTo)
      this.scroll.forceBottomNext = true
      this.renderChat()
    } catch (e) {
      this.toast(e instanceof Error ? e.message : String(e))
    }
  }

  private openTranslation(c: UiChat): void {
    const auto = !c.raw.auto_translate_disabled
    const outboundVal = (c.raw.outbound_lang || '').trim() ? String(c.raw.outbound_lang).trim().toLowerCase() : 'auto'
    const langOpts = outboundLangOptions(c.raw.user_lang)
    const body = `
      <div class="f-row" data-tr="toggle"><div class="mid"><b>Автоперевод</b>
        <span>Входящие → RU, ваши ответы → язык клиента</span></div>
        <div class="sw-t ${auto ? 'on' : ''}"></div></div>
      ${auto ? `
        <div class="dr-lab" style="padding-top:6px">Язык ответа клиенту</div>
        <select class="f-in tr-lang-sel" id="outLangSel">
          ${langOpts.map((o) => `<option value="${esc(o.value)}" ${o.value === outboundVal ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}
        </select>
        <p class="tr-hint">«Авто» — по языку последних сообщений фана (${esc(replyLangDisplay(c.raw))})</p>
      ` : ''}`
    this.modal('Перевод', body, (el) => {
      el.querySelector('[data-tr="toggle"]')?.addEventListener('click', () => {
        const nextDisabled = !c.raw.auto_translate_disabled
        void this.ctrl.updateTranslation(c.id, { auto_translate_disabled: nextDisabled })
        c.raw.auto_translate_disabled = nextDisabled
        c.tr.in = !nextDisabled
        c.tr.out = !nextDisabled
        this.openTranslation(c)
      })
      el.querySelector('#outLangSel')?.addEventListener('change', (ev) => {
        const v = (ev.target as HTMLSelectElement).value
        void this.ctrl.updateTranslation(c.id, { outbound_lang: v === 'auto' ? null : v })
        c.raw.outbound_lang = v === 'auto' ? null : v
        this.renderChat()
      })
    })
  }

  /** Правая панель «Инфо» — режим бота, персонаж, язык. */
  private openInfoPane(): void {
    this.pane = true
    this.ptab = 'info'
    $('#app')?.classList.add('side-open')
    this.renderPane()
  }

  private renderPane(): void {
    const c = this.ctrl.activeChat
    const pane = $('#pane')!
    if (!c) return
    pane.style.display = 'flex'
    pane.innerHTML = `
      <div class="p-head"><button class="ic" id="closePane">${I.close}</button><b>${esc(c.name)}</b></div>
      <div class="p-tabs">
        <button class="${this.ptab === 'info' ? 'on' : ''}" data-pt="info">Инфо</button>
        <button class="${this.ptab === 'notes' ? 'on' : ''}" data-pt="notes">Заметки</button>
      </div>
      <div class="p-body">${this.ptab === 'notes' ? this.notesPane(c) : this.infoPane(c)}</div>`
    $('#closePane')?.addEventListener('click', () => {
      this.pane = false
      $('#app')?.classList.remove('side-open')
      pane.style.display = 'none'
    })
    pane.querySelectorAll('[data-pt]').forEach((b) => {
      b.addEventListener('click', () => {
        this.ptab = (b as HTMLElement).dataset.pt as 'info' | 'notes'
        this.renderPane()
      })
    })
    if (this.ptab === 'notes') {
      $('#addNote')?.addEventListener('click', () => {
        const ta = $('#noteInp') as HTMLTextAreaElement | null
        const text = ta?.value.trim()
        if (text) void this.ctrl.addNote(c.id, text).then(() => this.renderPane())
      })
      $('#analyzeNotes')?.addEventListener('click', () => {
        void this.ctrl.runNotesAnalyze(c.id).then(() => {
          this.renderPane()
          this.toast('AI-анализ добавлен в заметки')
        }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
      })
    }
    if (this.ptab === 'info') {
      pane.querySelectorAll('[data-companion]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const mode = (btn as HTMLElement).dataset.companion || 'off'
          void this.ctrl.updateSettings(c.id, { companion_mode_override: mode }).then(() => {
            this.renderPane()
            this.toast('Режим компаньона обновлён')
          }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
        })
      })
    }
  }

  private infoPane(c: UiChat): string {
    const companion = c.raw.companion_mode_override ?? c.raw.effective_companion_mode ?? 'off'
    const companionBtns = COMPANION_MODES.map((mo) =>
      `<button type="button" class="tab ${companion === mo.id ? 'on' : ''}" data-companion="${mo.id}">${mo.label}</button>`,
    ).join('')
    return `<div class="p-top">${this.avaHtml(c)}
      <h3>${esc(c.name)}</h3><p>${esc(platformMeta(c.raw.platform).name)}</p></div>
      <div class="p-list">
        <div class="p-row"><span>${I.folder}</span><div><b>Персонаж</b><span>${esc(this.personaNameForChat(c))}</span></div></div>
        <div class="p-row"><span>${I.link}</span><div><b>ID</b><span>${esc(c.handle || String(c.id))}</span></div></div>
        <div class="p-row"><span>${I.globe}</span><div><b>Язык</b><span>${esc(c.lang)}</span></div></div>
        <div class="p-row"><span>${I.info}</span><div><b>AI-компаньон</b>
          <span>Автоответчик для этого диалога. «Полуавто» — только короткие сообщения (до 320 символов).</span>
          <div class="tabs" style="margin-top:6px;flex-wrap:wrap">${companionBtns}</div></div></div>
      </div>
      <div class="p-list" style="margin-top:12px">
        <a class="f-row" href="/workspace/connections" style="text-decoration:none;color:inherit">
          <div class="mid"><b>Подключения</b><span>Telegram, Fanvue, Instagram</span></div></a>
      </div>`
  }

  private notesPane(c: UiChat): string {
    const entries = c.notes.e.map((n) =>
      `<div class="nt-e"><header><b>${esc(n.d)}</b>${n.ai ? '<span class="ai-b">AI</span>' : ''}</header><p>${esc(n.t)}</p></div>`,
    ).join('')
    return `<div class="nt-wrap">${entries || '<div class="nt-empty">Заметок пока нет.</div>'}
      <textarea class="f-in" id="noteInp" placeholder="Новая заметка…"></textarea>
      <div class="nt-foot" style="display:flex;gap:8px">
        <button class="btn-n" id="analyzeNotes" style="flex:1;background:var(--accent-soft);color:var(--accent)">✦ AI-анализ</button>
        <button class="btn-n" id="addNote" style="flex:1">Сохранить</button>
      </div></div>`
  }

  private personaNameForChat(c: UiChat): string {
    const mid = c.raw.studio_model_id
    if (mid == null) return 'Без модели'
    return this.ctrl.models.find((m) => m.id === mid)?.name || `#${mid}`
  }

  private renderPersonasBlock(): string {
    if (!this.showPersonaSwitcher()) return ''
    const rows: string[] = []
    const mk = (id: PersonaFilter, label: string, ava: string, unread: number) => {
      const on = this.activePersonaId === id
      return `<button type="button" class="dr-persona ${on ? 'on' : ''}" data-persona="${id}">
        ${ava}
        <div class="mid"><b>${esc(label)}</b><span>${unread ? `${unread} ${plural(unread, 'новое', 'новых', 'новых')}` : 'Нет новых'}</span></div>
        ${unread ? `<span class="badge">${unread > 99 ? '99+' : unread}</span>` : (on ? `<span class="tick">${I.check}</span>` : '')}
      </button>`
    }
    if (this.ctrl.models.length > 1) {
      const u = this.unreadForPersona('all')
      rows.push(mk('all', 'Все персонажи', `<div class="ava" style="${avatarGradient(5)}">${I.folder}</div>`, u))
    }
    this.ctrl.models.forEach((m, i) => {
      rows.push(mk(m.id, m.name, this.personaAvaHtml(m, i), this.unreadForPersona(m.id)))
    })
    if (this.hasUnassignedChats()) {
      rows.push(mk('none', 'Без модели', `<div class="ava" style="${avatarGradient(6)}">?</div>`, this.unreadForPersona('none')))
    }
    return `<div class="dr-lab">Персонажи</div><div class="dr-personas">${rows.join('')}</div><div class="dr-sep"></div>`
  }

  private renderDrawer(): void {
    const visibleUnread = this.ctrl.chats.filter((c) => this.inPersona(c)).reduce((a, c) => a + c.unread, 0)
    const operator = this.ctrl.me?.display_name || this.ctrl.me?.login || 'Оператор'
    const pushOn = pushSupported() && pushPermission() === 'granted'
    const activeModel = typeof this.activePersonaId === 'number'
      ? this.ctrl.models.find((m) => m.id === this.activePersonaId)
      : null
    const headAva = activeModel
      ? this.personaAvaHtml(activeModel, 0)
      : `<div class="ava" style="${avatarGradient(4)}">${esc(initials(operator))}</div>`
    $('#drawer')!.innerHTML = `
      <div class="dr-top">${headAva}
        <b>${esc(this.currentPersonaLabel())}</b>
        <span>${operator}${visibleUnread ? ` · ${visibleUnread} ${plural(visibleUnread, 'новое', 'новых', 'новых')}` : ''}</span></div>
      ${this.renderPersonasBlock()}
      <div class="dr-item" data-act="workspace">${I.folder}<span>Кабинет OS</span></div>
      <div class="dr-item" data-act="connections">${I.link}<span>Подключения</span></div>
      ${pushSupported() ? `<div class="dr-item" data-act="push">${I.bell}<span>Push-уведомления</span>
        <div class="sw-t ${pushOn ? 'on' : ''}"></div></div>` : ''}
      <div class="dr-item" data-act="night">${I.moon}<span>Ночной режим</span>
        <div class="sw-t ${this.theme === 'dark' ? 'on' : ''}"></div></div>
      <div class="dr-sep"></div>
      <div class="dr-lab">Цвет</div>
      <div class="swatches">${ACCENTS.map((a) =>
        `<div class="sw-c ${this.accent === a ? 'on' : ''}" style="background:${a}" data-acc="${a}"><i></i></div>`,
      ).join('')}</div>`
  }

  private drawer(on: boolean): void {
    $('#drawer')?.classList.toggle('on', on)
    $('#scrim')?.classList.toggle('on', on)
  }

  private drawerAct(act: string): void {
    this.drawer(false)
    if (act === 'night') {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      this.applyTheme()
      this.renderDrawer()
      this.renderChat()
    }
    if (act === 'push') {
      void this.togglePush()
      return
    }
    if (act === 'workspace') window.location.href = '/workspace/'
    if (act === 'connections') window.location.href = '/workspace/connections'
  }

  private async togglePush(): Promise<void> {
    if (!pushSupported()) {
      this.toast('Push не поддерживается в этом браузере')
      return
    }
    if (pushPermission() === 'granted') {
      await unregisterChatPush()
      this.toast('Push отключены')
    } else {
      const r = await registerChatPush()
      if (r === 'granted') this.toast('Push включены')
      else if (r === 'denied') this.toast('Разрешите уведомления в настройках браузера')
      else if (r === 'server-off') this.toast('Push не настроены на сервере')
      else this.toast('Push недоступны')
    }
    this.renderDrawer()
  }

  private msgMenu(m: UiMessage, x: number, y: number): void {
    const ctx = $('#ctx')!
    const items = [
      [I.reply, 'Ответить', 'reply'],
      (m.text || m.ru) ? [I.copy, 'Копировать', 'copy'] : null,
      (m.text || m.ru) ? [I.note, 'В заметки', 'tonote'] : null,
    ].filter(Boolean) as Array<[string, string, string]>
    ctx.innerHTML =
      `<div class="quick-r">${REACTION_EMOJIS.map((e) => `<button type="button" data-qr="${e}">${e}</button>`).join('')}</div>` +
      items.map(([ic, l, a]) => `<button type="button" data-act="${a}">${ic}<span>${l}</span></button>`).join('')
    ctx.dataset.msg = String(m.id)
    this.showPop(ctx, x, y)
  }

  private chatMenu(c: UiChat, x: number, y: number): void {
    const ctx = $('#ctx')!
    const items = [
      [I.info, 'AI-компаньон', 'companion'],
      [I.folder, 'Добавить в папку', 'folder'],
      [I.note, 'Заметки', 'notes'],
      [I.pin, c.pinned ? 'Снять VIP' : 'VIP', 'pin'],
      [I.link, c.biz ? 'Снять метку «Реклама»' : 'Пометить как рекламу', 'biz'],
      [I.trash, 'Убрать из списка', 'delete'],
    ]
    ctx.innerHTML = items.map(([ic, l, a]) =>
      `<button type="button" data-chatact="${a}" class="${a === 'delete' ? 'dgr' : ''}">${ic}<span>${l}</span></button>`,
    ).join('')
    ctx.dataset.chat = String(c.id)
    this.showPop(ctx, x, y)
  }

  private msgAct(a: string): void {
    const ctx = $('#ctx')!
    const id = Number(ctx.dataset.msg)
    const c = this.ctrl.activeChat
    const m = c?.msgs.find((x) => x.id === id)
    if (!c || !m) return
    if (a === 'reply') {
      this.reply = id
      this.renderChat()
      $('#inp')?.focus()
    }
    if (a === 'copy') {
      void navigator.clipboard?.writeText(m.ru || m.text || '').then(() => this.toast('Скопировано'))
    }
    if (a === 'tonote') {
      const snippet = (m.ru || m.text || '').slice(0, 160)
      void this.ctrl.addNote(c.id, `Из переписки (${m.time}): «${snippet}»`).then(() => {
        this.pane = true
        this.ptab = 'notes'
        $('#app')?.classList.add('side-open')
        this.renderPane()
        this.toast('Добавлено в заметки')
      })
    }
  }

  private chatAct(a: string): void {
    const ctx = $('#ctx')!
    const convId = Number(ctx.dataset.chat)
    const c = this.ctrl.chats.find((x) => x.id === convId) || this.ctrl.activeChat
    if (!c) return
    if (a === 'companion') {
      void this.openChat(c.id).then(() => this.openInfoPane())
    }
    if (a === 'folder') this.openFolderPick(c.id)
    if (a === 'notes') {
      void this.openChat(c.id).then(() => {
        this.pane = true
        this.ptab = 'notes'
        $('#app')?.classList.add('side-open')
        this.renderPane()
      })
    }
    if (a === 'pin') {
      const next = c.pinned ? null : 'vip'
      void this.ctrl.updateSettings(c.id, { manual_category: next }).then(() => {
        this.renderTabs()
        this.renderList()
        this.toast(next ? 'VIP' : 'VIP снят')
      }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
    }
    if (a === 'biz') {
      const next = c.biz ? null : 'bomzh'
      void this.ctrl.updateSettings(c.id, { manual_category: next }).then(() => {
        this.renderTabs()
        this.renderList()
        this.toast(next ? 'Помечено как реклама' : 'Метка снята')
      }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
    }
    if (a === 'delete') {
      if (!window.confirm('Убрать диалог из списка? История сохранится на сервере.')) return
      void this.ctrl.hideConversation(c.id).then(() => {
        $('#app')?.classList.remove('open')
        this.pane = false
        this.renderAll()
        this.toast('Диалог скрыт')
      }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
    }
  }

  private findRun(q: string): void {
    if (!this.find) return
    const c = this.ctrl.activeChat
    if (!c) return
    this.find.q = q
    const t = q.trim().toLowerCase()
    this.find.hits = t.length > 1
      ? c.msgs.filter((m) => (m.text || m.ru || '').toLowerCase().includes(t)).map((m) => m.id)
      : []
    this.find.i = 0
    this.renderMsgs(true)
    if (this.find.hits.length) this.gotoMsg(this.find.hits[0])
  }

  private findGo(dir: number): void {
    if (!this.find?.hits.length) return
    this.find.i = (this.find.i + dir + this.find.hits.length) % this.find.hits.length
    this.updateFindN()
    this.gotoMsg(this.find.hits[this.find.i])
  }

  private gotoMsg(msgId: number): void {
    const row = document.getElementById(`msg-${msgId}`)
    row?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    this.renderMsgs(true)
  }

  private updateFindN(): void {
    const el = $('#findN')
    if (!el || !this.find) return
    el.textContent = this.find.hits.length
      ? `${this.find.i + 1} из ${this.find.hits.length}`
      : (this.find.q.trim().length > 1 ? 'ничего не найдено' : '')
  }

  private renderEmojiPop(): void {
    $('#emojiPop')!.innerHTML =
      `<div class="em-grid">${EMOJI_QUICK.map((e) => `<button type="button" data-em="${e}">${e}</button>`).join('')}</div>`
  }

  private folderTabMenu(folderId: number, x: number, y: number): void {
    const folder = this.ctrl.folders.find((f) => f.id === folderId)
    if (!folder) return
    const ctx = $('#ctx')!
    ctx.innerHTML =
      `<button type="button" data-folder-act="rename">${I.note}<span>Переименовать «${esc(folder.name)}»</span></button>` +
      `<button type="button" data-folder-act="delete" class="dgr">${I.trash}<span>Удалить папку</span></button>`
    ctx.dataset.folderId = String(folderId)
    this.showPop(ctx, x, y)
  }

  private folderAct(act: string, folderId: number): void {
    const folder = this.ctrl.folders.find((f) => f.id === folderId)
    if (!folder) return
    if (act === 'rename') this.openFolderRename(folderId, folder.name)
    if (act === 'delete') {
      if (!window.confirm(`Удалить папку «${folder.name}»? Диалоги останутся.`)) return
      void this.ctrl.removeUserFolder(folderId).then(() => {
        if (this.folder === String(folderId)) this.folder = 'all'
        this.renderTabs()
        this.toast('Папка удалена')
      }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
    }
  }

  private openFolderRename(folderId: number, current: string): void {
    this.modal('Переименовать папку', `
      <input class="f-in" id="folderName" value="${esc(current)}" autocomplete="off">
      <div style="margin-top:12px;display:flex;justify-content:flex-end">
        <button class="btn-n" id="folderSave">Сохранить</button>
      </div>`, (el) => {
      const save = () => {
        const name = (el.querySelector('#folderName') as HTMLInputElement | null)?.value.trim()
        if (!name) return
        void this.ctrl.renameUserFolder(folderId, name).then(() => {
          this.renderTabs()
          this.toast('Папка переименована')
          el.closest('.modal-wrap')?.remove()
        }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
      }
      el.querySelector('#folderSave')?.addEventListener('click', save)
      el.querySelector('#folderName')?.addEventListener('keydown', (e) => {
        if ((e as KeyboardEvent).key === 'Enter') save()
      })
    })
  }

  private async toggleReaction(messageId: number, emoji: string): Promise<void> {
    const c = this.ctrl.activeChat
    if (!c || !messageId || !emoji) return
    try {
      await this.ctrl.toggleReaction(c.id, messageId, emoji)
      this.renderMsgs(true)
    } catch (e) {
      this.toast(e instanceof Error ? e.message : String(e))
    }
  }

  private openFolderCreate(): void {
    this.modal('Новая папка', `
      <input class="f-in" id="folderName" placeholder="Название папки" autocomplete="off">
      <div style="margin-top:12px;display:flex;justify-content:flex-end">
        <button class="btn-n" id="folderSave">Создать</button>
      </div>`, (el) => {
      const save = () => {
        const name = (el.querySelector('#folderName') as HTMLInputElement | null)?.value.trim()
        if (!name) return
        void this.ctrl.createUserFolder(name).then(() => {
          this.renderTabs()
          this.toast('Папка создана')
          el.closest('.modal-wrap')?.remove()
        }).catch((e) => this.toast(e instanceof Error ? e.message : String(e)))
      }
      el.querySelector('#folderSave')?.addEventListener('click', save)
      el.querySelector('#folderName')?.addEventListener('keydown', (e) => {
        if ((e as KeyboardEvent).key === 'Enter') save()
      })
    })
  }

  private openFolderPick(convId: number): void {
    const folders = this.ctrl.folders
    const body = folders.length
      ? folders.map((f) => {
          const inFolder = f.conversation_ids.includes(convId)
          return `<button type="button" class="f-row" data-folder-pick="${f.id}" data-conv="${convId}">
            <div class="mid"><b>${esc(f.name)}</b><span>${inFolder ? 'Убрать из папки' : 'Добавить'}</span></div></button>`
        }).join('')
      : '<div class="empty-s">Сначала создайте папку через «+» над списком.</div>'
    this.modal('Папки', body)
  }

  private async pickFolderForChat(folderId: number, convId: number): Promise<void> {
    const folder = this.ctrl.folders.find((f) => f.id === folderId)
    if (!folder) return
    try {
      if (folder.conversation_ids.includes(convId)) {
        await this.ctrl.removeChatFromFolder(folderId, convId)
        this.toast('Убрано из папки')
      } else {
        await this.ctrl.addChatToFolder(folderId, convId)
        this.toast('Добавлено в папку')
      }
      this.renderTabs()
      document.querySelector('.modal-wrap')?.remove()
    } catch (e) {
      this.toast(e instanceof Error ? e.message : String(e))
    }
  }

  applyTheme(): void {
    document.body.dataset.theme = this.theme
    document.documentElement.style.setProperty('--accent', this.accent)
    void saveUiSettings(this.theme, this.accent, this.activePersonaId)
  }

  private initStrips(): void {
    ;['wrapF', 'wrapS'].forEach((id) => {
      const wrap = document.getElementById(id) as HTMLElement | null
      if (!wrap) return
      const strip = wrap.querySelector('.tabs') as HTMLElement
      let last = ''
      const upd = () => {
        const over = strip.scrollWidth - strip.clientWidth
        const l = over > 2 && strip.scrollLeft > 2
        const r = over > 2 && strip.scrollLeft < over - 2
        const key = `${l}|${r}`
        if (key === last) return
        last = key
        wrap.classList.toggle('ov-l', l)
        wrap.classList.toggle('ov-r', r)
      }
      ;(wrap as HTMLElement & { __upd?: () => void }).__upd = upd
      strip.addEventListener('scroll', upd, { passive: true })
      window.setTimeout(upd, 0)
    })
  }

  toast(text: string): void {
    const el = document.createElement('div')
    el.className = 'toast'
    el.textContent = text
    $('#toasts')!.appendChild(el)
    window.setTimeout(() => {
      el.style.opacity = '0'
      window.setTimeout(() => el.remove(), 260)
    }, 2400)
  }

  private modal(title: string, body: string, bind?: (el: HTMLElement) => void): void {
    const wrap = document.createElement('div')
    wrap.className = 'modal-wrap'
    wrap.innerHTML = `<div class="modal-bg"></div>
      <div class="modal"><div class="modal-h"><b>${esc(title)}</b><button class="ic" id="mx">${I.close}</button></div>
      <div class="modal-b">${body}</div></div>`
    document.body.appendChild(wrap)
    const close = () => wrap.remove()
    wrap.querySelector('.modal-bg')?.addEventListener('click', close)
    wrap.querySelector('#mx')?.addEventListener('click', close)
    bind?.(wrap)
  }
}
