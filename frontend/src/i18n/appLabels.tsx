import type { ReactNode } from 'react'
import { Trans } from 'react-i18next'
import i18n, { CHAT_NS, COMMON_NS, STUDIO_NS } from './index'

export function conversationNoteKindLabel(kind: 'manual' | 'ai_profile' | 'ai_daily' | 'ai_insight'): string {
  if (kind === 'ai_insight') return 'AI'
  const key = kind === 'ai_profile' ? 'profile' : kind === 'ai_daily' ? 'context' : 'manual'
  return i18n.t(`notes.kinds.${key}`, { ns: CHAT_NS })
}

export function outboundLangOptions(): { value: string; label: string }[] {
  const langs = [
    { value: '', key: 'auto' },
    { value: 'en', label: 'English' },
    { value: 'de', label: 'Deutsch' },
    { value: 'fr', label: 'Français' },
    { value: 'es', label: 'Español' },
    { value: 'it', label: 'Italiano' },
    { value: 'pt', label: 'Português' },
    { value: 'ru', key: 'ru' },
    { value: 'uk', label: 'Українська' },
    { value: 'pl', label: 'Polski' },
    { value: 'tr', label: 'Türkçe' },
    { value: 'nl', label: 'Nederlands' },
    { value: 'sv', label: 'Svenska' },
    { value: 'ja', label: '日本語' },
    { value: 'ko', label: '한국어' },
    { value: 'zh', label: '中文' },
  ]
  return langs.map((l) => ({
    value: l.value,
    label: l.label ?? i18n.t(`outboundLang.${l.key}`, { ns: CHAT_NS }),
  }))
}

export function formatSlaSeconds(sec: number | null | undefined): string {
  if (sec == null || sec <= 0) return '—'
  if (sec < 60) return i18n.t('duration.seconds', { ns: COMMON_NS, n: sec })
  if (sec < 3600) return i18n.t('duration.minutes', { ns: COMMON_NS, n: Math.round(sec / 60) })
  return i18n.t('duration.hours', { ns: COMMON_NS, n: (sec / 3600).toFixed(1) })
}

export function retentionDayUnit(days: number): string {
  const n100 = days % 100
  const n10 = days % 10
  if (n10 === 1 && n100 !== 11) return i18n.t('retention.dayUnit_one', { ns: STUDIO_NS })
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) {
    return i18n.t('retention.dayUnit_few', { ns: STUDIO_NS })
  }
  return i18n.t('retention.dayUnit_many', { ns: STUDIO_NS })
}

export function studioArchiveRetentionLead(
  health: { studio_generations_retention_days?: number } | null,
  kind: 'image' | 'video' = 'image',
): ReactNode {
  const days = health?.studio_generations_retention_days
  if (typeof days === 'number' && days > 0) {
    const dayUnit = retentionDayUnit(days)
    const key = kind === 'video' ? 'retention.videoWithDays' : 'retention.imageWithDays'
    return (
      <Trans
        i18nKey={key}
        ns={STUDIO_NS}
        values={{ days, dayUnit }}
        components={{ strong: <strong /> }}
      />
    )
  }
  const defaultKey = kind === 'video' ? 'retention.videoDefault' : 'retention.imageDefault'
  return <>{i18n.t(defaultKey, { ns: STUDIO_NS })}</>
}
