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
  isTrialing?: boolean
  canConnect: boolean
  onOpenIntegrations: () => void
}

export function WavespeedSetupBanner({
  variant,
  isTrialing,
  canConnect,
  onOpenIntegrations,
}: Props) {
  if (variant === 'integrations') {
    return (
      <div className="ws-setup-banner ws-setup-banner--integrations" role="status">
        <h4 className="ws-setup-banner__title">Подключите WaveSpeed для картинок и видео</h4>
        <p className="muted ws-setup-banner__lead">
          {isTrialing ? (
            <>
              На пробном периоде генерация идёт через <strong>ваш</strong> ключ WaveSpeed — без него студия
              не запустится. Текстовые промпты и vision уже работают с ключа платформы.
            </>
          ) : (
            <>
              Для тарифа BYOK и пробного Managed нужен ваш API-ключ WaveSpeed. После оплаты Managed ключ
              может подставлять платформа.
            </>
          )}
        </p>
        <ol className="ws-setup-banner__steps">
          <li>
            Зарегистрируйтесь на{' '}
            <a href="https://wavespeed.ai" target="_blank" rel="noopener noreferrer">
              wavespeed.ai
            </a>{' '}
            и пополните баланс.
          </li>
          <li>В личном кабинете WaveSpeed скопируйте API-ключ.</li>
          <li>
            Вставьте ключ в поле <strong>«API-ключ»</strong> ниже и нажмите <strong>«Сохранить»</strong>.
          </li>
        </ol>
      </div>
    )
  }

  const place =
    variant === 'video' ? 'раздел «Видео»' : 'раздел «Картинки»'

  return (
    <div className="ws-setup-banner ws-setup-banner--studio" role="status">
      <p className="ws-setup-banner__compact">
        <strong>Нет ключа WaveSpeed</strong> — {place} не сможет сгенерировать результат.
        {isTrialing ? ' На пробном периоде нужен ваш ключ.' : ' Добавьте ключ в кабинете.'}
      </p>
      {canConnect ? (
        <button type="button" className="send-btn ws-setup-banner__cta" onClick={onOpenIntegrations}>
          Подключить ключ WaveSpeed
        </button>
      ) : (
        <p className="muted small">
          Попросите владельца аккаунта открыть кабинет → <strong>Подключения</strong> → WaveSpeed.
        </p>
      )}
    </div>
  )
}
