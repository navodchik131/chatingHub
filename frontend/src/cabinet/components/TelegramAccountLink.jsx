import { useCallback, useMemo, useState } from 'react';
import '../../styles/auth-ui.css';
import { TelegramLoginButton } from '../../auth/TelegramAuth';
import { apiFetch } from '../../api';
import { formatHttpApiError } from '../../apiErrors';
import Hoverable from './Hoverable';
import { Panel, Eyebrow } from './ui';
import { color, line, font } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';

export default function TelegramAccountLink({ me, health, t, lang, onRefresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const botUsername = useMemo(() => {
    const raw = health?.telegram_login_bot_username || '';
    return String(raw).trim().replace(/^@/, '');
  }, [health?.telegram_login_bot_username]);

  const configured = Boolean(me?.telegram_login_available && botUsername);
  const linked = Boolean(me?.telegram_linked);
  const isOwner = Boolean(me?.is_workspace_owner);

  const linkedLabel = useMemo(() => {
    const userSuffix = me?.telegram_username
      ? (lang === 'ru' ? `: @${me.telegram_username}` : `: @${me.telegram_username}`)
      : '';
    const base = (t.telegramLinked || '').replace('{{username}}', userSuffix);
    return base.includes('{{username}}') ? `${base}${userSuffix}` : base;
  }, [me?.telegram_username, t.telegramLinked, lang]);

  const handleLinked = useCallback(async () => {
    setError('');
    await onRefresh?.();
  }, [onRefresh]);

  const handleUnlink = useCallback(async () => {
    if (!window.confirm(t.telegramUnlinkConfirm)) return;
    setBusy(true);
    setError('');
    try {
      const r = await apiFetch('/api/auth/telegram/link', { method: 'DELETE' });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        setError(formatHttpApiError(r, j));
        return;
      }
      await onRefresh?.();
    } finally {
      setBusy(false);
    }
  }, [onRefresh, t.telegramUnlinkConfirm]);

  if (!isOwner) return null;

  return (
    <Panel style={{ padding: '16px 18px', marginBottom: 24 }}>
      <Eyebrow style={{ marginBottom: 10 }}>{t.telegramTitle}</Eyebrow>
      {linked ? (
        <>
          <div style={{ fontSize: 13, lineHeight: 1.55, color: color.textMid, marginBottom: 12 }}>
            {linkedLabel}
          </div>
          <Hoverable
            as="button"
            type="button"
            disabled={busy}
            style={{
              background: color.raised,
              border: `1px solid ${line.mid}`,
              borderRadius: 10,
              padding: '9px 14px',
              fontSize: 12.5,
              fontWeight: 700,
              color: color.orange,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.6 : 1,
            }}
            hover={{ borderColor: borderHoverOff }}
            onClick={() => void handleUnlink()}
          >
            {t.telegramUnlink}
          </Hoverable>
        </>
      ) : configured ? (
        <>
          <div style={{ fontSize: 13, lineHeight: 1.55, color: color.textDim, marginBottom: 12 }}>
            {t.telegramLinkHint}
          </div>
          <TelegramLoginButton
            botUsername={botUsername}
            mode="link"
            onSuccess={handleLinked}
            onError={setError}
          />
        </>
      ) : (
        <div style={{ fontSize: 13, lineHeight: 1.55, color: color.textDim }}>
          {t.telegramNotConfigured}
        </div>
      )}
      {error ? (
        <div
          style={{
            marginTop: 10,
            fontSize: 12,
            lineHeight: 1.45,
            color: color.orange,
            fontFamily: font.mono,
          }}
        >
          {error}
        </div>
      ) : null}
    </Panel>
  );
}
