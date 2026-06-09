@echo off
REM ===========================================
REM Jasper Trades - Docker Deployment Script
REM ===========================================

echo.
echo ========================================
echo Jasper Trades - Docker Deployment
echo ========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Download from: https://www.docker.com/products/docker-desktop
    exit /b 1
)

echo [OK] Docker found
echo.

REM Check if .env file exists
if not exist .env (
    echo [INFO] .env file not found
    echo.
    echo Please create .env file with your API keys:
    echo   - NVIDIA_API_KEY
    echo   - ALPACA_API_KEY
    echo   - ALPACA_API_SECRET
    echo.
    echo Copy .env.example to .env and edit it.
    echo.
    set /p create="Create .env from .env.example? (y/n): "
    if /i "%create%"=="y" (
        copy .env.example .env
        echo Now edit .env and add your API keys
        pause
        exit /b
    )
)

echo [OK] .env file found
echo.

REM Pull latest images
echo Pulling latest Docker images...
docker-compose pull

echo.
echo ========================================
echo Starting Services
echo ========================================
echo.

REM Start all services
docker-compose up -d

echo.
echo Waiting for services to start...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo Service Status
echo ========================================
echo.

docker-compose ps

echo.
echo ========================================
echo Access URLs
echo ========================================
echo.
echo Frontend:    http://localhost:3000
echo Backend API: http://localhost:8000
echo API Docs:    http://localhost:8000/docs
echo WhatsApp:    http://localhost:2785
echo.
echo ========================================
echo Next Steps
echo ========================================
echo.
echo 1. Open http://localhost:2785 and scan QR code for WhatsApp
echo 2. Go to http://localhost:3000/settings
echo 3. Configure WhatsApp notifications
echo 4. Add your API keys in Settings page
echo.
echo To view logs: docker-compose logs -f
echo To stop:      docker-compose down
echo.