/**
 * Скролл треда: при открытии чата — всегда вниз (последнее сообщение).
 * Если пользователь листает вверх — не дёргаем, пока сам не вернётся к низу.
 */

const BOTTOM_THRESHOLD = 72

export class ThreadScroll {
  /** Пользователь у низа ленты. */
  stickToBottom = true
  /** Принудительный скролл вниз после смены чата / первого рендера. */
  forceBottomNext = false

  updateFromScroll(el: HTMLElement): void {
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    this.stickToBottom = dist <= BOTTOM_THRESHOLD
  }

  scrollToBottom(el: HTMLElement, behavior: ScrollBehavior = 'auto'): void {
    if (el.scrollTo) {
      el.scrollTo({ top: el.scrollHeight, behavior })
    } else {
      el.scrollTop = el.scrollHeight
    }
  }

  /** Вызывать после каждого renderMsgs. */
  afterMessagesRender(el: HTMLElement | null, opts?: { keepPosition?: boolean }): void {
    if (!el) return
    const force = this.forceBottomNext
    if (force) this.forceBottomNext = false

    if (opts?.keepPosition && !force && !this.stickToBottom) {
      this.updateFromScroll(el)
      return
    }

    if (force || this.stickToBottom) {
      this.stickToBottom = true
      this.scrollToBottom(el, 'auto')
      requestAnimationFrame(() => this.scrollToBottom(el, 'auto'))
      window.setTimeout(() => this.scrollToBottom(el, 'auto'), 50)
      window.setTimeout(() => this.scrollToBottom(el, 'auto'), 250)
    }
  }

  onThreadOpen(): void {
    this.stickToBottom = true
    this.forceBottomNext = true
  }

  onNewMessageWhileOpen(el: HTMLElement | null): void {
    if (!el || !this.stickToBottom) return
    this.afterMessagesRender(el)
  }

  bindScrollContainer(el: HTMLElement, onShowScrollDown: (show: boolean) => void): () => void {
    const onScroll = () => {
      this.updateFromScroll(el)
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight
      onShowScrollDown(dist > 300 && el.scrollHeight > el.clientHeight + 300)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    const ro = new ResizeObserver(() => {
      if (this.stickToBottom) this.scrollToBottom(el, 'auto')
      else onScroll()
    })
    ro.observe(el)
    onScroll()
    return () => {
      el.removeEventListener('scroll', onScroll)
      ro.disconnect()
    }
  }
}
