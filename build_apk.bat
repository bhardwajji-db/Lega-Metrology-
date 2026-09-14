@echo off
title MetrCheck AI - Android APK Builder
cd /d "%~dp0"

echo ============================================================
echo   MetrCheck AI - Android APK Builder
echo ============================================================
echo.

cd frontend
echo [1/3] Building Web Distribution...
call npm run build
if errorlevel 1 (
    echo [ERROR] Web build failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Syncing Capacitor Android Project...
call npx cap sync android
if errorlevel 1 (
    echo [ERROR] Capacitor sync failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Compiling Android APK with Gradle...
cd android
if exist gradlew.bat (
    call gradlew.bat assembleDebug
    if errorlevel 1 (
        echo.
        echo [NOTE] Local Java/Android SDK is required to compile locally.
        echo To build without installing Android SDK, simply push to GitHub
        echo and GitHub Actions will build MetrCheck-AI-Debug-APK automatically!
        pause
        exit /b 1
    )
    echo.
    echo ============================================================
    echo   [SUCCESS] APK Built Successfully!
    echo   File: frontend\android\app\build\outputs\apk\debug\app-debug.apk
    echo ============================================================
) else (
    echo Gradle wrapper not found.
)

pause
