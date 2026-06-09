@echo off
REM ===========================================
REM Jasper Trades - Installation Script
REM Installs: Backend + Frontend + OpenWA (WhatsApp)
REM ===========================================

echo.
echo ========================================
echo Jasper Trades Installation
echo ========================================
echo.

REM Check Python
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11+ not found
    echo Install from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found
python --version
echo.

REM Check Node.js
echo [2/6] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js 18+ not found
    echo Install from https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js found
node --version
echo.

REM Install backend dependencies
echo [3/6] Installing backend dependencies...
cd backend
call npm install @open-wa/wa-automate
pip install -r requirements.txt
cd ..
echo.

REM Setup backend environment
echo [4/6] Setting up backend environment...
if not exist "backend\.env" (
    copy "backend\.env.example" "backend\.env"
    echo [OK] Created backend\.env
    echo.
    echo IMPORTANT: Edit backend\.env and add:
    echo   - NVIDIA_API_KEY (get from build.nvidia.com)
) else (
    echo [OK] backend\.env already exists
)
echo.

REM Install frontend dependencies
echo [5/6] Installing frontend dependencies...
cd frontend
call npm install
cd ..
echo.

REM Setup frontend environment
echo [6/6] Setting up frontend environment...
if not exist "frontend\.env.local" (
    copy "frontend\.env.example" "frontend\.env.local"
    echo [OK] Created frontend\.env.local
) else (
    echo [OK] frontend\.env.local already exists
)
echo.

echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Edit backend\.env and add NVIDIA API key
echo 2. Run: start.bat
echo.
echo That's it! The app will open at:
echo   http://localhost:3000
echo.
echo Configure API keys at:
echo   http://localhost:3000/settings
echo.
echo ========================================
pause