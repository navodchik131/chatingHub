# Новый кабинет OS — статика + nginx, API проксируется на сервис api.
FROM node:22-alpine AS build
WORKDIR /app

# На production: --build-arg VITE_BASE_PATH=/workspace/
ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=$VITE_BASE_PATH

ENV npm_config_fund=false \
    npm_config_audit=false \
    npm_config_update_notifier=false

COPY frontend-os/package.json frontend-os/package-lock.json ./frontend-os/
RUN cd frontend-os && npm ci --no-audit --no-fund

# Макет + исходники frontend-os (sync-design читает «Доработка дизайна» из корня репо)
COPY ["Доработка дизайна/", "./Доработка дизайна/"]
COPY frontend-os/ ./frontend-os/

RUN cd frontend-os && npm run sync-design && npm run build

FROM nginx:1.27-alpine
COPY frontend-os/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend-os/dist /usr/share/nginx/html
EXPOSE 80
