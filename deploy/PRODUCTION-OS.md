# Новый кабинет OS на production (model-mate.online)

## Адреса

| Раздел | URL |
|--------|-----|
| Маркетинг (лендинг, pricing, login) | https://model-mate.online/ |
| **Кабинет OS** | https://model-mate.online/workspace/ |
| Workflow (пока старый редактор) | https://model-mate.online/workspace/workflow |
| Старый путь (редирект) | https://model-mate.online/os/ → `/workspace/` |

Один API и одна БД. Cookie `chating_token` общий (path=/).

## Деплой на сервер (один раз + обновления)

```bash
cd /opt/chatinghub   # или ваш каталог проекта
git pull

# Nginx (при смене конфига)
sudo cp deploy/nginx-model-mate.online.conf /etc/nginx/sites-available/model-mate.online
sudo ln -sf /etc/nginx/sites-available/model-mate.online /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Собрать: маркетинг (api) + кабинет OS с base /workspace/
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api frontend-os
```

## Обновление после правок

**Только кабинет OS:**

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build frontend-os
```

**Только маркетинг / favicon:**

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api
```

## Проверка

```bash
curl -sI https://model-mate.online/workspace/ | head -5
curl -sI https://model-mate.online/os/ | head -3    # должен быть 301 → /workspace/
curl -s https://model-mate.online/api/health
docker compose ps
```

## Локальная разработка (без /workspace/)

```bash
docker compose up -d --build          # frontend-os на http://127.0.0.1:5180/ (base /)
```

Маркетинг + старый `/workspace` в dev: `cd frontend && npm run dev` или api на :8080.

## CORS

При доступе через `https://model-mate.online/workspace/` запросы идут на `https://model-mate.online/api/` — тот же origin, отдельный CORS не нужен.

В `backend/.env` на всякий случай:

```
CORS_ORIGINS=https://model-mate.online,http://127.0.0.1:8080
```
