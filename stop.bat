@echo off
title MetrCheck AI - Stop Servers
echo ============================================
echo   MetrCheck AI - Stopping Servers...
echo ============================================
powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 5173,5174,8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" 2>nul
ping 127.0.0.1 -n 2 >nul
