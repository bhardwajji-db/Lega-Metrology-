@echo off
setlocal
title MetrCheck AI - Server Controller
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ============================================================
    echo   ERROR: Python virtual environment not found.
    echo   Please run setup.bat first to initialize dependencies.
    echo ============================================================
    pause
    exit /b 1
)

"venv\Scripts\python.exe" "runner.py"

pause
