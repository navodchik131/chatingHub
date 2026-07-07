import { createContext, useContext, type ReactNode } from 'react'
import { normalizeBillingPlan } from '../billing/planCatalog'
import { planDisplayShort, type BillingMeLike } from '../billing/planLabels'
import {
  formatStudioImageCostLabel,
  quoteStudioImageCredits,
  studioGenerationUsesDemo,
  normalizeWaveModelId,
  wanEditTierFromUiModelId,
  type WaveProfile,
} from '../studioImagePricing'

export type WorkflowBillingState = {
  me: BillingMeLike | null
  quoteWorkflowImageCredits: (waveModelId: string, nsfwEnabled: boolean) => {
    credits: number | null
    label: string
  }
}

const WorkflowBillingContext = createContext<WorkflowBillingState | null>(null)

export function WorkflowBillingProvider({
  me,
  children,
}: {
  me: BillingMeLike | null
  children: ReactNode
}) {
  const plan = normalizeBillingPlan(me?.billing_plan)
  const isProPlan = plan === 'pro'
  const demoRemaining = me?.demo_generations_remaining ?? 0
  const creditsBalance = me?.credits_balance ?? 0

  const quoteWorkflowImageCredits = (waveModelId: string, nsfwEnabled: boolean) => {
    if (isProPlan) {
      return { credits: null, label: 'Pro' }
    }
    const waveProfile: WaveProfile = nsfwEnabled ? 'nsfw' : 'regular'
    const apiModel = normalizeWaveModelId(waveModelId)
    const wanEditTier = wanEditTierFromUiModelId(waveModelId)
    const credits = quoteStudioImageCredits({
      waveModelId: apiModel,
      waveProfile,
      grokPipeline: 'workflow',
      workflow: true,
      wanEditTier,
    })
    const useDemo = studioGenerationUsesDemo({
      billingPlan: me?.billing_plan,
      demoRemaining,
      creditsBalance,
      waveProfile,
      waveModelId: apiModel,
      studioMode: 'model_scene',
      workflow: true,
    })
    return {
      credits,
      label: formatStudioImageCostLabel(credits, {
        isProPlan,
        demoRemaining,
        useDemo,
      }),
    }
  }

  return (
    <WorkflowBillingContext.Provider value={{ me, quoteWorkflowImageCredits }}>
      {children}
    </WorkflowBillingContext.Provider>
  )
}

export function useWorkflowBilling(): WorkflowBillingState {
  const ctx = useContext(WorkflowBillingContext)
  if (!ctx) {
    return {
      me: null,
      quoteWorkflowImageCredits: () => ({ credits: null, label: '—' }),
    }
  }
  return ctx
}

export function workflowBillingHeaderLine(me: BillingMeLike | null): string {
  if (!me) return ''
  const plan = planDisplayShort(me)
  const bal = me.credits_balance ?? 0
  const demo = me.demo_generations_remaining ?? 0
  if (normalizeBillingPlan(me.billing_plan) === 'pro') {
    return `${plan} · оплата у WaveSpeed`
  }
  if (demo > 0) {
    return `${plan} · ${bal} кр. · ${demo} демо`
  }
  return `${plan} · ${bal} кр.`
}
