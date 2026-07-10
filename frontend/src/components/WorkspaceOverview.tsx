import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { formatAppNumber } from '../i18n'

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
  tributeConfigured?: boolean
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
  tributeConfigured,
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
  const { t } = useTranslation('workspace')
  const recentChats = conversations.slice(0, 5)
  const recentGens = generations.slice(0, 4)

  return (
    <div className="dash">
      <div className="dash-kpi-row">
        <KpiCard
          label={t('overview.credits')}
          value={formatAppNumber(creditsBalance)}
          hint={billingPlanLabel}
        />
        <KpiCard
          label={t('overview.subscription')}
          value={subscriptionLabel}
          hint={t('overview.accessStatus')}
          valueTone={subscriptionLooksActive(subscriptionLabel) ? 'success' : 'default'}
        />
        {canChat ? (
          <KpiCard
            label={t('overview.dialogs')}
            value={conversationsTotal}
            hint={unreadTotal > 0 ? t('overview.unread', { count: unreadTotal }) : t('overview.allRead')}
          />
        ) : null}
        {canChat && (tributeEarningsLabel || tributeConfigured) ? (
          <KpiCard
            label={t('overview.tribute')}
            value={tributeEarningsLabel ?? '—'}
            hint={tributeEarningsHint ?? t('overview.tributeHint')}
            valueTone="success"
          />
        ) : null}
        {canChat && chatterOutboundCount != null ? (
          <KpiCard
            label={isOwner ? t('overview.teamReplies') : t('overview.myReplies')}
            value={chatterOutboundCount}
            hint={
              chatterStatsPeriod
                ? t('overview.dialogsPeriod', {
                    count: chatterConversationsCount ?? 0,
                    period: chatterStatsPeriod,
                  })
                : t('overview.dialogsCount', { count: chatterConversationsCount ?? 0 })
            }
          />
        ) : null}
        {canChat && chatterRatingsHint ? (
          <KpiCard label={t('overview.aiReplies')} value={chatterRatingsHint} hint={t('overview.aiRatingsHint')} />
        ) : null}
        {canStudioAny ? (
          <KpiCard label={t('overview.archive')} value={generationsTotal} hint={t('overview.savedFrames')} />
        ) : null}
      </div>

      <div className="dash-quick">
        <h2 className="dash-block-title">{t('overview.quickActions')}</h2>
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
              {t('overview.openChat')}
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
                {t('overview.newImage')}
              </button>
              <button
                type="button"
                className="dash-action-btn dash-action-btn--secondary"
                onClick={onOpenVideo}
              >
                <span className="dash-action-btn__icon dash-action-btn__icon--video" aria-hidden>
                  🎬
                </span>
                {t('overview.motionVideo')}
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
            {t('overview.cabinetIntegrations')}
          </button>
        </div>
      </div>

      <div className="dash-grid">
        {canChat ? (
          <section className="dash-panel">
            <div className="dash-panel-head">
              <h2 className="dash-block-title">{t('overview.recentChats')}</h2>
              <button type="button" className="dash-link-btn" onClick={() => onOpenChat()}>
                {t('overview.openAll')}
              </button>
            </div>
            {recentChats.length === 0 ? (
              <p className="muted dash-empty">{t('overview.emptyChats')}</p>
            ) : (
              <ul className="dash-list">
                {recentChats.map((c) => (
                  <li key={c.id}>
                    <button type="button" className="dash-list-item" onClick={() => onOpenChat(c.id)}>
                      <span className="dash-list-main">
                        <strong>{c.user_display_name ?? t('overview.unnamed')}</strong>
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
              <h2 className="dash-block-title">{t('overview.recentGenerations')}</h2>
              <button type="button" className="dash-link-btn" onClick={onOpenStudio}>
                {t('overview.studio')}
              </button>
            </div>
            {recentGens.length === 0 ? (
              <p className="muted dash-empty">{t('overview.emptyGenerations')}</p>
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
