import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { fetchHealth, loginTelegram } from '@/src/api/actions';
import type { TelegramLoginUser } from '@/src/api/types';
import { getSiteBaseUrl } from '@/src/api/config';

WebBrowser.maybeCompleteAuthSession();

function parseTelegramAuthUrl(url: string): TelegramLoginUser {
  const parsed = Linking.parse(url);
  const q = parsed.queryParams ?? {};
  const pick = (key: string) => {
    const v = q[key];
    return typeof v === 'string' ? v : Array.isArray(v) ? v[0] : '';
  };
  const id = Number(pick('id'));
  const auth_date = Number(pick('auth_date'));
  const hash = pick('hash').trim();
  if (!Number.isFinite(id) || id <= 0 || !Number.isFinite(auth_date) || auth_date <= 0 || !hash) {
    throw new Error('Telegram не вернул данные авторизации');
  }
  const user: TelegramLoginUser = { id, auth_date, hash };
  const first = pick('first_name').trim();
  const last = pick('last_name').trim();
  const username = pick('username').trim();
  const photo = pick('photo_url').trim();
  if (first) user.first_name = first;
  if (last) user.last_name = last;
  if (username) user.username = username;
  if (photo) user.photo_url = photo;
  return user;
}

export async function fetchTelegramLoginBotUsername(): Promise<string | null> {
  try {
    const health = await fetchHealth();
    if (health.telegram_login_configured && health.telegram_login_bot_username) {
      return health.telegram_login_bot_username.trim().replace(/^@/, '') || null;
    }
  } catch {
    /* ignore */
  }
  return null;
}

/** Открывает Telegram Login Widget в браузере и возвращает JWT через API. */
export async function signInWithTelegram(): Promise<string> {
  const botUsername = await fetchTelegramLoginBotUsername();
  if (!botUsername) {
    throw new Error('Telegram Login не настроен на сервере');
  }

  const redirectUrl = Linking.createURL('telegram-auth');
  const authPage = `${getSiteBaseUrl()}/mobile-telegram-auth.html?bot=${encodeURIComponent(botUsername)}&return=${encodeURIComponent(redirectUrl)}`;

  const result = await WebBrowser.openAuthSessionAsync(authPage, redirectUrl);
  if (result.type !== 'success' || !result.url) {
    throw new Error('Вход через Telegram отменён');
  }

  const payload = parseTelegramAuthUrl(result.url);
  const data = await loginTelegram(payload);
  return data.access_token;
}
