import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

/** Поля из GET /api/health, нужные маркетинговым страницам. */
export interface PublicHealthPricing {
  ok?: boolean
  signup_bonus_credits?: number
  demo_generations_grant?: number
  marketing_beta_creators_count?: number
  billing_catalog?: { plans?: unknown[]; referral?: unknown }
  billing_price_managed_month_rub?: number
  billing_price_byok_month_rub?: number
  billing_credit_pack_price_rub?: number
  billing_credit_pack_credits?: number
  billing_credits_min_purchase?: number
  billing_credits_bulk_from?: number
  billing_credits_unit_price_rub?: number
  billing_credits_bulk_unit_price_rub?: number
  studio_prompt_credit_cost?: number
  studio_upscale_credit_cost?: number
  studio_carousel_credit_cost?: number
  studio_image_pricing?: unknown
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
