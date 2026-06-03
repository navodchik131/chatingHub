const TELEGRAM_CHANNEL_URL = 'https://t.me/ModelMate_app'

export function TelegramChannelBanner() {
  return (
    <a
      href={TELEGRAM_CHANNEL_URL}
      className="workspace-tg-banner"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Канал ModelMate в Telegram — поддержка, анонсы, общение"
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
        Поддержка, анонсы, общение в{' '}
        <span className="workspace-tg-banner__emph">нашем канале</span>
      </span>
    </a>
  )
}
