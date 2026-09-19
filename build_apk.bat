@echo off
title MetrCheck AI - Android APK Builder
cd /d "%~dp0"

echo ============================================================
echo   MetrCheck AI - Android APK Builder
echo ============================================================
echo.

set BUILD_TYPE=debug
if /i "%1"=="release" set BUILD_TYPE=release

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
if "%BUILD_TYPE%"=="release" (
    echo [3/3] Building RELEASE APK...
) else (
    echo [3/3] Building DEBUG APK...
)
cd android
if exist gradlew.bat (
    if "%BUILD_TYPE%"=="release" (
        call gradlew.bat assembleRelease
    ) else (
        call gradlew.bat assembleDebug
    )
    if errorlevel 1 (
        echo.
        echo [NOTE] Build failed. Ensure Java/Android SDK is installed.
        echo To build without local SDK, push to GitHub for CI/CD build.
        pause
        exit /b 1
    )
    echo.
    echo ============================================================
    if "%BUILD_TYPE%"=="release" (
        echo   [SUCCESS] Release APK Built!
        echo   File: frontend\android\app\build\outputs\apk\release\app-release.apk
    ) else (
        echo   [SUCCESS] Debug APK Built!
        echo   File: frontend\android\app\build\outputs\apk\debug\app-debug.apk
    )
    echo ============================================================
) else (
    echo Gradle wrapper not found.
)

pause
