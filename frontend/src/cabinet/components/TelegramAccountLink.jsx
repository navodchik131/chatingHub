import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import '../../styles/auth-ui.css';
import { TelegramLoginButton } from '../../auth/TelegramAuth';
import {
  clearPendingTelegramLink,
  hasPendingTelegramLink,
  linkTelegramViaBot,
  resumePendingTelegramBotLink,
} from '../../auth/telegramBotLink';
import { apiFetch } from '../../api';
import { formatHttpApiError } from '../../apiErrors';
import { openBlankPopupForDeferredNav } from '../../utils/openExternalUrl';
import Hoverable from './Hoverable';
import { Panel, Eyebrow } from './ui';
import { color, line, font } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';

export default function TelegramAccountLink({ me, health, t, lang, onRefresh }) {
  const [busy, setBusy] = useState(() => hasPendingTelegramLink());
  const [error, setError] = useState('');
  const [showWidget, setShowWidget] = useState(false);
  const pollingRef = useRef(false);

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

  const tryResumeLink = useCallback(async () => {
    if (!hasPendingTelegramLink() || pollingRef.current) return;
    pollingRef.current = true;
    setBusy(true);
    try {
      const ok = await resumePendingTelegramBotLink();
      if (ok) {
        await handleLinked();
        return;
      }
      if (hasPendingTelegramLink()) {
        setError(t.telegramBotHint);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      pollingRef.current = false;
      setBusy(false);
    }
  }, [handleLinked, t.telegramBotHint]);

  useEffect(() => {
    if (linked || !configured) return;
    void tryResumeLink();

    const onVis = () => {
      if (document.visibilityState === 'visible') void tryResumeLink();
    };
    const onFocus = () => {
      void tryResumeLink();
    };
    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('focus', onFocus);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('focus', onFocus);
    };
  }, [linked, configured, tryResumeLink]);

  const runBotLink = useCallback(async () => {
    if (pollingRef.current) return;
    pollingRef.current = true;
    setBusy(true);
    setError('');
    const preopenedPopup = typeof window !== 'undefined' ? openBlankPopupForDeferredNav() : null;
    try {
      await linkTelegramViaBot({ preopenedPopup });
      await handleLinked();
    } catch (e) {
      if (!hasPendingTelegramLink()) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      pollingRef.current = false;
      setBusy(false);
    }
  }, [handleLinked]);

  const cancelPending = useCallback(() => {
    clearPendingTelegramLink();
    pollingRef.current = false;
    setBusy(false);
    setError('');
  }, []);

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
          <button
            type="button"
            className="telegram-bot-btn"
            disabled={busy}
            onClick={() => void runBotLink()}
            style={{ maxWidth: 360 }}
          >
            {busy ? t.telegramWaiting : t.telegramLinkViaApp}
          </button>
          {busy ? (
            <>
              <p className="auth-hint auth-hint--center" style={{ marginTop: 10 }}>
                {t.telegramBotHint}
              </p>
              <button type="button" className="auth-link-btn" onClick={cancelPending}>
                {t.telegramCancel}
              </button>
            </>
          ) : (
            <>
              <div style={{ fontSize: 11.5, lineHeight: 1.5, color: color.textGhost, marginTop: 10, maxWidth: 420 }}>
                {t.telegramLinkViaAppHint}
              </div>
              <Hoverable
                as="button"
                type="button"
                style={{
                  marginTop: 10,
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  fontSize: 11.5,
                  fontWeight: 700,
                  color: color.textDim,
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
                hover={{ color: color.textMid }}
                onClick={() => setShowWidget((v) => !v)}
              >
                {showWidget ? t.telegramHideBrowserLogin : t.telegramShowBrowserLogin}
              </Hoverable>
              {showWidget ? (
                <div style={{ marginTop: 12, maxWidth: 360 }}>
                  <div style={{ fontSize: 11, lineHeight: 1.45, color: color.orange, marginBottom: 8 }}>
                    {t.telegramWidgetHint}
                  </div>
                  <TelegramLoginButton
                    botUsername={botUsername}
                    mode="link"
                    onSuccess={handleLinked}
                    onError={setError}
                  />
                </div>
              ) : null}
            </>
          )}
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
