export type CreditsPlanKind = 'credits' | 'standard' | 'pro';

const LEGACY_BILLING_ALIASES: Record<string, CreditsPlanKind> = {
  managed: 'standard',
  byok: 'pro',
};

export function normalizeBillingPlan(raw: string | null | undefined): CreditsPlanKind {
  const s = (raw || 'standard').trim().toLowerCase();
  if (s in LEGACY_BILLING_ALIASES) return LEGACY_BILLING_ALIASES[s];
  if (s === 'credits' || s === 'standard' || s === 'pro') return s;
  return 'standard';
}

export function isProPlan(raw: string | null | undefined): boolean {
  return normalizeBillingPlan(raw) === 'pro';
}
