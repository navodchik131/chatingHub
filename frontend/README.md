# frontend — кабинет ModelMate OS

Источник вёрстки: `Доработка дизайна/ModelMate OS.dc.html` + `support.js`

| | Значение |
|---|---|
| Папка | `frontend/` |
| Docker | сервис `frontend`, порт http://127.0.0.1:5180/ |
| Production | https://model-mate.online/workspace/ |
| API | тот же backend (`api`), токен `localStorage.chating_token` |

## Запуск (Docker)

```bash
docker compose up -d --build
```

- **API:** http://127.0.0.1:8080/ (только `/api/*`, без SPA)
- **Кабинет:** http://127.0.0.1:5180/
- **Workflow:** http://127.0.0.1:5180/workflow/

Пересобрать после правок:

```bash
docker compose up -d --build frontend
```

## Локальная разработка (без Docker для фронта)

```bash
docker compose up -d api db
cd frontend
npm install
npm run dev                   # http://127.0.0.1:5174/, proxy → :8080
```

## Синхронизация с макетом

После правок в `Доработка дизайна/`:

```bash
cd frontend
npm run sync-design:legacy
docker compose up -d --build frontend
```

## Как устроено

- **Prod:** React SPA (`src/cabinet`, `npm run build:site` → `dist-site`).
- **Legacy (не prod):** `legacy/design-code/` + `legacy/mm-os/` — DesignCode-макет, `npm run sync-design:legacy`.
- `Dockerfile` + `nginx.conf` — статика и proxy `/api` → `api:8080`.

## Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Nginx: `deploy/nginx-model-mate.online.conf` — см. `deploy/PRODUCTION-OS.md`.
