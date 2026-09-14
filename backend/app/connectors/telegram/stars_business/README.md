# Stars Business bot (paid media за ⭐)

Отдельный модуль: **OWNER** / **OPERATOR**, без Unibox и companion media.

## Роли

- **OWNER** — владелец Telegram Business. Подключает **этого же бота** в настройках Business (Secretary Mode). От его имени уходят paid media фанам.
- **OPERATOR** — сотрудник. Пишет боту в личку, whitelist по `telegram user id`. Доступа к аккаунту OWNER нет.

## BotFather

1. Бот должен быть **создан под аккаунтом OWNER** (выручка за paid media в личке идёт на **баланс бота**).
2. Включите **Secretary Mode** (ранее Business Mode). Иначе запросы с `business_connection_id` падают с `BUSINESS_CONNECTION_NOT_ALLOWED`.
3. OWNER: Telegram → Business → Chatbots → подключить этого бота.

## Env

```env
STARS_BUSINESS_BOT_TOKEN=
STARS_BUSINESS_WEBHOOK_SECRET=   # случайная строка для URL
PUBLIC_APP_URL=https://your-domain
STARS_BUSINESS_OPERATOR_TELEGRAM_IDS=123456789,987654321
# Локально без HTTPS:
# STARS_BUSINESS_POLLING=1
```

Webhook: `POST /api/webhooks/telegram-stars/{STARS_BUSINESS_WEBHOOK_SECRET}`

`allowed_updates` включает `callback_query` (кнопки мастера /paid).

## OPERATOR

- `/paid` — фото/видео → цена ⭐ → выбор фана (список или пересылка сообщения) → подтверждение.
- `/chats` — недавние диалоги, 🟢/🔴 окно 24ч.
- `/cancel` — сброс.

Список диалогов строится из `business_message`. `@username` не используется.

## Ограничения Telegram

- Без входящего от фана за **24 часа** — `BUSINESS_CHAT_INACTIVE` (ожидаемо).
- Всегда `protect_content=True`.
- `payload` заказа = `str(order.id)`; оплата — `purchased_paid_media`.

## aiogram

Требуется **aiogram ≥ 3.13** (`send_paid_media` + `business_connection_id`).
