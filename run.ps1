param(
  [switch]$Clean = $false,
  [switch]$NoLLM = $false,
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "[HealthDiary] Starting helper script..." -ForegroundColor Cyan

# Ensure venv
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
  Write-Host "[HealthDiary] Creating virtual environment..." -ForegroundColor Yellow
  python -m venv .venv
}

Write-Host "[HealthDiary] Activating virtual environment..." -ForegroundColor Cyan
. .\.venv\Scripts\Activate.ps1

# Install deps (idempotent)
Write-Host "[HealthDiary] Installing dependencies..." -ForegroundColor Cyan
pip install -r backend\requirements.txt | Out-Null

# Clean data if requested
if ($Clean) {
  Write-Host "[HealthDiary] Cleaning SQLite DB and temp doctor pack files..." -ForegroundColor Yellow
  $dbPath = "backend\app\data\healthdiary.db"
  if (Test-Path $dbPath) { Remove-Item -Force $dbPath }

  $tempDir = Join-Path $env:TEMP "healthdiary_pdf"
  if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
}

# Optionally disable LLM
if ($NoLLM) {
  Write-Host "[HealthDiary] Disabling LLM (heuristic fallback will be used)." -ForegroundColor Yellow
  $env:QWEN_ENDPOINT = ""
  $env:QWEN_API_KEY = ""
  $env:QWEN_MODEL = ""
}

# Reminder of current LLM config
if ($env:QWEN_ENDPOINT) {
  Write-Host "[HealthDiary] LLM enabled -> $($env:QWEN_ENDPOINT) (model: $($env:QWEN_MODEL))" -ForegroundColor Green
} else {
  Write-Host "[HealthDiary] LLM not configured -> using heuristic mode" -ForegroundColor DarkYellow
}

Write-Host "[HealthDiary] Launching server on port $Port ..." -ForegroundColor Cyan
uvicorn backend.app.main:app --reload --port $Port










