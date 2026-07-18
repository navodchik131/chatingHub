# Кабинет OS на production (model-mate.online)

## Адреса

| Раздел | URL |
|--------|-----|
| **Лендинг** | https://model-mate.online/ |
| **Вход** | https://model-mate.online/login → `/workspace/` |
| **Кабинет** | https://model-mate.online/workspace/ |
| **Workflow** | https://model-mate.online/workspace/workflow/ |
| **Админка** | https://model-mate.online/admin |
| API | https://model-mate.online/api/ |
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

# API + кабинет (base /workspace/)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api frontend
```

## Обновление после правок

**Только кабинет:**

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build frontend
```

**Только API:**

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

## Локальная разработка

```bash
docker compose up -d --build
# кабинет http://127.0.0.1:5180/  ·  workflow http://127.0.0.1:5180/workflow/
cd frontend && npm install && npm run sync-design && npm run dev        # кабинет :5174
cd frontend && npm run dev:site                                          # лендинг :5173
cd frontend && npm run dev:workflow                                     # workflow :5175
```

## CORS

При доступе через `https://model-mate.online/workspace/` запросы идут на `https://model-mate.online/api/` — тот же origin, отдельный CORS не нужен.

В `backend/.env` на всякий случай:

```
CORS_ORIGINS=https://model-mate.online,http://127.0.0.1:8080
```
