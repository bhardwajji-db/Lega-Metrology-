@echo off
title MetrCheck AI - Backend Tunnel for Mobile Demo
cd /d "%~dp0"
echo ============================================================
echo   MetrCheck AI - Cloudflare HTTPS Tunnel (Backend API)
echo ============================================================
echo.
echo This script creates a secure HTTPS tunnel to your local
echo FastAPI backend on port 8000 for mobile APK testing.
echo.

REM Check if cloudflared is available
where cloudflared >nul 2>nul
if errorlevel 1 (
    echo [INFO] cloudflared not found in PATH.
    echo        Attempting to use npx cloudflared...
    echo.
    echo ============================================================
    echo   IMPORTANT: Copy the generated HTTPS URL and enter it
    echo   in MetrCheck app ^> Server Settings on your phone.
    echo ============================================================
    echo.
    echo   Make sure the FastAPI backend is running first!
    echo   Start it with:  cd backend ^&^& python -m uvicorn main:app --host 0.0.0.0 --port 8000
    echo.
    npx --yes cloudflared tunnel --url http://localhost:8000
) else (
    echo [OK] cloudflared found.
    echo.
    echo ============================================================
    echo   IMPORTANT: Copy the generated HTTPS URL and enter it
    echo   in MetrCheck app ^> Server Settings on your phone.
    echo ============================================================
    echo.
    echo   Make sure the FastAPI backend is running first!
    echo   Start it with:  cd backend ^&^& python -m uvicorn main:app --host 0.0.0.0 --port 8000
    echo.
    cloudflared tunnel --url http://localhost:8000
)

pause
