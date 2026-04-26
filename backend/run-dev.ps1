# Запуск без перезапуска при изменении SQLite (data/):
# watch только каталог app/, чтобы не останавливался Telegram polling при записи в БД.
Set-Location $PSScriptRoot
$port = if ($env:PORT) { $env:PORT } else { "8080" }
# Для доступа с телефона по Wi‑Fi: $env:CHATING_BIND_HOST = "0.0.0.0"
$bindHost = if ($env:CHATING_BIND_HOST) { $env:CHATING_BIND_HOST } else { "127.0.0.1" }
python -m uvicorn app.main:app --reload --reload-dir app --host $bindHost --port $port
