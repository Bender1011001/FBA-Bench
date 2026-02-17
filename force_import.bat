@echo off
echo [FBA] Forcing asset import by running Godot Editor...
set "GODOT_EXE=E:\code.projects\fba\FBA-Bench-Enterprise\Godot_v4.5.1-stable_win64_console.exe"
set "PROJECT_PATH=E:\code.projects\fba\FBA-Bench-Enterprise\godot_gui"

"%GODOT_EXE%" --path "%PROJECT_PATH%" --editor --quit
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Headless import might have failed. Trying with visible editor...
    "%GODOT_EXE%" --path "%PROJECT_PATH%" --editor --quit
)
echo [FBA] Import cycle complete.
