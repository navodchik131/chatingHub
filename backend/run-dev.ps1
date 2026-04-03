# Запуск без перезапуска при изменении SQLite (data/):
# watch только каталог app/, чтобы не останавливался Telegram polling при записи в БД.
Set-Location $PSScriptRoot
$port = if ($env:PORT) { $env:PORT } else { "8080" }
python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port $port
