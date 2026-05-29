import { useMemo } from 'react'

export const SETUP_TOUR_LS = 'modelmate_setup_tour_v1'

export type SetupTourPhase = 'wavespeed' | 'model' | 'generate' | 'done'

export function readSetupTourDismissed(): boolean {
  try {
    return localStorage.getItem(SETUP_TOUR_LS) === '1'
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

export function resolveSetupTourPhase(input: {
  dismissed: boolean
  wavespeedReady: boolean
  modelsCount: number
  generationsCount: number
}): SetupTourPhase | null {
  if (input.dismissed) return null
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
  const content = useMemo(() => {
    if (!phase || phase === 'done') return null
    if (phase === 'wavespeed') {
      return {
        title: 'Шаг 1 из 3 — ключ WaveSpeed',
        body: isOwner
          ? 'Без API-ключа WaveSpeed студия не сгенерирует картинки и видео. Откройте подключения и вставьте ключ.'
          : 'Попросите владельца аккаунта добавить ключ WaveSpeed в кабинете → Подключения.',
        cta: isOwner ? 'Открыть подключения' : null,
        onCta: onOpenIntegrations,
      }
    }
    if (phase === 'model') {
      return {
        title: 'Шаг 2 из 3 — ваша модель',
        body: 'Создайте модель в кабинете: имя, несколько фото (лицо, тело) — так студия узнает внешность.',
        cta: canStudioModels ? 'Создать модель' : 'Открыть кабинет',
        onCta: onOpenModels,
      }
    }
    return {
      title: 'Шаг 3 из 3 — первая картинка',
      body: 'В разделе «Картинки» выберите модель, загрузите референс (в «Подмена лица» — обязательно фото с человеком) и нажмите «Сгенерировать».',
      cta: 'Перейти в студию',
      onCta: onGoStudio,
    }
  }, [phase, isOwner, canStudioModels, onOpenIntegrations, onOpenModels, onGoStudio])

  if (!content) return null

  return (
    <div className="setup-tour" role="status" aria-live="polite">
      <div className="setup-tour__head">
        <strong className="setup-tour__title">{content.title}</strong>
        <button type="button" className="setup-tour__dismiss" onClick={onDismiss} aria-label="Скрыть подсказки">
          Позже
        </button>
      </div>
      <p className="setup-tour__body">{content.body}</p>
      <ol className="setup-tour__steps">
        <li
          className={
            phase === 'wavespeed' ? 'is-current' : phase === 'model' || phase === 'generate' ? 'is-done' : ''
          }
        >
          Ключ WaveSpeed
        </li>
        <li className={phase === 'model' ? 'is-current' : phase === 'generate' ? 'is-done' : ''}>
          Модель в кабинете
        </li>
        <li className={phase === 'generate' ? 'is-current' : ''}>Первая генерация</li>
      </ol>
      {content.cta ? (
        <button type="button" className="send-btn setup-tour__cta" onClick={content.onCta}>
          {content.cta}
        </button>
      ) : null}
    </div>
  )
}
