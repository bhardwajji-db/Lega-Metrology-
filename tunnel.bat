@echo off
title MetrCheck AI - Mobile Cloud Tunnel (Zero-Prompt)
cd /d "%~dp0"
echo ============================================================
echo   MetrCheck AI - Instant Secure Cloud Tunnel for Phone
echo ============================================================
echo.
echo Starting Cloudflare HTTPS Tunnel on port 5173...
echo Open the generated URL on your phone to use the app anywhere!
echo (No IP address or password verification required)
echo.
where cloudflared >nul 2>nul
if errorlevel 1 (
    npx --yes cloudflared tunnel --url https://localhost:5173 --no-tls-verify
) else (
    cloudflared tunnel --url https://localhost:5173 --no-tls-verify
)
pause
