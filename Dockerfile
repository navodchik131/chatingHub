# Сборка фронтенда (Alpine — меньше образ, но npm тянет пакеты с сети: на слабом канале шаг может
# идти 5–15+ мин без новых строк в логе; сборка с --progress=plain покажет прогресс).
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend

# Меньше «тишины» и лишних запросов при установке.
# На VPS с 1–2 ГБ RAM параллельный npm часто упирается в OOM → процесс режут (часто exit 146).
# Ограничиваем сокеты/параллелизм; при желании на хосте добавьте 1–2 ГБ swap.
ENV npm_config_fund=false \
    npm_config_audit=false \
    npm_config_update_notifier=false \
    npm_config_fetch_retries=5 \
    npm_config_fetch_retry_mintimeout=20000 \
    npm_config_fetch_retry_maxtimeout=120000 \
    npm_config_maxsockets=2

COPY frontend/package.json frontend/package-lock.json ./
# ci быстрее и детерминированнее install; при рассинхроне lock откатится на install
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# Backend + статика SPA
FROM python:3.12-slim
WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DEBCONF_NONINTERACTIVE_SEEN=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY backend/ ./
# Промпты вне тома data/ (compose монтирует chating_app_data на /app/backend/data).
COPY backend/data/prompts/ ./_bundled_prompts/
COPY backend/data/workflow_templates/ ./_bundled_workflow_templates/
COPY --from=frontend-build /app/frontend/dist ../frontend/dist

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
