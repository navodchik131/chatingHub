import { Trans, useTranslation } from 'react-i18next'
import { WAVESPEED_REF_URL } from '../billing/planCatalog'

export type WavespeedKeyInteg = {
  wavespeed_configured?: boolean
  wavespeed_managed_by_platform?: boolean
}

export function needsUserWavespeedKey(integ: WavespeedKeyInteg | null | undefined): boolean {
  if (!integ) return false
  if (integ.wavespeed_managed_by_platform) return false
  return !integ.wavespeed_configured
}

type Props = {
  variant: 'integrations' | 'studio' | 'video'
  canConnect: boolean
  onOpenIntegrations: () => void
}

export function WavespeedSetupBanner({
  variant,
  canConnect,
  onOpenIntegrations,
}: Props) {
  const { t } = useTranslation('workspace')

  if (variant === 'integrations') {
    return (
      <div className="ws-setup-banner ws-setup-banner--integrations" role="status">
        <h4 className="ws-setup-banner__title">{t('cabinet.wavespeedBanner.integrationsTitle')}</h4>
        <p className="muted ws-setup-banner__lead">
          <Trans
            i18nKey="cabinet.wavespeedBanner.integrationsLead"
            ns="workspace"
            components={{ strong: <strong /> }}
          />
        </p>
        <ol className="ws-setup-banner__steps">
          <li>
            <Trans
              i18nKey="cabinet.wavespeedBanner.step1"
              ns="workspace"
              components={{
                link: (
                  <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                    wavespeed.ai
                  </a>
                ),
              }}
            />
          </li>
          <li>{t('cabinet.wavespeedBanner.step2')}</li>
          <li>
            <Trans
              i18nKey="cabinet.wavespeedBanner.step3"
              ns="workspace"
              components={{ strong: <strong /> }}
            />
          </li>
        </ol>
      </div>
    )
  }

  const place =
    variant === 'video'
      ? t('cabinet.wavespeedBanner.sectionVideo')
      : t('cabinet.wavespeedBanner.sectionImages')

  return (
    <div className="ws-setup-banner ws-setup-banner--studio" role="status">
      <p className="ws-setup-banner__compact">
        <Trans
          i18nKey="cabinet.wavespeedBanner.studioCompact"
          ns="workspace"
          values={{ section: place }}
          components={{ strong: <strong /> }}
        />
      </p>
      {canConnect ? (
        <button type="button" className="send-btn ws-setup-banner__cta" onClick={onOpenIntegrations}>
          {t('cabinet.wavespeedBanner.connectCta')}
        </button>
      ) : (
        <p className="muted small">
          <Trans
            i18nKey="cabinet.wavespeedBanner.askOwner"
            ns="workspace"
            components={{ strong: <strong /> }}
          />
        </p>
      )}
    </div>
  )
}
