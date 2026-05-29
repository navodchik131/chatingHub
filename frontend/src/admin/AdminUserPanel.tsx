import { useState } from 'react'
import { apiFetch } from '../api'
import { formatHttpApiError } from '../apiErrors'
import {
  BILLING_PLAN_OPTIONS,
  PLAN_TIER_OPTIONS,
  SUBSCRIPTION_STATUS_LABELS,
  SUBSCRIPTION_STATUS_OPTIONS,
  billingPlanLabel,
  planTierLabel,
} from './constants'
import type { AdminUserDetail, AdminUserRow } from './types'
import {
  datetimeLocalInputToIsoUtc,
  formatDateTimeRu,
  isoToDatetimeLocalValue,
} from './utils'

export function AdminUserPanel({
  user,
  busy,
  onBusy,
  onUpdated,
  onClose,
  onError,
}: {
  user: AdminUserDetail
  busy: boolean
  onBusy: (v: boolean) => void
  onUpdated: (row: AdminUserRow) => void
  onClose: () => void
  onError: (msg: string | null) => void
}) {
  const [creditDelta, setCreditDelta] = useState('')
  const isOwner = user.parent_user_id == null
  const periodKey = `admin-panel-period-${user.id}-${user.subscription_period_end ?? 'none'}`

  const patchSubscription = async (patch: {
    status?: string
    billing_plan?: string
    plan_tier?: string
    current_period_end?: string | null
  }) => {
    onError(null)
    onBusy(true)
    try {
      const body: Record<string, string | null> = {}
      if (patch.status !== undefined) body.status = patch.status
      if (patch.billing_plan !== undefined) body.billing_plan = patch.billing_plan
      if (patch.plan_tier !== undefined) body.plan_tier = patch.plan_tier
      if (patch.current_period_end !== undefined) body.current_period_end = patch.current_period_end
      const r = await apiFetch(`/api/admin/users/${user.id}/subscription`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        onError(formatHttpApiError(r, j))
        return
      }
      const detail = await apiFetch(`/api/admin/users/${user.id}`)
      if (detail.ok) onUpdated((await detail.json()) as AdminUserDetail)
    } finally {
      onBusy(false)
    }
  }

  const patchUser = async (body: { is_active?: boolean; is_platform_admin?: boolean }) => {
    onError(null)
    const r = await apiFetch(`/api/admin/users/${user.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      onError(formatHttpApiError(r, j))
      return
    }
    onUpdated((await r.json()) as AdminUserRow)
  }

  const applyCredits = async () => {
    const delta = parseInt(creditDelta, 10)
    if (Number.isNaN(delta) || delta === 0) {
      onError('Укажите целое число кредитов (не 0).')
      return
    }
    onError(null)
    onBusy(true)
    try {
      const r = await apiFetch(`/api/admin/users/${user.id}/credits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta, note: 'admin panel' }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        onError(formatHttpApiError(r, j))
        return
      }
      setCreditDelta('')
      const detail = await apiFetch(`/api/admin/users/${user.id}`)
      if (detail.ok) onUpdated((await detail.json()) as AdminUserDetail)
    } finally {
      onBusy(false)
    }
  }

  return (
    <aside className="admin-panel" aria-label="Карточка пользователя">
      <div className="admin-panel__head">
        <div>
          <h2 className="admin-panel__title">{user.email}</h2>
          <p className="admin-panel__meta muted">
            ID {user.id} · {isOwner ? 'владелец' : `участник · ${user.member_login ?? '—'}`}
          </p>
        </div>
        <button type="button" className="ghost-btn" onClick={onClose} aria-label="Закрыть">
          ✕
        </button>
      </div>

      <dl className="admin-panel__stats">
        <div>
          <dt>Регистрация</dt>
          <dd>{formatDateTimeRu(user.created_at)}</dd>
        </div>
        <div>
          <dt>Баланс кредитов</dt>
          <dd className="mono">{user.credits_balance}</dd>
        </div>
        <div>
          <dt>Модели студии</dt>
          <dd>{user.studio_models_count}</dd>
        </div>
        <div>
          <dt>Генерации в архиве</dt>
          <dd>{user.studio_generations_count}</dd>
        </div>
        <div>
          <dt>Диалоги</dt>
          <dd>{user.conversations_count}</dd>
        </div>
        <div>
          <dt>Приглашено по рефералке</dt>
          <dd>{user.invited_users_count}</dd>
        </div>
        {user.referred_by_email ? (
          <div>
            <dt>Пришёл по рефералке</dt>
            <dd>{user.referred_by_email}</dd>
          </div>
        ) : null}
        {isOwner && user.workspace_members_count > 0 ? (
          <div>
            <dt>Участников в команде</dt>
            <dd>{user.workspace_members_count}</dd>
          </div>
        ) : null}
      </dl>

      <section className="admin-panel__section">
        <h3>Подписка (владелец пространства)</h3>
        <label className="admin-field">
          <span>Статус</span>
          <select
            value={user.subscription_status}
            disabled={busy}
            onChange={(e) => {
              const v = e.target.value
              if (v !== user.subscription_status) void patchSubscription({ status: v })
            }}
          >
            {SUBSCRIPTION_STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {SUBSCRIPTION_STATUS_LABELS[s] ?? s}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-field">
          <span>Биллинг</span>
          <select
            value={(user.billing_plan || 'managed').toLowerCase()}
            disabled={busy}
            onChange={(e) => {
              const v = e.target.value
              if (v !== (user.billing_plan || 'managed').toLowerCase()) {
                void patchSubscription({ billing_plan: v })
              }
            }}
          >
            {BILLING_PLAN_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {billingPlanLabel(p)}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-field">
          <span>Тариф</span>
          <select
            value={(user.plan_tier || 'solo').toLowerCase()}
            disabled={busy}
            onChange={(e) => {
              const v = e.target.value
              if (v !== (user.plan_tier || 'solo').toLowerCase()) {
                void patchSubscription({ plan_tier: v })
              }
            }}
          >
            {PLAN_TIER_OPTIONS.map((t) => (
              <option key={t} value={t}>
                {planTierLabel(t)}
              </option>
            ))}
          </select>
        </label>
        <div className="admin-field">
          <span>Период до</span>
          <p className="mono small">{formatDateTimeRu(user.subscription_period_end)}</p>
          <div className="admin-period-row">
            <input
              type="datetime-local"
              className="admin-period-inp"
              defaultValue={isoToDatetimeLocalValue(user.subscription_period_end)}
              key={periodKey}
              id={periodKey}
              disabled={busy}
            />
            <button
              type="button"
              className="ghost-btn small"
              disabled={busy}
              onClick={() => {
                const el = document.getElementById(periodKey) as HTMLInputElement | null
                const raw = el?.value ?? ''
                void patchSubscription({
                  current_period_end: raw ? datetimeLocalInputToIsoUtc(raw) : null,
                })
              }}
            >
              Сохранить
            </button>
            <button
              type="button"
              className="ghost-btn small"
              disabled={busy}
              onClick={() => void patchSubscription({ current_period_end: null })}
            >
              Сброс
            </button>
          </div>
        </div>
      </section>

      <section className="admin-panel__section">
        <h3>Доступ и кредиты</h3>
        <label className="admin-check">
          <input
            type="checkbox"
            checked={user.is_active}
            disabled={busy}
            onChange={(e) => void patchUser({ is_active: e.target.checked })}
          />
          Аккаунт активен
        </label>
        {isOwner ? (
          <label className="admin-check">
            <input
              type="checkbox"
              checked={user.is_platform_admin}
              disabled={busy}
              onChange={(e) => void patchUser({ is_platform_admin: e.target.checked })}
            />
            Администратор платформы
          </label>
        ) : null}
        <div className="admin-credit-row">
          <input
            type="text"
            inputMode="numeric"
            placeholder="+/- кредиты"
            value={creditDelta}
            disabled={busy}
            onChange={(e) => setCreditDelta(e.target.value)}
          />
          <button type="button" className="ghost-btn" disabled={busy} onClick={() => void applyCredits()}>
            Применить
          </button>
        </div>
      </section>
    </aside>
  )
}
