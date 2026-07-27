import * as Linking from 'expo-linking';
import { fetchHealth, pollTelegramMobileAuth, startTelegramMobileAuth } from '@/src/api/actions';

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 3 * 60 * 1000;

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
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

/** Открывает Telegram-бота и ждёт JWT через polling (без web widget). */
export async function signInWithTelegram(): Promise<string> {
  const botUsername = await fetchTelegramLoginBotUsername();
  if (!botUsername) {
    throw new Error('Telegram Login не настроен на сервере');
  }

  const started = await startTelegramMobileAuth();
  const telegramUrl = (started.telegram_url || `https://t.me/${botUsername}?start=mm_${started.session_id}`).trim();
  const canOpen = await Linking.canOpenURL(telegramUrl);
  if (!canOpen) {
    throw new Error('Не удалось открыть Telegram. Установите приложение Telegram.');
  }

  await Linking.openURL(telegramUrl);

  const deadline = Date.now() + POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS);
    const poll = await pollTelegramMobileAuth(started.session_id);
    if (poll.status === 'done' && poll.access_token) {
      return poll.access_token;
    }
    if (poll.status === 'expired') {
      throw new Error('Время входа истекло — попробуйте снова');
    }
  }

  throw new Error('Вход через Telegram не завершён. Нажмите Start в боте и вернитесь в приложение.');
}
