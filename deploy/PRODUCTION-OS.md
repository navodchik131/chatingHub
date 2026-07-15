# Новый кабинет OS на production (model-mate.online)

## Адреса

| Кабинет | URL |
|---------|-----|
| Старый (как сейчас) | https://model-mate.online/ |
| Новый OS | https://model-mate.online/os/ |

Оба работают параллельно, один API и одна БД. Cookie `chating_token` общий (path=/).

## Деплой на сервер (один раз + обновления)

```bash
cd /opt/chatinghub   # или ваш каталог проекта
git pull

# Собрать с base path /os/ для production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Nginx (первый раз)
sudo cp deploy/nginx-model-mate.online.conf /etc/nginx/sites-available/model-mate.online
sudo ln -sf /etc/nginx/sites-available/model-mate.online /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Обновление после правок в frontend-os

```bash
cd /opt/chatinghub
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build frontend-os
```

## Обновление только старого кабинета

```bash
docker compose up -d --build api
```

## Проверка

```bash
curl -sI https://model-mate.online/os/ | head -5
curl -s https://model-mate.online/api/health
docker compose ps
```

## Локальная разработка (без /os/)

```bash
docker compose up -d --build          # frontend-os на http://127.0.0.1:5180/ (base /)
```

## CORS

При доступе через `https://model-mate.online/os/` запросы идут на `https://model-mate.online/api/` — тот же origin, отдельный CORS не нужен.

В `backend/.env` на всякий случай:

```
CORS_ORIGINS=https://model-mate.online,http://127.0.0.1:8080
```
