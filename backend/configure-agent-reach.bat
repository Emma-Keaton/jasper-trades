@echo off
REM Configure Agent Reach after logging into Twitter/X and Reddit in Chrome
REM Run this AFTER you've logged in to chrome

echo ===========================================
echo Agent Reach Configuration
echo ===========================================
echo.
echo This will extract cookies from Chrome for:
echo   - Twitter/X (twitter-cli)
echo   - Reddit (OpenCLI)
echo.
echo Make sure you're logged into:
echo   - https://twitter.com or https://x.com
echo   - https://reddit.com
echo.
echo in your Chrome browser.
echo.
pause

echo.
echo Extracting Twitter cookies...
agent-reach configure --from-browser chrome twitter-cookies

echo.
echo Extracting Reddit cookies...
agent-reach configure --from-browser chrome reddit-cookies

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
pause