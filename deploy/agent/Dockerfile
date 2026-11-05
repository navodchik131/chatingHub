# Persona Studio в режиме «хостинг» (кабинет model-mate, /workspace/agent/).
# Код — agent/ (обновляется scripts/sync-agent.ps1 из локальной Persona Studio).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY deploy/agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
# модель вырезания человека для силуэтов — в образ, чтобы не качать на первом запросе
ENV U2NET_HOME=/models
RUN python -c "from rembg import new_session; new_session('u2net_human_seg')"
COPY agent/ /app/
ENV PS_DATA=/data HOST=0.0.0.0 PORT=8765 PYTHONUNBUFFERED=1
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://127.0.0.1:8765/ >/dev/null || exit 1
CMD ["python", "server.py"]
