# Скопировать Persona Studio (B:\Nika\persona-studio) в agent/ этого репозитория — оттуда собирается контейнер agent.
# Данные (data/), кэш и личные правила (prompts/rules.md) не копируются.
#   powershell -ExecutionPolicy Bypass -File scripts\sync-agent.ps1 [-Source B:\Nika\persona-studio]
param([string]$Source = "B:\Nika\persona-studio")
$ErrorActionPreference = "Stop"
$dst = Join-Path $PSScriptRoot "..\agent"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($f in @("server.py", "recipes.py", "hosted.py", "lineart.py")) { Copy-Item (Join-Path $Source $f) $dst -Force }
robocopy (Join-Path $Source "static") (Join-Path $dst "static") /MIR /NFL /NDL /NJH /NJS | Out-Null
New-Item -ItemType Directory -Force (Join-Path $dst "prompts") | Out-Null
foreach ($f in @("system.md", "system.default.md", "rules.default.md")) { Copy-Item (Join-Path $Source "prompts\$f") (Join-Path $dst "prompts") -Force }
Write-Host "agent/ обновлён из $Source"
