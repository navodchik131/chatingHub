import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { AdminBarChart, AdminHBarChart } from './AdminBarChart'
import { AdminDonutChart, AdminShareBars } from './AdminDonutChart'
import { AdminDrillableKpi, AdminDrillLink } from './AdminDrillableKpi'
import { AdminRevenueChart } from './AdminRevenueChart'
import {
  subscriptionStatusLabel,
  usageKindLabel,
} from './constants'
import type { AdminStats } from './types'
import { formatRub } from './utils'

export function AdminOverview({
  stats,
  onDrill,
}: {
  stats: AdminStats
  onDrill: (segment: string, title: string) => void
}) {
  const { t } = useTranslation('admin')
  const eng = stats.engagement
  const monthChange =
    stats.revenue_month_change_pct > 0
      ? t('overview.kpi.revenueMonthUp', { pct: stats.revenue_month_change_pct })
      : stats.revenue_month_change_pct < 0
        ? t('overview.kpi.revenueMonthDown', { pct: Math.abs(stats.revenue_month_change_pct) })
        : t('overview.kpi.revenueMonthFlat')

  const statusItems = stats.subscriptions_by_status.map((s) => ({
    label: subscriptionStatusLabel(s.label) || s.label,
    count: s.count,
  }))

  const kpis: Array<{
    label: string
    value: string
    hint: ReactNode
    tone: 'default' | 'success' | 'accent' | 'pink' | 'purple' | 'warn'
    segment?: string
    drillTitle?: string
  }> = [
    {
      label: t('overview.kpi.users'),
      value: stats.total_users.toLocaleString('ru-RU'),
      hint: t('overview.kpi.usersHint', {
        owners: stats.workspace_owners,
        members: stats.workspace_members,
      }),
      tone: 'default' as const,
    },
    {
      label: t('overview.kpi.paymentsTotal'),
      value: stats.payments_total.toLocaleString('ru-RU'),
      hint: t('overview.kpi.paymentsTotalHint'),
      tone: 'default' as const,
      segment: 'yookassa_payments' as const,
      drillTitle: t('overview.drill.yookassaPayments'),
    },
    {
      label: t('overview.kpi.activeSubscriptions'),
      value: eng.paid_active_owners.toLocaleString('ru-RU'),
      hint: t('overview.kpi.activeSubscriptionsHint', { pct: eng.paid_active_pct }),
      tone: 'success' as const,
      segment: 'paid_active' as const,
      drillTitle: t('overview.drill.paidActive'),
    },
    {
      label: t('overview.kpi.revenueTotal'),
      value: formatRub(stats.revenue_total_rub),
      hint: t('overview.kpi.revenueTotalHint'),
      tone: 'accent' as const,
    },
    {
      label: t('overview.kpi.revenueMonth'),
      value: formatRub(stats.revenue_month_rub),
      hint: monthChange,
      tone: 'accent' as const,
    },
    {
      label: t('overview.kpi.donationsTotal'),
      value: formatRub(stats.donations_total_rub),
      hint: t('overview.kpi.donationsTotalHint', { count: stats.donations_count }),
      tone: 'pink' as const,
    },
    {
      label: t('overview.kpi.generationsTotal'),
      value: stats.studio_generations_total.toLocaleString('ru-RU'),
      hint: t('overview.kpi.archiveHint', {
        images: stats.studio_images_total,
        videos: stats.studio_videos_total,
        motion: stats.studio_motion_renders_total,
      }),
      tone: 'purple' as const,
    },
    {
      label: t('overview.engagement.zombie'),
      value: `${eng.zombie_owners} (${eng.zombie_pct}%)`,
      hint: (
        <>
          {t('overview.engagement.engagedEver')}{' '}
          <AdminDrillLink
            segment="engaged_ever"
            title={t('overview.drill.engagedEver')}
            count={eng.engaged_owners_ever}
            onDrill={onDrill}
          >
            {eng.engaged_owners_ever}
          </AdminDrillLink>
        </>
      ),
      tone: 'warn' as const,
      segment: 'zombie' as const,
      drillTitle: t('overview.drill.zombie'),
    },
  ]

  return (
    <div className="admin-overview admin-fade-in">
      <div className="admin-kpi-grid admin-kpi-grid--hero">
        {kpis.map((kpi) => {
          const inner = (
            <>
              <span className="admin-kpi__label">{kpi.label}</span>
              <strong className={`admin-kpi__value admin-kpi__value--${kpi.tone}`}>{kpi.value}</strong>
              <span className="admin-kpi__hint">{kpi.hint}</span>
            </>
          )
          if (kpi.segment) {
            return (
              <AdminDrillableKpi
                key={kpi.label}
                segment={kpi.segment}
                title={kpi.drillTitle ?? kpi.label}
                count={0}
                onDrill={onDrill}
                className={`admin-kpi admin-kpi--${kpi.tone}`}
              >
                {inner}
              </AdminDrillableKpi>
            )
          }
          return (
            <div key={kpi.label} className={`admin-kpi admin-kpi--${kpi.tone}`}>
              {inner}
            </div>
          )
        })}
      </div>

      <div className="admin-two-col">
        <AdminRevenueChart series={stats.revenue_by_month} />
        <AdminShareBars
          title={t('overview.charts.topPlans')}
          items={stats.top_plans}
          emptyHint={t('overview.charts.noData')}
        />
      </div>

      <div className="admin-two-col">
        <AdminDonutChart items={stats.generations_by_type} total={stats.studio_generations_total} />
        <AdminShareBars
          title={t('overview.charts.topEngines')}
          items={stats.top_engines}
          emptyHint={t('overview.charts.noEngines')}
        />
      </div>

      {eng ? (
        <section className="admin-section admin-card">
          <h2 className="admin-section-title">{t('overview.engagement.title')}</h2>
          <p className="admin-section-lead muted">{t('overview.engagement.dek')}</p>
          <div className="admin-kpi-grid admin-kpi-grid--engagement">
            <AdminDrillableKpi
              segment="active_7d"
              title={t('overview.drill.active7d')}
              count={eng.active_owners_7d}
              onDrill={onDrill}
              className="admin-kpi admin-kpi--highlight"
            >
              <span className="admin-kpi__label">{t('overview.engagement.active7d')}</span>
              <strong className="admin-kpi__value">
                {eng.active_owners_7d}
                <span className="admin-kpi__pct"> ({eng.active_owners_7d_pct}%)</span>
              </strong>
            </AdminDrillableKpi>
            <AdminDrillableKpi
              segment="active_30d"
              title={t('overview.drill.active30d')}
              count={eng.active_owners_30d}
              onDrill={onDrill}
              className="admin-kpi admin-kpi--highlight"
            >
              <span className="admin-kpi__label">{t('overview.engagement.active30d')}</span>
              <strong className="admin-kpi__value">
                {eng.active_owners_30d}
                <span className="admin-kpi__pct"> ({eng.active_owners_30d_pct}%)</span>
              </strong>
            </AdminDrillableKpi>
            <AdminDrillableKpi
              segment="paid_or_trialing"
              title={t('overview.drill.paidOrTrialing')}
              count={eng.paid_or_trialing_owners}
              onDrill={onDrill}
            >
              <span className="admin-kpi__label">{t('overview.engagement.paidOrTrialing')}</span>
              <strong className="admin-kpi__value">
                {eng.paid_or_trialing_owners}
                <span className="admin-kpi__pct"> ({eng.paid_or_trialing_pct}%)</span>
              </strong>
              <span className="admin-kpi__hint">
                <AdminDrillLink
                  segment="trialing"
                  title={t('overview.drill.trialing')}
                  count={eng.trialing_owners}
                  onDrill={onDrill}
                >
                  trial {eng.trialing_owners}
                </AdminDrillLink>
                {' · '}
                <AdminDrillLink
                  segment="past_due"
                  title={t('overview.drill.pastDue')}
                  count={eng.past_due_owners}
                  onDrill={onDrill}
                >
                  past_due {eng.past_due_owners}
                </AdminDrillLink>
              </span>
            </AdminDrillableKpi>
            <AdminDrillableKpi
              segment="registered_30d"
              title={t('overview.drill.registered30d')}
              count={eng.registered_owners_30d}
              onDrill={onDrill}
            >
              <span className="admin-kpi__label">{t('overview.engagement.registered30d')}</span>
              <strong className="admin-kpi__value">{eng.registered_owners_30d}</strong>
            </AdminDrillableKpi>
            <AdminDrillableKpi
              segment="yookassa_credits_buyers"
              title={t('overview.drill.yookassaCreditsBuyers')}
              count={eng.owners_yookassa_credits_buyers}
              onDrill={onDrill}
            >
              <span className="admin-kpi__label">{t('overview.engagement.yookassaCreditsBuyers')}</span>
              <strong className="admin-kpi__value">{eng.owners_yookassa_credits_buyers}</strong>
            </AdminDrillableKpi>
            <div className="admin-kpi admin-kpi--split">
              <span className="admin-kpi__label">{t('overview.engagement.studioChat')}</span>
              <div className="admin-kpi__split-vals">
                <AdminDrillLink
                  segment="owners_with_studio"
                  title={t('overview.drill.ownersWithStudio')}
                  count={eng.owners_with_studio}
                  onDrill={onDrill}
                >
                  <strong className="admin-kpi__value">{eng.owners_with_studio}</strong>
                  <span className="admin-kpi__hint">{t('overview.engagement.studio')}</span>
                </AdminDrillLink>
                <span className="admin-kpi__split-sep">/</span>
                <AdminDrillLink
                  segment="owners_with_chat"
                  title={t('overview.drill.ownersWithChat')}
                  count={eng.owners_with_chat}
                  onDrill={onDrill}
                >
                  <strong className="admin-kpi__value">{eng.owners_with_chat}</strong>
                  <span className="admin-kpi__hint">{t('overview.engagement.chats')}</span>
                </AdminDrillLink>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {stats.activation_funnel && stats.activation_funnel.registered > 0 ? (
        <section className="admin-section admin-card">
          <h2 className="admin-section-title">
            {t('overview.funnel.title', { days: stats.activation_funnel.days })}
          </h2>
          <p className="admin-section-lead muted">{t('overview.funnel.lead')}</p>
          <div className="admin-funnel">
            {stats.activation_funnel.steps.map((step) => (
              <div key={step.key} className="admin-funnel__row">
                <div className="admin-funnel__label">{step.label}</div>
                <div className="admin-funnel__bar-wrap">
                  <div
                    className="admin-funnel__bar"
                    style={{ width: `${Math.max(step.pct_of_registered, 2)}%` }}
                  />
                </div>
                <div className="admin-funnel__meta mono">
                  {step.count}{' '}
                  <span className="admin-kpi__pct">({step.pct_of_registered}%)</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="admin-charts-grid">
        <AdminBarChart title={t('overview.charts.registrations')} series={stats.registrations_by_day} />
        <AdminBarChart title={t('overview.charts.generations')} series={stats.generations_by_day} />
        <AdminHBarChart title={t('overview.charts.subscriptionsByStatus')} items={statusItems} />
        <AdminHBarChart
          title={t('overview.charts.subscriptionsByPlan')}
          items={stats.subscriptions_by_plan}
        />
      </div>

      {Object.keys(stats.usage_by_kind).length > 0 ? (
        <section className="admin-section admin-card">
          <h2 className="admin-section-title">{t('overview.usage.title')}</h2>
          <ul className="admin-usage-list">
            {Object.entries(stats.usage_by_kind)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 20)
              .map(([k, c]) => (
                <li key={k}>
                  <span>{usageKindLabel(k)}</span>
                  <span className="mono">{c}</span>
                </li>
              ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
