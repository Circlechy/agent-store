@echo off
REM Frontend Service Startup Script (Windows Batch)
REM Usage: start.bat

REM Set UTF-8 encoding
chcp 65001 >nul 2>&1

echo ========================================
echo    Vibe Agent Frontend Service
echo ========================================
echo.

REM Check if we're in the correct directory
if not exist "package.json" (
    echo Error: Please run this script from frontend/ directory
    echo Current directory: %CD%
    echo Please change to: vibeAgent/frontend/ directory
    pause
    exit /b 1
)

echo [OK] Directory check passed
echo.

REM Check Node.js
echo Checking Node.js...
where node >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js not found
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

node --version
echo.

REM Check npm
echo Checking npm...
where npm >nul 2>&1
if errorlevel 1 (
    echo Error: npm not found
    pause
    exit /b 1
)

echo [OK] npm is available
echo.

REM Check dependencies
if not exist "node_modules" (
    echo Dependencies not installed, installing...
    call npm install
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
    echo.
) else (
    echo [OK] Dependencies already installed
    echo.
)

echo Starting frontend service...
echo Frontend URL: http://localhost:3000
echo Make sure backend is running at: http://localhost:8000
echo Press Ctrl+C to stop the service
echo.

REM Start the service
call npm run dev

pause

