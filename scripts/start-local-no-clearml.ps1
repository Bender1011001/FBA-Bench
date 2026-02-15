Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== FBA Local GUI Startup (No ClearML) ==="

# 1) Prologue and repo root resolution
$scriptRoot = $PSScriptRoot
if (-not $scriptRoot) {
  $scriptRoot = Split-Path -Parent $PSCommandPath
}
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
Set-Location $repoRoot
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# 2) Prerequisite checks
Write-Host "`n-- Checking prerequisites --"
try {
  $pyVerStr = & python --version 2>&1
} catch {
  throw "Python not found. Install Python 3.10–3.13 and ensure 'python' is on PATH."
}
$pyVerMatch = [regex]::Match($pyVerStr, 'Python\s+(\d+)\.(\d+)\.(\d+)')
if (-not $pyVerMatch.Success) { throw "Unable to parse Python version output: $pyVerStr" }
$pyMajor = [int]$pyVerMatch.Groups[1].Value
$pyMinor = [int]$pyVerMatch.Groups[2].Value
if ($pyMajor -ne 3 -or $pyMinor -lt 10 -or $pyMinor -gt 13) {
  throw "Python 3.10–3.13 required, found $($pyVerMatch.Groups[1].Value).$($pyVerMatch.Groups[2].Value).$($pyVerMatch.Groups[3].Value)"
}

try { & poetry --version | Out-Null } catch { throw "Poetry is required. Install from https://python-poetry.org/docs/#installation" }
try { & node --version | Out-Null } catch { throw "Node.js is required. Install from https://nodejs.org/" }
try { & npm --version | Out-Null } catch { throw "npm is required (bundled with Node.js)" }
try { & docker --version | Out-Null } catch { throw "Docker Desktop is required. Install and ensure it's running." }
try { & docker info -f '{{json .ServerVersion}}' | Out-Null } catch { throw "Docker daemon not running. Start Docker Desktop." }
Write-Host "✅ Prerequisites OK: Python, Poetry, Node/npm, Docker"

# 3) .env handling and ClearML hard-disable
Write-Host "`n-- Ensuring .env and disabling ClearML --"
$envFile = Join-Path $repoRoot ".env"
$envExample = Join-Path $repoRoot ".env.example"
if (!(Test-Path $envFile) -and (Test-Path $envExample)) {
  Copy-Item $envExample $envFile -Force
  Write-Host "Copied .env from .env.example"
}
$ensureLines = @(
  "FBA_FEATURES__ENABLE_CLEARML=false",
  "CLEARML_API_ACCESS_KEY=",
  "CLEARML_API_SECRET_KEY=",
  "CLEARML_WEB_HOST="
)
if (Test-Path $envFile) {
  $existing = Get-Content $envFile -ErrorAction SilentlyContinue
} else {
  $existing = @()
}
foreach ($line in $ensureLines) {
  if ($existing -notcontains $line) {
    Add-Content -Path $envFile -Value $line
  }
}
Write-Host "🔒 ClearML disabled via environment settings."

# 4) Start data services (Docker)
Write-Host "`n-- Starting data services (Docker) --"
# PostgreSQL
$pgName = "fba-postgres-local"
$POSTGRES_DB = "fba_bench"
$POSTGRES_USER = "fba_user"
$POSTGRES_PASSWORD = "localdev123"
$pgImage = "postgres:13"
$pgExists = $false
$pgRunning = $false
try {
  $pgState = & docker inspect -f '{{.State.Status}}' $pgName 2>$null
  if ($LASTEXITCODE -eq 0 -and $pgState) { $pgExists = $true; $pgRunning = ($pgState.Trim() -eq "running") }
} catch { $pgExists = $false }
if (-not $pgExists) {
  Write-Host "Launching PostgreSQL container '$pgName'..."
  & docker run -d --name $pgName `
    -e "POSTGRES_DB=fba_bench" `
    -e "POSTGRES_USER=fba_user" `
    -e "POSTGRES_PASSWORD=localdev123" `
    -p 5432:5432 `
    -v postgres_data:/var/lib/postgresql/data `
    $pgImage | Out-Null
} elseif (-not $pgRunning) {
  Write-Host "Starting existing PostgreSQL container..."
  & docker start $pgName | Out-Null
} else {
  Write-Host "PostgreSQL already running."
}
# Wait for readiness
$pgTimeoutSec = 90
$pgStart = Get-Date
$pgReady = $false
while ((New-TimeSpan -Start $pgStart -End (Get-Date)).TotalSeconds -lt $pgTimeoutSec) {
  try {
    $out = & docker exec $pgName pg_isready -h localhost -U $POSTGRES_USER -d $POSTGRES_DB 2>&1
    if ($LASTEXITCODE -eq 0 -and ($out -match "accepting connections")) { $pgReady = $true; break }
  } catch { }
  Start-Sleep -Seconds 2
}
if (-not $pgReady) { throw "PostgreSQL did not become ready within $pgTimeoutSec seconds." }
Write-Host "✅ PostgreSQL ready."
# Bootstrap schema owners with init-db.sql (once per container lifecycle)
$initSql = Join-Path $repoRoot "scripts\init-db.sql"
$markerPath = "/var/lib/postgresql/data/.fba_bootstrapped"
$needBootstrap = $true
try {
  & docker exec $pgName test -f $markerPath
  if ($LASTEXITCODE -eq 0) { $needBootstrap = $false }
} catch { $needBootstrap = $true }
if ($needBootstrap) {
  if (Test-Path $initSql) {
    Write-Host "Applying database bootstrap from scripts\init-db.sql..."
    & docker cp $initSql "${pgName}:/tmp/init-db.sql"
    & docker exec $pgName bash -lc "export PGPASSWORD='$POSTGRES_PASSWORD'; psql -h localhost -U '$POSTGRES_USER' -d '$POSTGRES_DB' -v ON_ERROR_STOP=1 -v app_user='$POSTGRES_USER' -f /tmp/init-db.sql && touch $markerPath"
    if ($LASTEXITCODE -ne 0) { throw "Failed to bootstrap database with init-db.sql" }
  } else {
    Write-Warning "scripts\init-db.sql not found; skipping bootstrap."
  }
} else {
  Write-Host "DB bootstrap already applied; skipping."
}
# Redis
$redisName = "fba-redis-dev"
$redisImage = "redis:7"
$redisState = ""
try { $redisState = & docker inspect -f '{{.State.Status}}' $redisName 2>$null } catch { }
if (-not $redisState) {
  Write-Host "Launching Redis container '$redisName'..."
  & docker run -d --name $redisName -p 6379:6379 $redisImage | Out-Null
} elseif ($redisState.Trim() -ne "running") {
  Write-Host "Starting existing Redis container..."
  & docker start $redisName | Out-Null
} else {
  Write-Host "Redis already running."
}
Write-Host "✅ Redis ready."

# 5) Python deps and DB migrations
Write-Host "`n-- Installing Python dependencies and running migrations --"
& poetry install --with dev
$env:DATABASE_URL = "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:FBA_BENCH_REDIS_URL = "redis://localhost:6379/0"
& poetry run alembic upgrade head

# 6) Start Backend API (uvicorn) in background job
Write-Host "`n-- Starting Backend API (Uvicorn) --"
$apiLog = Join-Path $repoRoot "logs\api.log"
Add-Content -Path $apiLog -Value "`n==== API start $(Get-Date -Format s) ===="
Get-Job -Name "fba-api" -ErrorAction SilentlyContinue | Stop-Job -Force -ErrorAction SilentlyContinue
Get-Job -Name "fba-api" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
$null = Start-Job -Name "fba-api" -ScriptBlock {
  $env:DATABASE_URL = "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
  $env:REDIS_URL = "redis://localhost:6379/0"
  $env:FBA_BENCH_REDIS_URL = "redis://localhost:6379/0"
  $env:FBA_FEATURES__ENABLE_CLEARML = "false"
  $env:CLEARML_API_ACCESS_KEY = ""
  $env:CLEARML_API_SECRET_KEY = ""
  $env:CLEARML_WEB_HOST = ""
  Set-Location "$using:repoRoot"
  poetry run uvicorn fba_bench_api.main:app --factory --host 0.0.0.0 --port 8000 --reload --log-level info *>> "$using:apiLog"
}
# Wait for API readiness
$apiReady = $false
$apiDeadline = (Get-Date).AddSeconds(60)
while (Get-Date -lt $apiDeadline) {
  try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 5
    if ($resp -or $LASTEXITCODE -eq 0) { $apiReady = $true; break }
  } catch { }
  Start-Sleep -Seconds 2
}
if ($apiReady) {
  Write-Host "✅ API ready at http://localhost:8000"
} else {
  Write-Warning "API not ready yet; check logs\api.log"
}

# 7) Start Frontend (Vite) in background job
Write-Host "`n-- Starting Frontend (Vite) --"
$frontendDir = Join-Path $repoRoot "frontend"
$feLog = Join-Path $repoRoot "logs\frontend.log"
if (!(Test-Path $frontendDir)) {
  Write-Warning "Frontend directory not found at $frontendDir; skipping frontend start."
} else {
  Set-Location $frontendDir
  if (!(Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies (npm ci)..."
    & npm ci
  } else {
    Write-Host "Frontend dependencies present."
  }
  Add-Content -Path $feLog -Value "`n==== Frontend start $(Get-Date -Format s) ===="
  Get-Job -Name "fba-frontend" -ErrorAction SilentlyContinue | Stop-Job -Force -ErrorAction SilentlyContinue
  Get-Job -Name "fba-frontend" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
  $null = Start-Job -Name "fba-frontend" -ScriptBlock {
    $env:VITE_API_URL = "http://localhost:8000"
    Set-Location "$using:repoRoot\frontend"
    npm run dev -- --host 0.0.0.0 *>> "$using:feLog"
  }
  Write-Host "✅ Frontend started at http://localhost:5173"
}

# 8) Final summary
Set-Location $repoRoot
Write-Host "`n=== Local GUI stack started (no ClearML) ==="
Write-Host "API:      http://localhost:8000    (Docs: /docs, Health: /health)"
Write-Host "Frontend: http://localhost:5173"
Write-Host "Logs:"
Write-Host "  - $apiLog"
Write-Host "  - $feLog"
Write-Host ""
Write-Host "To stop: use the optional stop script: scripts\stop-local-no-clearml.ps1 (if present)"
exit 0
