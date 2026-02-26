@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Ensure we are in repo root (this script’s directory)
cd /d "%~dp0" || (
  echo [FBA] Failed to change directory to repo root.
  exit /b 1
)

if "%~1"=="" goto :usage
set "cmd=%~1"

if /I "%cmd%"=="start" goto :start
if /I "%cmd%"=="stop" goto :stop
if /I "%cmd%"=="status" goto :status

:usage
echo FBA command usage:
echo   FBA start   - Start backend (Docker: Postgres, Redis, API), start frontend, and open browser
echo   FBA stop    - Stop Docker services (docker-compose down)
echo   FBA status  - Show Docker service status (docker-compose ps)
exit /b 1

:start
echo [FBA] Starting stack...
call "scripts\fba-start.bat"
exit /b %ERRORLEVEL%

:stop
echo [FBA] Stopping stack...
docker-compose down
exit /b %ERRORLEVEL%

:status
echo [FBA] Stack status:
docker-compose ps
exit /b %ERRORLEVEL%