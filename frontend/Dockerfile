# Единое SPA (маркетинг + кабинет + admin) + Workflow — статика + nginx, API проксируется на сервис api.
FROM node:22-alpine AS build
WORKDIR /app

ARG VITE_WORKFLOW_BASE=/workspace/workflow/
ENV VITE_WORKFLOW_BASE=$VITE_WORKFLOW_BASE

ENV npm_config_fund=false \
    npm_config_audit=false \
    npm_config_update_notifier=false

COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund

COPY frontend/ ./frontend/

RUN cd frontend && npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist-site /usr/share/nginx/html
COPY --from=build /app/frontend/dist/workflow /usr/share/nginx/html/workspace/workflow
EXPOSE 80
