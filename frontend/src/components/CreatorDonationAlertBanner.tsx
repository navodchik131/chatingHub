import { useTranslation } from 'react-i18next'
import { formatAppCurrency } from '../i18n/appFormat'
import type { CreatorDonationOverviewEvent } from '../utils/creatorDonationOverview'

type Props = {
  event: CreatorDonationOverviewEvent
  onOpen: () => void
  onDismiss: () => void
}

export function CreatorDonationAlertBanner({ event, onOpen, onDismiss }: Props) {
  const { t } = useTranslation('workspace')
  const amount = formatAppCurrency(event.amount_minor, event.currency)

  return (
    <div className="creator-donation-alert billing-return-banner billing-return-banner--success" role="status">
      <div className="billing-return-banner__text">
        <h2 className="billing-return-banner__title">{t('platformDonations.alertTitle')}</h2>
        <p className="billing-return-banner__body">
          {t('platformDonations.alertBody', { amount })}
        </p>
      </div>
      <div className="billing-return-banner__actions">
        <button type="button" className="send-btn" onClick={onOpen}>
          {t('platformDonations.alertOpen')}
        </button>
        <button type="button" className="ghost-btn" onClick={onDismiss}>
          {t('platformDonations.alertDismiss')}
        </button>
      </div>
    </div>
  )
}
