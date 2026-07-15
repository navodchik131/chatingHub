# frontend-os — новый кабинет с макета (параллельно со старым)

Источник вёрстки: `Доработка дизайна/ModelMate OS.dc.html` + `support.js`

| | Старый | Новый (OS) |
|---|---|---|
| Папка | `frontend/` (в образе `api`) | `frontend-os/` |
| URL в Docker | http://127.0.0.1:8080/ | http://127.0.0.1:5180/ |
| Токен | `localStorage.chating_token` | тот же |

## Запуск (всё в Docker)

```bash
docker compose up -d --build
```

- **API + старый кабинет:** http://127.0.0.1:8080/
- **Новый кабинет OS:** http://127.0.0.1:5180/

Оба фронта ходят в один `api`, не мешают друг другу.

**Вход:** токен в cookie `path=/` — если залогинены на :8080, на :5180 подхватится автоматически (обновите :8080 после пересборки `api`). Иначе войдите на экране логина OS.

Пересобрать после правок:

```bash
docker compose up -d --build frontend-os
```

## Локальная разработка (без Docker)

```bash
docker compose up -d api db   # только бэкенд
cd frontend-os
npm install
npm run dev                   # http://127.0.0.1:5174/, proxy → :8080
```

## Синхронизация с макетом

После правок в `Доработка дизайна/`:

```bash
cd frontend-os
npm run sync-design
# для Docker:
docker compose up -d --build frontend-os
```

## Как устроено

- `public/mm-os-api.js` — JWT, fetch, студийные job'ы.
- `public/mm-os-bridge.js` — подмена mock-данных, WebSocket, действия UI.
- `scripts/sync-design.mjs` — копия макета + патчи API.
- `Dockerfile` + `nginx.conf` — статика и proxy `/api` → `api:8080`.

Когда новый кабинет готов — заменим отдачу основного фронта в `api` на `frontend-os/dist`.

## Production (model-mate.online)

- **Старый:** https://model-mate.online/
- **Новый OS:** https://model-mate.online/os/

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Nginx: `deploy/nginx-model-mate.online.conf` — см. `deploy/PRODUCTION-OS.md`.
