/**
 * Unibox UI — рендер и события, данные из ChatController + кэш медиа.
 */

import type { ChatController } from '../store/ChatController'
import type { UiChat, UiMessage } from '../types'
import { esc, initials, avatarGradient, plural } from '../lib/format'
import { platformMeta, platformIconImg, SOURCE_TABS } from '../lib/platforms'
import { previewText, chatSubTitle } from '../lib/mapMessage'
import { loadUiSettings, saveUiSettings } from '../cache/threadCache'
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

  private scroll = new ThreadScroll()
  private unbindScroll: (() => void) | null = null
  private fileInput: HTMLInputElement | null = null

  constructor(private ctrl: ChatController) {}

  async mount(): Promise<void> {
    document.querySelectorAll('.edge.l').forEach((b) => { b.innerHTML = I.chevL })
    document.querySelectorAll('.edge.r').forEach((b) => { b.innerHTML = I.chevR })
    $('#addFolder')!.innerHTML = I.folderPlus

    const saved = await loadUiSettings()
    if (saved) {
      this.theme = saved.theme === 'dark' ? 'dark' : 'light'
      this.accent = saved.accent || this.accent
    }
    this.applyTheme()

    this.ctrl.subscribe(() => this.renderAll())
    this.bindGlobal()
    this.initStrips()
    this.renderAll()
  }

  private renderAll(): void {
    this.renderTabs()
    this.renderList()
    this.renderChat()
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
      if (!t.closest('.pop')) $$('.pop').forEach((p) => p.classList.remove('on'))

      const chatEl = t.closest('[data-chat]')
      if (chatEl && !t.closest('.pop')) {
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
      const u = this.ctrl.chats.filter((c) => this.inSrc(c) && this.matchFolderId(c, f.id)).reduce((a, c) => a + c.unread, 0)
      return tab(f.id, f.n, u, this.folder === f.id)
    })
    const custom = this.ctrl.folders.map((f) => {
      const u = this.ctrl.chats.filter((c) => f.conversation_ids.includes(c.id) && this.inSrc(c)).reduce((a, c) => a + c.unread, 0)
      return tab(String(f.id), f.name, u, this.folder === String(f.id))
    })
    $('#folders')!.innerHTML = folderTabs.join('') + custom.join('')

    const srcTab = (id: string, name: string, color: string | null, unread: number, on: boolean) => {
      const glyph = color ? `<span class="s-ic" style="color:${color}">${platformIconImg(id === 'tg' ? 'telegram' : id === 'fv' ? 'fanvue' : 'instagram', 17)}</span>` : ''
      return `<button class="tab ${on ? 'on' : ''}" data-src="${esc(id)}" title="${esc(name)}">${glyph}${on || !color ? esc(name) : ''}${unread ? `<i>${unread > 99 ? '99+' : unread}</i>` : ''}</button>`
    }

    const srcUnread = (id: string) =>
      this.ctrl.chats.filter((c) => this.inFolder(c) && (id === 'all' || c.src === id)).reduce((a, c) => a + c.unread, 0)

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
    let list = this.ctrl.chats.filter((c) => this.inFolder(c) && this.inSrc(c))
    if (q) list = list.filter((c) => c.name.toLowerCase().includes(q) || c.handle.toLowerCase().includes(q))
    list = [...list].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))

    const activeId = this.ctrl.activeChatId
    const html = list.map((c) => {
      const m = c.msgs[c.msgs.length - 1] || null
      const ticks = m && m.out ? `<span class="ticks">${I.checks}</span>` : ''
      return `<div class="row ${activeId === c.id ? 'on' : ''}" data-chat="${c.id}">
        ${this.avaHtml(c)}
        <div class="mid">
          <div class="r1"><span class="nm">${esc(c.name)}</span>
            <span class="time">${ticks}${m ? esc(m.time) : ''}</span></div>
          <div class="r2">
            <span class="last">${esc(previewText(m))}</span>
            ${c.unread ? `<span class="badge">${c.unread > 99 ? '99+' : c.unread}</span>` : ''}
          </div>
        </div>
      </div>`
    }).join('')

    $('#list')!.innerHTML = html || '<div class="empty-s">Нет диалогов.<br>Подключите соцсети в кабинете.</div>'
  }

  async openChat(convId: number): Promise<void> {
    this.reply = null
    this.scroll.onThreadOpen()
    $('#app')?.classList.add('open')
    await this.ctrl.openChat(convId)
    this.renderAll()
  }

  private renderChat(): void {
    const c = this.ctrl.activeChat
    const pane = $('#chatPane')!
    if (!c) {
      pane.innerHTML = `<div style="flex:1;display:grid;place-items:center;color:var(--txt-2);font-size:14px">Выберите диалог</div>`
      return
    }

    const sub = chatSubTitle(c)
    const trOn = c.tr.in || c.tr.out
    pane.innerHTML = `
      <header class="head">
        <button class="ic back" id="backBtn">${I.back}</button>
        <span id="headAva" style="cursor:pointer">${this.avaHtml(c, true)}</span>
        <div class="t" id="openPane">
          <div class="h-nm">${esc(c.name)}</div>
          <div class="h-sub">${esc(sub.t)} ${trOn ? `<span class="tr-chip">${esc(c.tr.lang.toUpperCase())} ⇄ RU</span>` : ''}</div>
        </div>
        <button class="ic" id="notesBtn" title="Заметки">${I.note}</button>
        <button class="ic" id="trBtn" title="Перевод">${I.globe}</button>
        <a class="ic" href="/workspace/connections" title="Подключения">${I.link}</a>
      </header>
      <div class="msgs" id="msgs"></div>
      <button class="scroll-down" id="scrollDown">${I.down}</button>
      <div class="comp">
        ${this.reply ? this.replyBar(c) : ''}
        <div class="crow">
          <button class="ic" id="attachBtn" title="Фото">${I.clip}</button>
          <textarea class="inp" id="inp" rows="1" placeholder="Сообщение…">${esc(c.draft || '')}</textarea>
          <button class="send" id="sendBtn" title="Отправить">${I.send}</button>
        </div>
        ${c.tr.out && c.tr.lang !== 'ru' ? `<div class="out-tr">${I.globe} Ответ уйдёт на ${esc(c.tr.lang.toUpperCase())}</div>` : ''}
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
      html += this.msgHtml(m, c, !sameTail)
    })

    box.innerHTML = html
    this.hydrateMedia(c)
    this.scroll.afterMessagesRender(box, { keepPosition: keepPosition })

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

  private msgHtml(m: UiMessage, c: UiChat, tail: boolean): string {
    const cls = ['mrow', m.out ? 'out' : '', tail ? '' : '', m.pending ? 'pending' : ''].filter(Boolean).join(' ')
    const showTr = c.tr.in && m.ru && !m.out
    const meta = `<span class="meta">${esc(m.time)}${m.pending ? ' …' : ''}</span>`
    let inner = ''

    if (m.replyTo) {
      const r = c.msgs.find((x) => x.id === m.replyTo)
      inner += `<div class="reply"><div class="rb"></div><div><b>${esc(c.name)}</b><span>${esc(previewText(r || null).slice(0, 60))}</span></div></div>`
    }

    if (m.kind === 'photo' || m.kind === 'video_note') {
      const mediaSrc = m.mediaKey ? this.ctrl.mediaUrls.get(m.mediaKey) : m.attachmentUrl
      inner += `<div class="photo" data-msg-media="${m.id}">
        ${mediaSrc ? `<img src="${mediaSrc}" alt="" loading="lazy">` : '<span style="padding:20px;display:block">…</span>'}
      </div>`
      if (m.text) inner += `<div class="txt">${this.fmt(m.text)}</div>${showTr ? `<div class="tr"><span class="lb">RU</span>${this.fmt(m.ru!)}</div>` : ''}${meta}`
      else inner += meta
    } else if (m.kind === 'voice') {
      inner += `<div class="voice"><button class="play">${I.send}</button><div style="flex:1"><div class="vdur">Голосовое</div></div></div>${meta}`
    } else if (m.kind === 'file') {
      inner += `<div class="file"><div class="fico">${esc(m.fext || 'FILE')}</div><div><b>${esc(m.fname || 'Файл')}</b></div></div>${meta}`
    } else {
      inner += `<div class="txt">${this.fmt(m.text)}${showTr ? '' : meta}</div>`
      if (showTr) inner += `<div class="tr"><span class="lb">RU</span>${this.fmt(m.ru!)}${meta}</div>`
    }

    return `<div class="${cls}" data-msg="${m.id}" id="msg-${m.id}">
      <div class="ava sm" style="${avatarGradient(c.g)}">${esc(initials(c.name))}</div>
      <div class="bub ${tail ? 'tail' : ''}">${inner}</div></div>`
  }

  private fmt(t: string): string {
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
          el.innerHTML = `<img src="${url}" alt="" loading="lazy">`
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
      this.unbindScroll = this.scroll.bindScrollContainer(box, (show) => {
        $('#scrollDown')?.classList.toggle('show', show)
      })
    }

    $('#backBtn')?.addEventListener('click', () => $('#app')?.classList.remove('open'))
    $('#openPane')?.addEventListener('click', () => {
      this.pane = true
      this.ptab = 'info'
      $('#app')?.classList.add('side-open')
      this.renderPane()
    })
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
      if (!window.matchMedia('(max-width:900px)').matches) inp.focus()
    }
    $('#sendBtn')?.addEventListener('click', () => {
      if (inp) void this.send(c, inp)
    })
  }

  private async send(c: UiChat, inp: HTMLTextAreaElement): Promise<void> {
    const text = inp.value.trim()
    if (!text) return
    inp.value = ''
    c.draft = ''
    this.reply = null
    try {
      await this.ctrl.sendText(c.id, text, this.reply)
      this.scroll.forceBottomNext = true
      this.renderChat()
    } catch (e) {
      this.toast(e instanceof Error ? e.message : String(e))
    }
  }

  private openTranslation(c: UiChat): void {
    const auto = !c.raw.auto_translate_disabled
    const body = `
      <div class="f-row" data-tr="in"><div class="mid"><b>Автоперевод входящих</b></div>
        <div class="sw-t ${auto ? 'on' : ''}"></div></div>
      <div class="f-row" data-tr="out"><div class="mid"><b>Переводить мои ответы</b></div>
        <div class="sw-t ${auto ? 'on' : ''}"></div></div>`
    this.modal('Перевод', body, (el) => {
      el.querySelectorAll('[data-tr]').forEach((r) => {
        r.addEventListener('click', () => {
          const on = !c.raw.auto_translate_disabled
          void this.ctrl.updateTranslation(c.id, { auto_translate_disabled: on })
          c.raw.auto_translate_disabled = on
          r.querySelector('.sw-t')?.classList.toggle('on', !on)
        })
      })
    })
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
    }
  }

  private infoPane(c: UiChat): string {
    return `<div class="p-top">${this.avaHtml(c)}
      <h3>${esc(c.name)}</h3><p>${esc(platformMeta(c.raw.platform).name)}</p></div>
      <div class="p-list">
        <div class="p-row"><span>${I.link}</span><div><b>ID</b><span>${esc(c.handle || String(c.id))}</span></div></div>
        <div class="p-row"><span>${I.globe}</span><div><b>Язык</b><span>${esc(c.lang)}</span></div></div>
      </div>`
  }

  private notesPane(c: UiChat): string {
    const entries = c.notes.e.map((n) =>
      `<div class="nt-e"><header><b>${esc(n.d)}</b>${n.ai ? '<span class="ai-b">AI</span>' : ''}</header><p>${esc(n.t)}</p></div>`,
    ).join('')
    return `<div class="nt-wrap">${entries || '<div class="nt-empty">Заметок пока нет.</div>'}
      <textarea class="f-in" id="noteInp" placeholder="Новая заметка…"></textarea>
      <div class="nt-foot"><button class="btn-n" id="addNote">Сохранить</button></div></div>`
  }

  private renderDrawer(): void {
    const total = this.ctrl.chats.reduce((a, c) => a + c.unread, 0)
    const name = this.ctrl.me?.display_name || this.ctrl.me?.login || 'Оператор'
    $('#drawer')!.innerHTML = `
      <div class="dr-top"><div class="ava" style="${avatarGradient(4)}">${esc(initials(name))}</div>
        <b>${esc(name)}</b><span>${total} ${plural(total, 'новое', 'новых', 'новых')}</span></div>
      <div class="dr-sep"></div>
      <div class="dr-item" data-act="workspace">${I.folder}<span>Кабинет OS</span></div>
      <div class="dr-item" data-act="connections">${I.link}<span>Подключения</span></div>
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
    if (act === 'workspace') window.location.href = '/workspace/'
    if (act === 'connections') window.location.href = '/workspace/connections'
  }

  applyTheme(): void {
    document.body.dataset.theme = this.theme
    document.documentElement.style.setProperty('--accent', this.accent)
    void saveUiSettings(this.theme, this.accent)
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
