export function creditUnitFromHealth(
  health: {
    billing_catalog?: { credits_pricing?: { unit_price_rub?: number } }
    billing_credits_unit_price_rub?: number
  } | null | undefined,
): number {
  const fromCatalog = health?.billing_catalog?.credits_pricing?.unit_price_rub
  if (typeof fromCatalog === 'number' && fromCatalog > 0) return fromCatalog
  const direct = health?.billing_credits_unit_price_rub
  if (typeof direct === 'number' && direct > 0) return direct
  return 3.7
}
