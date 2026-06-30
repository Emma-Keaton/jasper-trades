@echo off
REM Configure Agent Reach after logging into Twitter/X and Reddit in Chrome
REM Run this AFTER you've logged in to chrome

echo ===========================================
echo Agent Reach Configuration
echo ===========================================
echo.
echo This will extract cookies from Chrome for:
echo   - Twitter/X
echo   - Reddit
echo   - AND all other supported platforms
echo.
echo IMPORTANT: Make sure you're logged into:
echo   - https://twitter.com or https://x.com
echo   - https://reddit.com
echo.
echo in your Chrome browser, then CLOSE Chrome completely.
echo.
pause

echo.
echo Closing Chrome if running...
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Extracting ALL cookies from Chrome...
agent-reach configure --from-browser chrome

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Cookie extraction failed!
    echo Please make sure:
    echo   1. You are logged into Twitter and Reddit in Chrome
    echo   2. Chrome is completely closed (check Task Manager)
    echo   3. You run this as Administrator
    echo.
    pause
    exit /b 1
)

echo.
echo Copying config to backend-accessible location...
set CONFIG_SOURCE=%USERPROFILE%\.agent-reach\config.yaml
set CONFIG_TARGET=%~dp0agent_reach_config.yaml
if exist "%CONFIG_SOURCE%" (
    copy "%CONFIG_SOURCE%" "%CONFIG_TARGET%"
    echo Config copied to: %CONFIG_TARGET%
) else (
    echo WARNING: Config file not found at %CONFIG_SOURCE%
    echo You may need to run agent-reach doctor first
)

echo.
echo ===========================================
echo Configuration Complete!
echo ===========================================
echo.
echo To verify everything is working, run:
echo   agent-reach doctor
echo.
echo You should see Twitter and Reddit show as available.
echo.
echo NEXT STEPS:
echo 1. Set AGENT_REACH_ENABLED=true in .env
echo 2. Set AGENT_REACH_CHANNELS=twitter,reddit,v2ex
echo 3. Set AGENT_REACH_CONFIG_PATH=%CONFIG_TARGET% (if different from default)
echo 4. Restart the backend server
echo.
pause