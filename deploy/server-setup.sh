#!/usr/bin/env bash
# Установка Chating Hub в указанную директорию (клон уже должен лежать там или будет ошибка).
# Использование: bash deploy/server-setup.sh --port 18080 --dir /opt/chatinghub

set -euo pipefail

PORT="18080"
TARGET_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --dir) TARGET_DIR="$2"; shift 2 ;;
    *) echo "Неизвестный аргумент: $1"; exit 1 ;;
  esac
done

if [[ -z "$TARGET_DIR" ]]; then
  echo "Укажите --dir /полный/путь/к/репозиторию"
  exit 1
fi

if [[ ! -d "$TARGET_DIR/backend" ]]; then
  echo "Нет каталога $TARGET_DIR/backend — сначала git clone репозитория в $TARGET_DIR"
  exit 1
fi

if command -v ss >/dev/null 2>&1; then
  if ss -tlnp 2>/dev/null | grep -qE ":${PORT}[[:space:]]|:${PORT}\$"; then
    echo "Порт ${PORT} уже занят. Выберите другой: ss -tlnp"
    exit 1
  fi
else
  echo "Команда ss не найдена — проверьте порт ${PORT} вручную."
fi

BACKEND="$TARGET_DIR/backend"
FRONT="$TARGET_DIR/frontend"

cd "$BACKEND"
python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cd "$FRONT"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run sync-design
npm run build

echo ""
echo "=== Готово ==="
echo "Backend venv: $BACKEND/.venv"
echo "Статика фронта: $FRONT/dist"
echo ""
echo "Запуск вручную (проверка):"
echo "  cd $BACKEND && . .venv/bin/activate"
echo "  set -a && [ -f .env ] && . ./.env && set +a"
echo "  export PORT=$PORT"
echo "  exec uvicorn app.main:app --host 127.0.0.1 --port $PORT"
echo ""
echo "Скопируйте deploy/chatinghub.service.example в /etc/systemd/system/chatinghub.service,"
echo "замените пути и PORT=$PORT, затем: sudo systemctl daemon-reload && sudo systemctl enable --now chatinghub"
