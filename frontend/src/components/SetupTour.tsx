import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

export const SETUP_TOUR_LS = 'modelmate_setup_tour_v1'
export const SETUP_TOUR_HAD_GEN_LS = 'modelmate_setup_tour_had_gen_v1'

export type SetupTourPhase = 'wavespeed' | 'model' | 'generate' | 'done'

export function readSetupTourDismissed(): boolean {
  try {
    return localStorage.getItem(SETUP_TOUR_LS) === '1'
  } catch {
    return false
  }
}

export function readSetupTourHadGeneration(): boolean {
  try {
    return localStorage.getItem(SETUP_TOUR_HAD_GEN_LS) === '1'
  } catch {
    return false
  }
}

export function dismissSetupTour(): void {
  try {
    localStorage.setItem(SETUP_TOUR_LS, '1')
  } catch {
    /* private mode */
  }
}

export function markSetupTourHadGeneration(): void {
  try {
    localStorage.setItem(SETUP_TOUR_HAD_GEN_LS, '1')
    localStorage.setItem(SETUP_TOUR_LS, '1')
  } catch {
    /* private mode */
  }
}

export function resolveSetupTourPhase(input: {
  dismissed: boolean
  hadGeneration: boolean
  archiveReady: boolean
  wavespeedReady: boolean
  modelsCount: number
  generationsCount: number
}): SetupTourPhase | null {
  if (input.dismissed || input.hadGeneration) return null
  if (!input.archiveReady) return null
  if (!input.wavespeedReady) return 'wavespeed'
  if (input.modelsCount < 1) return 'model'
  if (input.generationsCount < 1) return 'generate'
  return 'done'
}

type Props = {
  phase: SetupTourPhase | null
  isOwner: boolean
  canStudioModels: boolean
  onOpenIntegrations: () => void
  onOpenModels: () => void
  onGoStudio: () => void
  onDismiss: () => void
}

export function SetupTour({
  phase,
  isOwner,
  canStudioModels,
  onOpenIntegrations,
  onOpenModels,
  onGoStudio,
  onDismiss,
}: Props) {
  const { t } = useTranslation('studio')

  const content = useMemo(() => {
    if (!phase || phase === 'done') return null
    if (phase === 'wavespeed') {
      return {
        title: t('setupTour.wavespeed.title'),
        body: isOwner ? t('setupTour.wavespeed.bodyOwner') : t('setupTour.wavespeed.bodyMember'),
        cta: isOwner ? t('setupTour.wavespeed.cta') : null,
        onCta: onOpenIntegrations,
      }
    }
    if (phase === 'model') {
      return {
        title: t('setupTour.model.title'),
        body: t('setupTour.model.body'),
        cta: canStudioModels ? t('setupTour.model.ctaCreate') : t('setupTour.model.ctaCabinet'),
        onCta: onOpenModels,
      }
    }
    return {
      title: t('setupTour.generate.title'),
      body: t('setupTour.generate.body'),
      cta: t('setupTour.generate.cta'),
      onCta: onGoStudio,
    }
  }, [phase, isOwner, canStudioModels, onOpenIntegrations, onOpenModels, onGoStudio, t])

  if (!content) return null

  return (
    <div className="setup-tour" role="status">
      <div className="setup-tour__head">
        <strong className="setup-tour__title">{content.title}</strong>
        <button
          type="button"
          className="setup-tour__dismiss"
          onClick={onDismiss}
          aria-label={t('setupTour.dismissAria')}
        >
          {t('setupTour.dismiss')}
        </button>
      </div>
      <p className="setup-tour__body">{content.body}</p>
      <ol className="setup-tour__steps">
        <li
          className={
            phase === 'wavespeed' ? 'is-current' : phase === 'model' || phase === 'generate' ? 'is-done' : ''
          }
        >
          {t('setupTour.steps.wavespeed')}
        </li>
        <li className={phase === 'model' ? 'is-current' : phase === 'generate' ? 'is-done' : ''}>
          {t('setupTour.steps.model')}
        </li>
        <li className={phase === 'generate' ? 'is-current' : ''}>{t('setupTour.steps.generate')}</li>
      </ol>
      {content.cta ? (
        <button type="button" className="send-btn setup-tour__cta" onClick={content.onCta}>
          {content.cta}
        </button>
      ) : null}
    </div>
  )
}
