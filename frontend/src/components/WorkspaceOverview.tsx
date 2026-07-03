import type { ReactNode } from 'react'

interface ConversationPreview {
  id: number
  user_display_name: string | null
  platform: string
  last_message_preview: string | null
  unread_count?: number
}

interface GenerationPreview {
  id: number
  image_url: string
  prompt_excerpt: string | null
}

export interface WorkspaceOverviewProps {
  creditsBalance: number
  billingPlanLabel: string
  subscriptionLabel: string
  unreadTotal: number
  conversationsTotal: number
  generationsTotal: number
  canChat: boolean
  canStudioAny: boolean
  conversations: ConversationPreview[]
  generations: GenerationPreview[]
  tributeEarningsLabel?: string | null
  tributeEarningsHint?: string | null
  chatterOutboundCount?: number | null
  chatterConversationsCount?: number | null
  chatterRatingsHint?: string | null
  chatterStatsPeriod?: string | null
  isOwner?: boolean
  onOpenChat: (convId?: number) => void
  onOpenStudio: () => void
  onOpenVideo: () => void
  onOpenAccount: () => void
}

function KpiCard({
  label,
  value,
  hint,
  valueTone,
}: {
  label: string
  value: ReactNode
  hint?: string
  valueTone?: 'default' | 'success'
}) {
  return (
    <article className="dash-kpi">
      <span className="dash-kpi-label">{label}</span>
      <strong
        className={`dash-kpi-value${valueTone === 'success' ? ' dash-kpi-value--success' : ''}`}
      >
        {value}
      </strong>
      {hint ? <span className="dash-kpi-hint">{hint}</span> : null}
    </article>
  )
}

function platformLabel(p: string): string {
  if (p === 'telegram') return 'Telegram'
  if (p === 'fanvue') return 'Fanvue'
  if (p === 'instagram') return 'Instagram'
  return p
}

function subscriptionLooksActive(label: string): boolean {
  const lower = label.toLowerCase()
  return lower.includes('актив') || lower.includes('active') || lower.includes('trial')
}

export function WorkspaceOverview({
  creditsBalance,
  billingPlanLabel,
  subscriptionLabel,
  unreadTotal,
  conversationsTotal,
  generationsTotal,
  canChat,
  canStudioAny,
  conversations,
  generations,
  tributeEarningsLabel,
  tributeEarningsHint,
  chatterOutboundCount,
  chatterConversationsCount,
  chatterRatingsHint,
  chatterStatsPeriod,
  isOwner,
  onOpenChat,
  onOpenStudio,
  onOpenVideo,
  onOpenAccount,
}: WorkspaceOverviewProps) {
  const recentChats = conversations.slice(0, 5)
  const recentGens = generations.slice(0, 4)

  return (
    <div className="dash">
      <div className="dash-kpi-row">
        <KpiCard label="Кредиты" value={creditsBalance.toLocaleString('ru-RU')} hint={billingPlanLabel} />
        <KpiCard
          label="Подписка"
          value={subscriptionLabel}
          hint="Статус доступа"
          valueTone={subscriptionLooksActive(subscriptionLabel) ? 'success' : 'default'}
        />
        {canChat ? (
          <KpiCard
            label="Диалоги"
            value={conversationsTotal}
            hint={unreadTotal > 0 ? `${unreadTotal} непрочитанных` : 'Все прочитаны'}
          />
        ) : null}
        {canChat && tributeEarningsLabel ? (
          <KpiCard
            label="Tribute"
            value={tributeEarningsLabel}
            hint={tributeEarningsHint ?? 'Донаты и подписки'}
            valueTone="success"
          />
        ) : null}
        {canChat && chatterOutboundCount != null ? (
          <KpiCard
            label={isOwner ? 'Ответов команды' : 'Мои ответы'}
            value={chatterOutboundCount}
            hint={
              chatterStatsPeriod
                ? `${chatterConversationsCount ?? 0} диалогов · ${chatterStatsPeriod}`
                : `${chatterConversationsCount ?? 0} диалогов`
            }
          />
        ) : null}
        {canChat && chatterRatingsHint ? (
          <KpiCard label="AI-ответы" value={chatterRatingsHint} hint="Оценки 👍 / 👎 за период" />
        ) : null}
        {canStudioAny ? (
          <KpiCard label="В архиве" value={generationsTotal} hint="Сохранённые кадры" />
        ) : null}
      </div>

      <div className="dash-quick">
        <h2 className="dash-block-title">Быстрые действия</h2>
        <div className="dash-quick-actions">
          {canChat ? (
            <button
              type="button"
              className="dash-action-btn dash-action-btn--primary"
              onClick={() => onOpenChat()}
            >
              <span className="dash-action-btn__icon" aria-hidden>
                💬
              </span>
              Открыть диалоги
            </button>
          ) : null}
          {canStudioAny ? (
            <>
              <button
                type="button"
                className="dash-action-btn dash-action-btn--secondary"
                onClick={onOpenStudio}
              >
                <span className="dash-action-btn__icon dash-action-btn__icon--photo" aria-hidden>
                  🖼
                </span>
                Новая картинка
              </button>
              <button
                type="button"
                className="dash-action-btn dash-action-btn--secondary"
                onClick={onOpenVideo}
              >
                <span className="dash-action-btn__icon dash-action-btn__icon--video" aria-hidden>
                  🎬
                </span>
                Motion / видео
              </button>
            </>
          ) : null}
          <button
            type="button"
            className="dash-action-btn dash-action-btn--secondary"
            onClick={onOpenAccount}
          >
            <span className="dash-action-btn__icon dash-action-btn__icon--muted" aria-hidden>
              ⚙
            </span>
            Кабинет и интеграции
          </button>
        </div>
      </div>

      <div className="dash-grid">
        {canChat ? (
          <section className="dash-panel">
            <div className="dash-panel-head">
              <h2 className="dash-block-title">Недавние диалоги</h2>
              <button type="button" className="dash-link-btn" onClick={() => onOpenChat()}>
                Все
              </button>
            </div>
            {recentChats.length === 0 ? (
              <p className="muted dash-empty">Подключите Telegram или Fanvue в кабинете.</p>
            ) : (
              <ul className="dash-list">
                {recentChats.map((c) => (
                  <li key={c.id}>
                    <button type="button" className="dash-list-item" onClick={() => onOpenChat(c.id)}>
                      <span className="dash-list-main">
                        <strong>{c.user_display_name ?? 'Без имени'}</strong>
                        <span className="dash-list-platform">{platformLabel(c.platform)}</span>
                        {(c.unread_count ?? 0) > 0 ? (
                          <span className="dash-list-badge">{c.unread_count}</span>
                        ) : null}
                      </span>
                      {c.last_message_preview ? (
                        <span className="dash-list-preview">{c.last_message_preview}</span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        {canStudioAny ? (
          <section className="dash-panel">
            <div className="dash-panel-head">
              <h2 className="dash-block-title">Последние кадры</h2>
              <button type="button" className="dash-link-btn" onClick={onOpenStudio}>
                Студия
              </button>
            </div>
            {recentGens.length === 0 ? (
              <p className="muted dash-empty">Сгенерируйте первый кадр во вкладке «Картинки».</p>
            ) : (
              <div className="dash-thumb-grid">
                {recentGens.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    className="dash-thumb"
                    onClick={onOpenStudio}
                    title={g.prompt_excerpt ?? undefined}
                  >
                    <img src={g.image_url} alt="" loading="lazy" />
                  </button>
                ))}
              </div>
            )}
          </section>
        ) : null}
      </div>
    </div>
  )
}
