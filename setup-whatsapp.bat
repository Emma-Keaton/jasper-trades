@echo off
REM WhatsApp Setup Script for Jasper Trades
REM This script installs and configures OpenWA for WhatsApp notifications

echo ========================================
echo   WhatsApp Setup for Jasper Trades
echo ========================================
echo.

cd /d %~dp0backend

echo [1/3] Checking Node.js installation...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed!
    echo Please install Node.js from https://nodejs.org/
    exit /b 1
)
echo OK: Node.js is installed

echo.
echo [2/3] Installing OpenWA (WhatsApp API)...
echo This may take 2-5 minutes...
call npm install @open-wa/wa-automate --legacy-peer-deps

if %errorlevel% neq 0 (
    echo ERROR: Failed to install OpenWA
    echo Try running: npm install @open-wa/wa-automate --legacy-peer-deps
    exit /b 1
)
echo OK: OpenWA installed successfully

echo.
echo [3/3] Creating data directories...
mkdir data\openwa-session 2>nul
mkdir data\logs 2>nul
echo OK: Directories created

echo.
echo ========================================
echo   WhatsApp Setup Complete!
echo ========================================
echo.
echo Next Steps:
echo 1. Start the backend: python -m uvicorn app.main:app --reload
echo 2. Open browser: http://localhost:8000
echo 3. Go to Settings - Notifications - WhatsApp
echo 4. Enter your phone number and click "Send Code"
echo 5. Check backend console for QR code or verification code
echo.
echo For production (Render):
echo - The Dockerfile already includes OpenWA installation
echo - WhatsApp will work automatically after deployment
echo.
pause