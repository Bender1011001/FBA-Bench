@echo off
echo [FBA] Starting Full Stack (Backend + GUI)...
set "VENV_PYTHON=E:\code.projects\fba\FBA-Bench-Enterprise\.venv\Scripts\python.exe"
set "GODOT_EXE=E:\code.projects\fba\FBA-Bench-Enterprise\Godot_v4.5.1-stable_win64.exe"

if exist "%VENV_PYTHON%" (
    echo [FBA] Using virtual environment: %VENV_PYTHON%
    "%VENV_PYTHON%" launch_godot_gui.py --godot "%GODOT_EXE%"
) else (
    echo [WARNING] Virtual environment not found. Trying global python...
    python launch_godot_gui.py --godot "%GODOT_EXE%"
)

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Launch failed.
    pause
)
