# start-dev.ps1 - Windows PowerShell script to start FBA-Bench dev environment
# Orchestrates: Poetry install (backend), npm install/dev (frontend), Redis (Docker), API (uvicorn --reload)
# Usage: .\scripts\start-dev.ps1 [Stop] - Run in repo root; creates logs in ~/.fba/logs
# Requirements: PowerShell 5.1+, Poetry, Node.js/npm, Docker Desktop (for Redis; optional local)
# Best practices: Error handling, UTF-8, logging, health checks, parallel jobs (Start-Job)

param([switch]$Stop)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$OutputEncoding = [Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$env:NO_COLOR = '1'

# ---- Logging ----
$LogDir = Join-Path $env:USERPROFILE '.fba\logs'
$null = New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("start-dev-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Log([string]$lvl, [string]$msg) {
  $line = "[{0}] {1} {2}" -f ((Get-Date).ToString('o')), $lvl, $msg
  $color = if ($lvl -eq 'ERROR') { 'Red' } elseif ($lvl -eq 'WARN') { 'Yellow' } else { 'Green' }
  Write-Host $line -ForegroundColor $color
  $line | Add-Content -Path $LogFile -Encoding utf8
}
function Info($m) { Log 'INFO' $m }
function Warn($m) { Log 'WARN' $m }
function Err($m) { Log 'ERROR' $m; exit 1 }

# ---- Repo root ----
$__scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (& git -C $__scriptDir rev-parse --show-toplevel 2>$null); if (-not $repoRoot) { $repoRoot = $__scriptDir }
$repoRoot = Resolve-Path $repoRoot

if ($Stop) {
  Info "Stopping dev services"
  Stop-Job -Name 'fba-api', 'fba-frontend' -ErrorAction SilentlyContinue
  Remove-Job -Name 'fba-api', 'fba-frontend' -ErrorAction SilentlyContinue
  docker stop fba-redis-dev -ErrorAction SilentlyContinue
  docker rm fba-redis-dev -ErrorAction SilentlyContinue
  Info "Stopped"
  exit 0
}

Info "Starting FBA-Bench dev environment"
Info "Repo root: $repoRoot"

# ---- Env setup ----
if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env' -Force
  Warn "Created .env from example - edit with API keys (e.g., OPENAI_API_KEY)"
}
# Load .env (simple parse; for prod use python-dotenv if needed)
Get-Content '.env' | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') {
    $varName = $matches[1].Trim()
    $varValue = $matches[2].Trim()
    Set-Item "env:$varName" -Value $varValue -Force
  }
}

# Dev defaults (override .env if missing)
$env:AUTH_ENABLED = if ($env:AUTH_ENABLED) { $env:AUTH_ENABLED } else { 'false' }
$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { 'sqlite+aiosqlite:///./dev.db' }
$env:LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { 'INFO' }

# ---- Prereqs check ----
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) { Err "Poetry not found - install: pip install poetry" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Err "npm not found - install Node.js from nodejs.org" }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Warn "Docker not found - install Desktop from docker.com (needed for Redis); continuing without" } else { $hasDocker = $true }

# ---- Backend (Poetry) ----
Push-Location $repoRoot
Info "Installing backend deps with Poetry"
& poetry install --with dev --no-interaction 2>&1 | ForEach-Object { Info "Poetry: $_" }
if ($LASTEXITCODE) { Err "Poetry install failed (exit $LASTEXITCODE)" }
Info "Backend installed"

# DB migrate (if Alembic available)
Info "Running DB migrations"
& poetry run alembic upgrade head 2>&1 | ForEach-Object { Info "Alembic: $_" }
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { Warn "Migrations failed (exit $LASTEXITCODE) - may be OK if no DB changes" }

# ---- Frontend ----
Set-Location frontend
Info "Installing frontend deps with npm"
& npm ci 2>&1 | ForEach-Object { Info "npm: $_" }
if ($LASTEXITCODE) { Err "npm ci failed (exit $LASTEXITCODE)" }
Info "Frontend installed"

# ---- Redis (Docker preferred; fallback local if installed) ----
if ($hasDocker) {
  Info "Starting Redis via Docker"
  docker run -d --name fba-redis-dev -p 6379:6379 redis:alpine redis-server --appendonly yes 2>&1 | ForEach-Object { Info "Docker Redis: $_" }
  if ($LASTEXITCODE) { Err "Redis Docker failed" }
} else {
  Warn "No Docker - start Redis manually (e.g., redis-server if installed)"
}

# ---- Start API (background job) ----
Info "Starting API (uvicorn --reload)"
$apiJob = Start-Job -ScriptBlock {
  param($repoRoot, $LogFile)
  Set-Location $repoRoot
  & poetry run uvicorn fba_bench_api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload --log-level info 2>&1 | ForEach-Object {
    $line = "API: $_"
    Write-Output $line
    $line | Add-Content -Path $LogFile -Encoding utf8
  }
} -ArgumentList $repoRoot, $LogFile -Name 'fba-api'
if (-not $apiJob) { Err "Failed to start API job" }
Info "API job started (ID: $($apiJob.Id))"

# Wait a bit for API startup
Start-Sleep 5

# Health check API
$healthOk = $false
for ($i = 1; $i -le 30; $i++) {
  try {
    $r = Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/health' -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $healthOk = $true; break }
  } catch {}
  Start-Sleep 2
}
if ($healthOk) { Info "API ready at http://localhost:8000" } else { Warn "API may still be starting - check logs" }

# ---- Start Frontend (background job) ----
Info "Starting frontend (npm run dev)"
$frontendJob = Start-Job -ScriptBlock {
  param($repoRoot, $LogFile)
  Set-Location (Join-Path $repoRoot 'frontend')
  & npm run dev 2>&1 | ForEach-Object {
    $line = "Frontend: $_"
    Write-Output $line
    $line | Add-Content -Path $LogFile -Encoding utf8
  }
} -ArgumentList $repoRoot, $LogFile -Name 'fba-frontend'
if (-not $frontendJob) { Err "Failed to start frontend job" }
Info "Frontend job started (ID: $($frontendJob.Id))"

# ---- Jupyter (optional, start if requested) ----
# To start: .\scripts\start-dev.ps1 -Jupyter
# param([switch]$Jupyter)
# if ($Jupyter) {
#   Info "Starting Jupyter Lab"
#   Start-Process "poetry" "run jupyter lab --ip=0.0.0.0 --port=8888 --no-browser" -WorkingDirectory $repoRoot
# }

Info "Dev environment started!"
Info "API: http://localhost:8000 (docs: /docs)"
Info "GUI Dashboard: http://localhost:5173 (wait ~30s for Vite)"
Info "Logs: $LogFile"
Info "Stop: .\scripts\start-dev.ps1 -Stop"
Info "Monitor jobs: Get-Job | Receive-Job -Wait"
Info "Health: curl.exe -sS http://localhost:8000/api/v1/health or browser"

# Keep script running to monitor (optional; Ctrl+C to stop)
try {
  Wait-Job -Job $apiJob, $frontendJob -Any | Out-Null
} catch {
  Info "Jobs completed or interrupted"
} finally {
  Stop-Job -Name 'fba-api', 'fba-frontend' -ErrorAction SilentlyContinue
  Remove-Job -Name 'fba-api', 'fba-frontend' -ErrorAction SilentlyContinue
  if ($hasDocker) { docker stop fba-redis-dev -ErrorAction SilentlyContinue; docker rm fba-redis-dev -ErrorAction SilentlyContinue }
}
