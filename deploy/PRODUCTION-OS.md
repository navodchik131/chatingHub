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

### Workflow (важно)

Новый workflow — React SPA (~600 байт HTML). Legacy OS — ~219 KB.

```bash
# снаружи (HTTPS)
curl -sI https://model-mate.online/workspace/workflow/ | grep -i content-length
curl -s https://model-mate.online/workspace/workflow/ | head -3
# ожидается: content-length ~600 и <!doctype html> ... ModelMate Workflow

# напрямую в docker-frontend (обходит host nginx)
curl -sI http://127.0.0.1:5180/workflow/ | grep -i content-length
curl -s http://127.0.0.1:5180/workflow/ | head -3
```

Если `:5180/workflow/` правильный, а HTTPS — 219062: проблема в **host nginx** (старый конфиг).  
Если оба 219062: **frontend-образ не пересобран** — см. ниже.

## Workflow не открывается (219 KB HTML, `{{lightboxData}}`, ошибки JS)

1. Убедитесь, что код актуален: `git log -1 --oneline` (нужны коммиты с fix workflow nginx).
2. Пересоберите frontend **без кэша**:

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d frontend
```

3. Host nginx — workflow должен идти в `:5180`, не в `:8080`:

```bash
sudo cp deploy/nginx-model-mate.online.conf /etc/nginx/sites-available/model-mate.online
sudo nginx -t && sudo systemctl reload nginx
grep -A2 'workspace/workflow' /etc/nginx/sites-enabled/model-mate.online
# не должно быть proxy_pass на 8080 для workflow
```

4. Проверка внутри контейнера:

```bash
docker compose exec frontend head -3 /usr/share/nginx/html/workspace/workflow/index.html
docker compose exec frontend wc -c /usr/share/nginx/html/index.html
# workflow/index.html — ModelMate Workflow; корневой index.html — ~1500 байт, не 219000
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
