@echo off
title MetrCheck AI — Full Setup (HACKATHON)
echo ============================================
echo   MetrCheck AI - Full Setup
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Creating Python 3.11 virtual environment (required for PaddlePaddle)...
if exist venv\Scripts\python.exe (
    echo   venv already exists - checking version...
    venv\Scripts\python.exe --version
) else (
    echo   NOTE: Need Python 3.11 for PaddlePaddle.
    echo   Using uv-managed Python 3.11.15...
    if exist "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe" (
        "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe" -m venv venv
    ) else (
        py -3.11 -m venv venv
    )
    if errorlevel 1 (
        echo   ERROR: Failed to create venv. Install Python 3.11 first.
        pause
        exit /b 1
    )
    echo   venv created
)
echo.

echo [2/3] Installing Python dependencies (PaddlePaddle is a large download ~700MB)...
venv\Scripts\python.exe -m pip install --upgrade pip -q
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo   ERROR: Failed to install requirements
    pause
    exit /b 1
)
echo   All Python packages installed
echo.

echo [3/3] Checking frontend (npm) dependencies...
cd frontend
if exist node_modules\.package-lock.json (
    echo   node_modules already exists - skipping npm install
) else (
    npm install
    if errorlevel 1 (
        echo   ERROR: Failed to install npm packages
        pause
        exit /b 1
    )
)
cd ..

echo.
echo ============================================
echo   Setup Complete!
echo   To RUN: double-click run.bat
echo ============================================
pause