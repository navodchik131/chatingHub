# Chating Hub

Единый инбокс для **Telegram Channel Direct Messages** с переводом входящих на русский и ответов с русского на язык собеседника. Заготовка под **Fanvue** (вебхук и коннектор).

## Стек

- **Backend:** Python, FastAPI, aiogram 3, SQLAlchemy async, SQLite  
- **Frontend:** React, TypeScript, Vite  
- **Перевод:** DeepL (если задан `DEEPL_API_KEY`), иначе публичный LibreTranslate  

## Запуск

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

В `.env` укажите `BOT_TOKEN` (от [@BotFather](https://t.me/BotFather)). Опционально: `DEEPL_API_KEY`.

База SQLite по умолчанию: **`backend/data/app.db`** (путь абсолютный, не зависит от того, из какой папки запущен Python). Проверка: откройте в браузере **`/api/health`** — там путь к файлу и счётчики записей.

**Рекомендуемая команда разработки (Windows):** скрипт `backend/run-dev.ps1` — `--reload` только для каталога `app/`, чтобы при записи в SQLite **не перезапускался** процесс и **не останавливался** Telegram polling.

```powershell
cd backend
.\run-dev.ps1
```

Или вручную:

```bash
python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8080
```

**Windows:** если появляется `WinError 10013` (доступ к сокету запрещён), часто порт **8000** занят или попал в зарезервированный диапазон (Hyper-V и т.п.). Запустите на другом порту, например **8080** (как в примерах выше).

Во `frontend` создайте файл `.env` со строкой `VITE_BACKEND_PORT=8080`, чтобы прокси Vite ходил на тот же порт.

### 2. Frontend (разработка)

В другом терминале:

```bash
cd frontend
npm install
npm run dev
```

Откройте http://127.0.0.1:5173 — запросы проксируются на API (по умолчанию порт 8000, см. `VITE_BACKEND_PORT` в `frontend/.env`).

### 3. Один порт (без Vite)

Соберите фронт и откройте только backend (раздаёт и API, и SPA):

```bash
cd frontend
npm run build
cd ../backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Интерфейс: http://127.0.0.1:8000

## Telegram

1. Создайте бота в BotFather, получите токен.  
2. Добавьте бота **администратором** в чат **Direct messages** вашего канала и выдайте право управлять direct messages (по сути — доступ к диалогам с подписчиками).  
3. Запустите backend с `BOT_TOKEN` — включится long polling.

Входящие сообщения попадают в БД и в веб-интерфейс; ответ из UI уходит в тот же топик диалога (`direct_messages_topic_id`).

### Сообщения есть в Telegram, но `/api/health` показывает 0 диалогов

1. **В логах backend** (уровень INFO) должны появляться строки `telegram.incoming: update.message chat_id=... is_direct_messages=...`.  
   - **Если их нет** при новом сообщении — бот **не получает** апдейты: проверьте, что в BotFather тот же токен, что в `.env`; что бот **админ** в чате Direct messages; что нет **второго** процесса с тем же токеном; запускайте через `run-dev.ps1` (чтобы `--reload` не ронял polling из‑за `data/*.db`).

2. **Если строки есть**, смотрите поля: `is_direct_messages=True` и заполнены `direct_messages_topic` или `message_thread_id`. Код обрабатывает оба варианта.

3. Убедитесь, что пишете именно в **Direct messages канала** (как подписчик в интерфейсе канала), а не в личку пользователя @username, если это другой тип чата.

4. **Админ в канале** ≠ доступ к чату Direct messages. Бота нужно добавить **администратором в отдельный чат Direct messages** (супергруппа, привязанная к каналу), с правом на direct messages — это не то же самое, что «админ канала» только для постов.

### Нет связи с api.telegram.org (таймаут, VPN)

В логах: `Cannot connect to host api.telegram.org` / `TimeoutError` — компьютер **не достигает** серверы Telegram по HTTPS. Пока так, **polling не получит ни одного сообщения**, независимо от прав бота.

Что сделать: другой интернет, **VPN**, или прокси в `backend/.env`:

```env
TELEGRAM_PROXY=http://127.0.0.1:7890
```

(или `socks5://127.0.0.1:1080` — локальный порт подставьте от своего VPN/прокси.)

После изменения перезапустите backend. В ответе **`/api/health`** смотрите `telegram_api_reachable` и `telegram_bot_username`.

## Fanvue

Интеграция по [документации Fanvue](https://api.fanvue.com/docs): вебхук входящих сообщений и REST API для ответов.

### Переменные окружения (`backend/.env`)

| Переменная | Назначение |
|------------|------------|
| `FANVUE_WEBHOOK_SECRET` | Секрет подписи вебхука (Developer Area → приложение → Webhooks → View Signing Secret). Без него вебхук принимается **без** проверки подписи (в лог пишется предупреждение). |
| `FANVUE_ACCESS_TOKEN` | Bearer-токен OAuth создателя со scope `write:chat` — нужен, чтобы отправлять ответы из UI. |
| `FANVUE_API_VERSION` | По умолчанию `2025-06-26` (заголовок `X-Fanvue-API-Version`). |
| `FANVUE_API_BASE` | По умолчанию `https://api.fanvue.com`. |

### URL вебхука

Укажите в кабинете разработчика Fanvue, например:

`https://<ваш-домен>/api/connectors/fanvue/webhook`

Для локальной отладки — туннель (ngrok и т.п.) с HTTPS.

Событие **Message Received** требует scope `read:chat` у подключённого приложения. Входящие пишутся в те же `Conversation` / `Message` с `platform=fanvue`. Идентификаторы: `external_chat_id` = UUID фана (отправителя), `external_topic_id` = UUID создателя (получателя вебхука).

Событие **Message Read** подтверждается ответом `200`, содержимое можно не хранить (непрочитанные в приложении считаются по своей логике).

### Отправка ответов

`POST /chats/{userUuid}/message` с телом `{"text": "..."}` — в пути `userUuid` это UUID собеседника (фана), совпадает с `external_chat_id` диалога.

## Развёртывание на сервере (Linux, nginx, закрытый UI)

Пошагово: каталог **`deploy/`** — скрипт `server-setup.sh`, пример **systemd** и **nginx** с паролем на интерфейс и отдельным публичным путём для вебхука Fanvue. См. **`deploy/README.md`**.
