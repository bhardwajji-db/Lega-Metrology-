@echo off
title MetrCheck AI - Windows Firewall Port Configuration
echo ============================================================
echo   MetrCheck AI - Unblocking Ports 5173 and 8000 in Firewall
echo ============================================================
echo.

REM Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges to add firewall rule...
    powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c \"\"%~dpnx0\"\"' -Verb RunAs"
    exit /b
)

echo Adding inbound rule for TCP ports 5173 and 8000...
netsh advfirewall firewall delete rule name="MetrCheck AI (5173, 8000)" >nul 2>&1
netsh advfirewall firewall add rule name="MetrCheck AI (5173, 8000)" dir=in action=allow protocol=TCP localport=5173,8000 profile=any

echo.
echo ============================================================
echo   [SUCCESS] Ports 5173 and 8000 have been unblocked!
echo   Your phone can now connect seamlessly.
echo ============================================================
echo.
pause
