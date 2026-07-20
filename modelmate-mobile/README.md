# ModelMate Mobile (Expo)

Нативное приложение iOS / Android по дизайну `Редизайн кабинета Model Mate (4)/ModelMate Mobile.dc.html`.

Полный кликабельный прототип: все вкладки, подменю, формы генерации, персонажи, биллинг, команда, admin.

## Запуск

```bash
cd modelmate-mobile
npm install
npm start
```

- **Android:** Expo Go или эмулятор Android Studio
- **Web preview:** `npm run web`
- **iOS:** iPhone + Expo Go или EAS Build

## Навигация (как в макете)

**Старт:** экран авторизации (email, Telegram, Face ID) → после входа — 5 вкладок.

**5 вкладок:** Обзор · Диалоги · Студия · Персонажи · Профиль

| Раздел | Экраны |
|--------|--------|
| Обзор | KPI, быстрые ссылки в студию, недавние диалоги |
| Auth | логин, Telegram, биометрия |
| Диалоги | фильтры, список, чат с переводом и полем ввода |
| Студия | Картинки (6 режимов + формы), Видео, Архив |
| Персонажи | список, новый, карточка (Фото / Персона / EXIF / История) |
| Профиль | Тариф, Донаты, Подключения, Команда, Настройки |
| Admin | обзор, пользователи, рассылки, EXIF/IG боты, донаты |

## API (FastAPI)

1. Скопируйте `.env.example` → `.env` и укажите URL бэкенда:

```bash
EXPO_PUBLIC_API_URL=http://10.0.2.2:8080
```

2. Запустите backend (`uvicorn` или Docker) на порту **8080**.

3. Войдите тем же email/паролем, что и в веб-кабинете.

Токен хранится в **SecureStore** (`chating_token`), все запросы — `Authorization: Bearer`.

### Что подключено к API

- Auth: login, session `/api/auth/me`
- Диалоги: список, сообщения, отправка
- Студия: генерация картинок (workflow), видео, архив
- Персонажи: CRUD, загрузка фото, профиль
- Подключения: Telegram, Tribute
- Биллинг: checkout YooKassa/Tribute
- Донаты, команда, admin-разделы

## Структура

```
app/index.tsx
src/api/                 # HTTP client, actions, mappers
src/context/AppDataProvider.tsx
src/screens/ScreenRouter.tsx
src/data/mock.ts         # UI-константы (режимы студии, права)
```
