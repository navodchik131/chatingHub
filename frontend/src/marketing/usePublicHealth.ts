import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

/** Поля из GET /api/health, нужные маркетинговым страницам. */
export interface PublicHealthPricing {
  ok?: boolean
  billing_price_managed_month_rub?: number
  billing_price_byok_month_rub?: number
  billing_credit_pack_price_rub?: number
  billing_credit_pack_credits?: number
  studio_prompt_credit_cost?: number
  studio_upscale_credit_cost?: number
  studio_carousel_credit_cost?: number
}

export function usePublicHealth(): PublicHealthPricing | null {
  const [h, setH] = useState<PublicHealthPricing | null>(null)
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const r = await apiFetch('/api/health')
        if (!r.ok || cancelled) return
        const j = (await r.json()) as PublicHealthPricing
        if (!cancelled) setH(j)
      } catch {
        if (!cancelled) setH(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])
  return h
}

export function formatRub(amount: number): string {
  return `${amount.toLocaleString('ru-RU')} ₽`
}
