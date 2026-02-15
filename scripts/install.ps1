# FBA-Bench Installation Script for Windows PowerShell
# Installs backend dependencies using Poetry. Frontend build is handled in deployment recipes.
# Usage: Right-click > Run with PowerShell (or) `powershell -ExecutionPolicy Bypass -File scripts\install.ps1`

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Console UTF-8 for clean output
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$PSDefaultParameterValues['Out-File:Encoding']    = 'utf8'
$PSDefaultParameterValues['Add-Content:Encoding'] = 'utf8'
$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'

function Write-Info    ($m) { Write-Host "[INFO]    $m" -ForegroundColor Cyan }
function Write-Success ($m) { Write-Host "[SUCCESS] $m" -ForegroundColor Green }
function Write-Warn    ($m) { Write-Host "[WARN]    $m" -ForegroundColor Yellow }
function Write-ErrorLn ($m) { Write-Host "[ERROR]   $m" -ForegroundColor Red }

function Invoke-Checked {
  param(
    [Parameter(Mandatory=$true)][string]$CommandLine,
    [string]$Hidden = $false
  )
  if ($Hidden) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & cmd /c $CommandLine 2>&1 | Out-Null
    } finally {
      $ErrorActionPreference = $prev
    }
    if ($LASTEXITCODE) {
      throw "Command failed ($LASTEXITCODE): $CommandLine"
    }
    return
  }
  & cmd /c $CommandLine
  if ($LASTEXITCODE) {
    throw "Command failed ($LASTEXITCODE): $CommandLine"
  }
}

# Detect repository root (git preferred; fallback to script directory parent)
$__scriptFile = if ($PSCommandPath) { $PSCommandPath } elseif ($MyInvocation.MyCommand.Path) { $MyInvocation.MyCommand.Path } else { $null }
$__scriptDir  = if ($PSScriptRoot)  { $PSScriptRoot }  elseif ($__scriptFile)              { [IO.Path]::GetDirectoryName($__scriptFile) } else { (Get-Location).Path }
$repoRoot = (& git -C $__scriptDir rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) { $repoRoot = $__scriptDir | Split-Path -Parent }
$repoRoot = [IO.Path]::GetFullPath($repoRoot)
Write-Info "Repository root: $repoRoot"

Push-Location $repoRoot
try {
  # Python detection
  $pythonCmd = $null
  if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
  }

  if (-not $pythonCmd) {
    Write-ErrorLn "Python 3.10+ is not installed. Install from https://www.python.org/downloads/windows/"
    exit 1
  }

  $ver = & cmd /c "$pythonCmd --version 2>&1"
  Write-Info "Detected $ver"
  # Basic version check (major.minor)
  $verParts = ($ver -replace '[^\d\.]', '').Split('.')
  if ($verParts.Count -lt 2) {
    Write-Warn "Unable to parse Python version; continuing."
  } else {
    $major = [int]$verParts[0]
    $minor = [int]$verParts[1]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
      Write-ErrorLn "Python 3.10+ required. Found: $ver"
      exit 1
    }
  }

  # Ensure pip is present and updated
  Write-Info "Upgrading pip..."
  Invoke-Checked "$pythonCmd -m pip install --user --upgrade pip" -Hidden:$true

  # Ensure Poetry installed (prefer python -m poetry)
  $poetryOk = $false
  & cmd /c "$pythonCmd -m poetry --version" 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { $poetryOk = $true }

  if (-not $poetryOk) {
    Write-Info "Installing Poetry..."
    Invoke-Checked "$pythonCmd -m pip install --user poetry" -Hidden:$true
    & cmd /c "$pythonCmd -m poetry --version" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      Write-ErrorLn "Poetry installation failed. Ensure Python is added to PATH and retry."
      exit 1
    }
  }

  # Install dependencies with dev extras (matches scripts/install.sh)
  Write-Info "Installing backend dependencies with Poetry..."
  Invoke-Checked "$pythonCmd -m poetry install --with dev --no-interaction --no-ansi"

  Write-Success "Installation completed."
  ""
  Write-Info "Next steps:"
  Write-Host " - Run the API locally:" -ForegroundColor Gray
  Write-Host "     $pythonCmd -m poetry run uvicorn fba_bench_api.main:get_app --factory --host 0.0.0.0 --port 8000 --reload"
  Write-Host " - Optional: Start ClearML Server for experiment tracking (if Compose file present):" -ForegroundColor Gray
  Write-Host "     docker compose -f docker-compose.clearml.yml up -d"
}
finally {
  Pop-Location
}
