@echo off
REM ===========================================
REM Jasper Trades - Complete Start Script
REM Starts: Backend (with embedded WhatsApp) + Frontend
REM All API keys configured via Settings page
REM ===========================================

echo.
echo ========================================
echo Jasper Trades - Starting...
echo ========================================
echo.
echo Starting 2 services:
echo   1. Backend  (Port 8000) - includes embedded WhatsApp
echo   2. Frontend (Port 3000)
echo.
echo First-time setup will install dependencies automatically.
echo API Keys: Configure via Settings page after starting
echo   - http://localhost:3000/settings
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ not found. Install from python.org
    pause
    exit /b 1
)
echo [OK] Python found

REM Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js 18+ not found. Install from nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

echo.
echo ========================================
echo Checking Installation
echo ========================================

REM Check/install backend dependencies
cd backend
if not exist "node_modules\@open-wa\wa-automate" (
    echo.
    echo [INFO] Installing OpenWA for WhatsApp (first-time only)...
    echo This may take 5-10 minutes...
    echo.
    call npm install @open-wa/wa-automate
    echo [OK] OpenWA installed
) else (
    echo [OK] OpenWA already installed
)

if not exist "%LOCALAPPDATA%\Programs\Python\Python314\Lib\site-packages\fastapi" (
    echo.
    echo [INFO] Installing backend Python packages...
    pip install -r requirements.txt
    echo [OK] Backend dependencies installed
) else (
    echo [OK] Backend dependencies already installed
)
cd ..

REM Check/install frontend dependencies
cd frontend
if not exist "node_modules" (
    echo.
    echo [INFO] Installing frontend npm packages...
    call npm install
    echo [OK] Frontend dependencies installed
) else (
    echo [OK] Frontend dependencies already installed
)
cd ..

REM Check/create environment files
if not exist "backend\.env" (
    copy "backend\.env.example" "backend\.env" >nul
    echo [OK] Created backend\.env (add your API keys)
) else (
    echo [OK] backend\.env exists
)

if not exist "frontend\.env.local" (
    copy "frontend\.env.example" "frontend\.env.local" >nul
    echo [OK] Created frontend\.env.local
) else (
    echo [OK] frontend\.env.local exists
)

echo.
echo ========================================
echo Starting Services
echo ========================================
echo.

REM Start Backend in new window
echo Starting Backend (includes embedded WhatsApp on port 3001)...
start "Jasper - Backend" cmd /k "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait for backend to start
timeout /t 5 /nobreak >nul

REM Start Frontend in new window
echo Starting Frontend...
start "Jasper - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo Jasper Trades is starting!
echo ========================================
echo.
echo Service URLs:
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo   Settings:  http://localhost:3000/settings
echo.
echo 2 new windows should have opened.
echo Close those windows to stop all services.
echo.
echo ========================================
echo Next Steps:
echo ========================================
echo.
echo 1. Wait for services to finish starting (~10 seconds)
echo 2. Open http://localhost:3000/settings
echo 3. Configure API keys:
echo    - NVIDIA NIM API (required for AI)
echo    - Alpaca API Keys (for trading)
echo    - WhatsApp phone number (optional)
echo 4. Start trading!
echo.
echo See DEPLOYMENT.md for cloud deployment.
echo ========================================
echo.
pause