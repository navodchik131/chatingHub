import { useEffect, useState } from 'react';
import { apiFetch } from '../../api';
import { useApp } from '../hooks/useApp';
import { color, line } from '../styles/tokens';
import Hoverable from './Hoverable';

/** Отдельная статичная страница нового кабинета (демо), см. frontend/swap/index.html. */
export const SWAP_APP_URL = '/workspace/swap/';

const SESSION_KEY = 'mm_swap_promo_seen';
const HIDE_KEY = 'mm_swap_promo_hide';

const TEXT = {
  ru: {
    tag: 'Новый кабинет · демо',
    title: 'Попробуйте новый кабинет',
    body: 'Референс → готовый промпт → генерация в один клик. Модели с набором ракурсов, автопроверка результата и второй проход. Тариф, баланс и ключи — те же, что здесь.',
    note: 'Старый кабинет продолжает работать как раньше — вернуться можно в любой момент.',
    locked: 'Демо доступно на активной подписке.',
    open: 'Открыть новый кабинет',
    billing: 'Оформить подписку',
    later: 'Позже',
    hide: 'Больше не показывать',
  },
  en: {
    tag: 'New workspace · demo',
    title: 'Try the new workspace',
    body: 'Reference → ready prompt → one-click generation. Models with an angle kit, automatic result check and a second pass. Same plan, balance and keys as here.',
    note: 'The current workspace keeps working as before — you can come back any time.',
    locked: 'The demo is available with an active subscription.',
    open: 'Open new workspace',
    billing: 'Get a subscription',
    later: 'Later',
    hide: "Don't show again",
  },
};

function readFlag(storage, key) {
  try {
    return storage.getItem(key) === '1';
  } catch {
    return false;
  }
}

function writeFlag(storage, key) {
  try {
    storage.setItem(key, '1');
  } catch {
    /* приватный режим — просто не запоминаем */
  }
}

export default function NewCabinetPromo() {
  const { lang, go } = useApp();
  const [access, setAccess] = useState(null);
  const [open, setOpen] = useState(false);
  const [hide, setHide] = useState(false);

  useEffect(() => {
    if (readFlag(window.localStorage, HIDE_KEY) || readFlag(window.sessionStorage, SESSION_KEY)) return undefined;
    let alive = true;
    apiFetch('/api/swap/access', { timeoutMs: 10000 })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!alive || !j || !j.enabled) return;
        setAccess(j);
        setOpen(true);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!open || !access) return null;
  const t = TEXT[lang === 'en' ? 'en' : 'ru'];

  const close = () => {
    writeFlag(window.sessionStorage, SESSION_KEY);
    if (hide) writeFlag(window.localStorage, HIDE_KEY);
    setOpen(false);
  };
  const primary = () => {
    writeFlag(window.sessionStorage, SESSION_KEY);
    if (hide) writeFlag(window.localStorage, HIDE_KEY);
    if (access.allowed) {
      window.location.assign(SWAP_APP_URL);
    } else {
      setOpen(false);
      go('billing')();
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mm-swap-promo-title"
      onClick={close}
      style={{
        position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(5,6,8,.72)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 460, background: color.raised, border: `1px solid ${line.mid}`,
          borderRadius: 18, padding: '22px 22px 18px', boxShadow: '0 24px 70px rgba(0,0,0,.6)',
          boxSizing: 'border-box',
        }}
      >
        <div style={{
          display: 'inline-block', fontSize: 11, fontWeight: 800, letterSpacing: '.08em', textTransform: 'uppercase',
          color: color.lime, border: `1px solid ${color.limeInkSoft}`, borderRadius: 999, padding: '4px 10px',
        }}
        >
          {t.tag}
        </div>
        <div id="mm-swap-promo-title" style={{ fontWeight: 800, fontSize: 22, margin: '12px 0 8px', color: color.text }}>
          {t.title}
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.55, color: color.textMid }}>{t.body}</div>
        <div style={{ fontSize: 12.5, lineHeight: 1.5, color: color.textDim, marginTop: 10 }}>
          {access.allowed ? t.note : t.locked}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 18, flexWrap: 'wrap' }}>
          <Hoverable
            style={{
              flex: '1 1 200px', textAlign: 'center', background: color.lime, color: color.limeInk, fontWeight: 800,
              fontSize: 14, borderRadius: 11, padding: '11px 16px', cursor: 'pointer',
            }}
            hover={{ filter: 'brightness(1.06)' }}
            onClick={primary}
          >
            {access.allowed ? t.open : t.billing}
          </Hoverable>
          <Hoverable
            style={{
              textAlign: 'center', border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
              fontSize: 14, borderRadius: 11, padding: '11px 16px', cursor: 'pointer',
            }}
            hover={{ borderColor: line.strong }}
            onClick={close}
          >
            {t.later}
          </Hoverable>
        </div>

        <label style={{
          display: 'flex', alignItems: 'center', gap: 8, marginTop: 14, fontSize: 12.5,
          color: color.textDim, cursor: 'pointer', userSelect: 'none',
        }}
        >
          <input type="checkbox" checked={hide} onChange={(e) => setHide(e.target.checked)} />
          {t.hide}
        </label>
      </div>
    </div>
  );
}
