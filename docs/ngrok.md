# Локальная отладка с ngrok (HTTPS для Telegram webhook)

Telegram принимает webhook только по **HTTPS**. Ngrok даёт временный публичный URL и проксирует трафик на ваш локальный порт.

## Важно: какой порт проксировать

Вебхуки бьют в **FastAPI** (`/api/webhooks/...`), а не в Vite.

- Backend у вас обычно на **8080** (`run-dev.ps1`).
- Команда: **`ngrok http 8080`** (не 5173).

Если фронт крутите через Vite (`5173`), в браузере можно по-прежнему открывать `http://127.0.0.1:5173` — запросы к API идут через прокси Vite на тот же backend. А **PUBLIC_APP_URL** должен быть именно **HTTPS ngrok**, чтобы `setWebhook` зарегистрировал правильный адрес.

## Шаги (Windows)

### 1. Установить ngrok

- Скачайте с [ngrok.com/download](https://ngrok.com/download) или:  
  `winget install ngrok.ngrok`
- Один раз привяжите токен (из [dashboard.ngrok.com](https://dashboard.ngrok.com)):  
  `ngrok config add-authtoken <ВАШ_ТОКЕН>`

### 2. Запустить backend на 8080

```powershell
cd b:\work\chating\backend
.\run-dev.ps1
```

Убедитесь, что `PORT` / скрипт дают **8080** (или запомните свой порт и подставьте его в ngrok).

### 3. Запустить туннель (второй терминал)

```powershell
ngrok http 8080
```

В выводе возьмите **Forwarding** вида `https://xxxx.ngrok-free.app` (или `ngrok.io`).

### 4. Прописать URL в `.env` backend

В `backend/.env`:

```env
PUBLIC_APP_URL=https://xxxx.ngrok-free.app
```

Без слэша в конце. **Перезапустите** `run-dev.ps1`, чтобы подтянулся новый URL.

### 5. Снова сохранить Telegram в кабинете

В UI: **Кабинет** → вставить bot token → **Сохранить Telegram**.  
Так вызовется `setWebhook` уже на ngrok-адрес.

### 6. Проверка

- В логах backend не должно быть ошибки `bad webhook`.
- Напишите боту в Direct messages канала — сообщение должно появиться в списке диалогов.

## Бесплатный ngrok

- URL **меняется** при каждом новом запуске туннеля → после рестарта ngrok снова обновите `PUBLIC_APP_URL` и **ещё раз** нажмите «Сохранить Telegram».
- Иногда у бесплатного домена есть особенности (страница-предупреждение в браузере); **POST от Telegram** обычно проходит. Если нет — смотрите [dashboard ngrok → Requests](https://dashboard.ngrok.com).

## Один URL для всего (по желанию)

Чтобы открывать интерфейс тоже по HTTPS с того же хоста:

```powershell
cd b:\work\chating\frontend
npm run build
cd ..\backend
# uvicorn на 8080 уже отдаёт и API, и собранный SPA — см. README
python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8080
```

Затем `ngrok http 8080` и в браузере: `https://xxxx.ngrok-free.app`.

## CORS

Если когда-нибудь откроете фронт **на другом origin**, чем API, добавьте ngrok-URL в `CORS_ORIGINS` в `backend/.env` (через запятую).
