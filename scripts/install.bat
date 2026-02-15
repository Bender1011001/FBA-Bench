@echo off
REM FBA-Bench Installation Script for Windows
REM Installs dependencies for this repository using Poetry (backend only; legacy frontend removed).

setlocal enabledelayedexpansion

REM Python check
python --version >nul 2>&1
if %errorLevel% neq 0 (
  echo [ERROR] Python is not installed. Install Python 3.10+ from https://python.org
  exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [INFO] Python version: %PYTHON_VERSION%

REM Ensure Poetry (use python -m poetry to avoid PATH issues)
python -m poetry --version >nul 2>&1
if %errorLevel% neq 0 (
  echo [INFO] Installing Poetry...
  python -m pip install --user --upgrade pip
  python -m pip install --user poetry
)
python -m poetry --version >nul 2>&1
if %errorLevel% neq 0 (
  echo [ERROR] Poetry installation failed.
  exit /b 1
)

echo [INFO] Installing backend dependencies with Poetry...
python -m poetry install --with dev --no-interaction --no-ansi
if %errorLevel% neq 0 (
  echo [ERROR] Poetry install failed.
  exit /b 1
)

echo [SUCCESS] Installation completed.

echo.
echo [INFO] Next steps:
echo   - Run the API locally:
echo       python -m poetry run uvicorn fba_bench_api.main:get_app --factory --host 0.0.0.0 --port 8000 --reload
echo   - Optional: Start ClearML Server for experiment tracking:
echo       docker compose -f docker-compose.clearml.yml up -d
exit /b 0
