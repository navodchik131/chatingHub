import { useTranslation } from 'react-i18next'

const TELEGRAM_CHANNEL_URL = 'https://t.me/ModelMate_app'

export function TelegramChannelBanner() {
  const { t } = useTranslation('chat')

  return (
    <a
      href={TELEGRAM_CHANNEL_URL}
      className="workspace-tg-banner"
      target="_blank"
      rel="noopener noreferrer"
      aria-label={t('telegramBanner.aria')}
    >
      <img
        src="/marketing/telegram.svg"
        alt=""
        className="workspace-tg-banner__icon"
        width={22}
        height={22}
        decoding="async"
      />
      <span className="workspace-tg-banner__text">
        {t('telegramBanner.text')}{' '}
        <span className="workspace-tg-banner__emph">{t('telegramBanner.emph')}</span>
      </span>
    </a>
  )
}
