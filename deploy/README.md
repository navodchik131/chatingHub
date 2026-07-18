# Развёртывание на Linux-сервере

## Безопасность

1. **Не храните** GitHub-токены в репозитории и в скриптах с фиксированной строкой.
2. На сервере клонируйте так: экспортируйте токен в сессии и клонируйте один раз, либо используйте **SSH deploy key** (рекомендуется для production).
3. Пароль для веб-интерфейса — через **nginx** `auth_basic` (см. `nginx-chatinghub.conf.example`).  
   **Важно:** путь `POST /api/connectors/fanvue/webhook` в примере **без** пароля — иначе Fanvue не сможет доставлять события.

## Порты

- Backend (uvicorn) слушает **только localhost** (например `127.0.0.1:18080`).
- Снаружи — **443** (nginx). Свободный порт для uvicorn выберите скриптом или вручную:  
  `ss -tlnp | head -50` — посмотреть занятые порты.

## Быстрый старт

```bash
# 1) На сервере (Debian/Ubuntu): зависимости
sudo apt update
sudo apt install -y git python3 python3-venv nodejs npm nginx apache2-utils

# 2) Клон (пример с токеном только в переменной окружения — токен не светите в истории bash)
export GITHUB_TOKEN='ваш_новый_токен'
git clone "https://${GITHUB_TOKEN}@github.com/navodchik131/chatingHub.git" /opt/chatinghub
unset GITHUB_TOKEN

# 3) Установка и выбор порта (например 18080)
cd /opt/chatinghub
sudo bash deploy/server-setup.sh --port 18080 --dir /opt/chatinghub

# 4) Скопируйте backend/.env с секретами (BOT_TOKEN, Fanvue, и т.д.)
# 5) systemd: скопируйте unit из вывода скрипта или из deploy/chatinghub.service.example
# 6) nginx: скопируйте и подправьте deploy/nginx-chatinghub.conf.example
sudo htpasswd -c /etc/nginx/.htpasswd-chatinghub admin
sudo nginx -t && sudo systemctl reload nginx
```

`CORS_ORIGINS` в `backend/.env` должен включать ваш HTTPS-домен.

## Обновление

```bash
cd /opt/chatinghub
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api frontend
```
