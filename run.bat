@echo off
REM Hyperliquid Tracker - Quick Start Script for Windows

echo ======================================
echo Hyperliquid Trader Address Tracker
echo ======================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

REM Check if .env exists
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit .env to configure your settings.
    exit /b 1
)

REM Create necessary directories
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Run the tracker
echo.
echo Starting tracker...
echo Dashboard will be available at: http://localhost:5000
echo Press Ctrl+C to stop
echo.

cd src
python main.py
