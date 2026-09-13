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
npx --yes cloudflared tunnel --url http://localhost:5173
pause
