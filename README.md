# Chating Hub

Единый инбокс для **Telegram Channel Direct Messages** с переводом входящих на русский и ответов с русского на язык собеседника. Заготовка под **Fanvue** (вебхук и коннектор).

## Стек

- **Backend:** Python, FastAPI, aiogram 3, SQLAlchemy async, PostgreSQL (прод) / SQLite (локально)  
- **Frontend:** React, TypeScript, Vite  
- **Перевод:** DeepL (если задан `DEEPL_API_KEY`), иначе публичный LibreTranslate  
- **SaaS:** регистрация, JWT, кредиты и подписка (ЮKassa), интеграции Telegram/Fanvue на пользователя, шифрование секретов (Fernet)

Подробная архитектура: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Docker (PostgreSQL + API со встроенным фронтом)

Из корня репозитория задайте в `.env` минимум `JWT_SECRET`, `FERNET_KEY`, `PUBLIC_APP_URL` (HTTPS в проде), затем:

```bash
docker compose up --build
```

Интерфейс: http://localhost:8080 — сначала **регистрация**, затем в «Кабинете» подключите Telegram и Fanvue.  
Пример переменных: [deploy/env.example](deploy/env.example).

Локальная SQLite-база из старых версий **несовместима** с новой схемой (нужен `user_id` у диалогов): удалите `backend/data/app.db` или перейдите на PostgreSQL.

**Локально протестировать Telegram webhook (HTTPS):** [docs/ngrok.md](docs/ngrok.md).

## Запуск

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

В `.env` для **SaaS** укажите `JWT_SECRET`, `FERNET_KEY`, при необходимости `DATABASE_URL` (PostgreSQL) и настройки ЮKassa — см. `backend/.env.example`. Интеграции Telegram/Fanvue задаются в UI после регистрации.

Для **legacy** long polling одного бота: `BOT_TOKEN` и `LEGACY_USER_ID` (id пользователя в БД после регистрации). Опционально: `DEEPL_API_KEY`.

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

Интеграция по [документации Fanvue](https://api.fanvue.com/docs).

### Администратор сервера (один раз)

1. В [Fanvue Developer Area](https://fanvue.com) создайте приложение **ChatingApp**.
2. **Authentication** → permissions: `read:chat`, `write:chat`, `offline_access`, `read:self`, `openid`.
3. **Authentication** → **Redirects** → добавьте:
   `https://<ваш-домен>/api/integrations/fanvue/oauth/callback`
4. **Events** → **View Signing Secret** → скопируйте в `.env` как `FANVUE_WEBHOOK_SIGNING_SECRET`.
5. **Events** → **Add Webhook** → URL `https://<ваш-domен>/api/webhooks/fanvue`, событие **Message Received**.
6. В `backend/.env`:
   - `FANVUE_CLIENT_ID`, `FANVUE_CLIENT_SECRET` из Authentication
   - `FANVUE_WEBHOOK_SIGNING_SECRET` из Events
   - `PUBLIC_APP_URL=https://<ваш-домен>`

Nginx: путь `/api/webhooks/fanvue` и `/api/integrations/fanvue/oauth/callback` **без** HTTP Basic Auth.

### Пользователь ModelMate

**Кабинет → Интеграции → Подключить Fanvue** — OAuth от своего creator-аккаунта. Токены и Creator UUID сохраняются автоматически. Webhook URL показывается в кабинете (копировать для проверки; регистрируется администратором один раз в Fanvue Events).

### Устаревший режим

Ручной `PUT /api/integrations/fanvue` с access token — если OAuth на сервере не настроен.

## Развёртывание на сервере (Linux, nginx, закрытый UI)

Пошагово: каталог **`deploy/`** — скрипт `server-setup.sh`, пример **systemd** и **nginx** с паролем на интерфейс и отдельным публичным путём для вебхука Fanvue. См. **`deploy/README.md`**.
