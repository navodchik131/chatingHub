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

interface MotionPreview {
  id: number
  video_url: string
  frame_image_url: string
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
  motionRenders: MotionPreview[]
  onOpenChat: (convId?: number) => void
  onOpenStudio: () => void
  onOpenVideo: () => void
  onOpenAccount: () => void
}

function KpiCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: ReactNode
  hint?: string
  accent?: boolean
}) {
  return (
    <article className={`dash-kpi${accent ? ' dash-kpi--accent' : ''}`}>
      <span className="dash-kpi-label">{label}</span>
      <strong className="dash-kpi-value">{value}</strong>
      {hint ? <span className="dash-kpi-hint">{hint}</span> : null}
    </article>
  )
}

function platformLabel(p: string): string {
  if (p === 'telegram') return 'Telegram'
  if (p === 'fanvue') return 'Fanvue'
  return p
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
  motionRenders,
  onOpenChat,
  onOpenStudio,
  onOpenVideo,
  onOpenAccount,
}: WorkspaceOverviewProps) {
  const recentChats = conversations.slice(0, 5)
  const recentGens = generations.slice(0, 4)
  const recentVideos = motionRenders.slice(0, 3)

  return (
    <div className="dash">
      <div className="dash-kpi-row">
        <KpiCard label="Кредиты" value={creditsBalance.toLocaleString('ru-RU')} hint={billingPlanLabel} accent />
        <KpiCard label="Подписка" value={subscriptionLabel} hint="Статус доступа" />
        {canChat ? (
          <KpiCard
            label="Диалоги"
            value={conversationsTotal}
            hint={unreadTotal > 0 ? `${unreadTotal} непрочитанных` : 'Все прочитаны'}
          />
        ) : null}
        {canStudioAny ? (
          <KpiCard label="В архиве" value={generationsTotal} hint="Сохранённые кадры" />
        ) : null}
      </div>

      <div className="dash-quick panel-glass">
        <h2 className="dash-block-title">Быстрые действия</h2>
        <div className="dash-quick-actions">
          {canChat ? (
            <button type="button" className="send-btn" onClick={() => onOpenChat()}>
              Открыть диалоги
            </button>
          ) : null}
          {canStudioAny ? (
            <>
              <button type="button" className="ghost-btn" onClick={onOpenStudio}>
                Новая картинка
              </button>
              <button type="button" className="ghost-btn" onClick={onOpenVideo}>
                Motion / видео
              </button>
            </>
          ) : null}
          <button type="button" className="ghost-btn" onClick={onOpenAccount}>
            Кабинет и интеграции
          </button>
        </div>
      </div>

      <div className="dash-grid">
        {canChat ? (
          <section className="dash-panel panel-glass">
            <div className="dash-panel-head">
              <h2 className="dash-block-title">Недавние диалоги</h2>
              <button type="button" className="dash-link-btn" onClick={() => onOpenChat()}>
                Все →
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
                        <span className="muted">{platformLabel(c.platform)}</span>
                      </span>
                      {c.last_message_preview ? (
                        <span className="dash-list-preview">{c.last_message_preview}</span>
                      ) : null}
                      {(c.unread_count ?? 0) > 0 ? (
                        <span className="dash-list-badge">{c.unread_count}</span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}

        {canStudioAny ? (
          <section className="dash-panel panel-glass">
            <div className="dash-panel-head">
              <h2 className="dash-block-title">Последние кадры</h2>
              <button type="button" className="dash-link-btn" onClick={onOpenStudio}>
                Студия →
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

        {canStudioAny ? (
          <section className="dash-panel panel-glass dash-panel--wide">
            <div className="dash-panel-head">
              <h2 className="dash-block-title">Последние видео</h2>
              <button type="button" className="dash-link-btn" onClick={onOpenVideo}>
                Motion →
              </button>
            </div>
            {recentVideos.length === 0 ? (
              <p className="muted dash-empty">Ролики появятся после шага «Сделать видео».</p>
            ) : (
              <div className="dash-video-row">
                {recentVideos.map((v) => (
                  <a
                    key={v.id}
                    className="dash-video-card"
                    href={v.video_url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    <img src={v.frame_image_url} alt="" loading="lazy" />
                    <span>Видео #{v.id}</span>
                  </a>
                ))}
              </div>
            )}
          </section>
        ) : null}
      </div>
    </div>
  )
}
