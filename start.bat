@echo off
cd /d "%~dp0"

echo.
echo ================================================
echo   AutoTrade - A-Share Quant Backtest System
echo   http://localhost:8080
echo ================================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

REM --- Activate venv if exists ---
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if exist venv\Scripts\activate.bat    call venv\Scripts\activate.bat

REM --- Check deps ---
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Installing dependencies...
    python -m pip install "fastapi[standard]" -q
    if errorlevel 1 (
        echo [ERROR] Failed to install. Run manually:
        echo   python -m pip install "fastapi[standard]"
        pause
        exit /b 1
    )
)

REM --- Ensure data dirs ---
if not exist data\cache  mkdir data\cache
if not exist data\results mkdir data\results
if not exist data\logs   mkdir data\logs

REM --- Start ---
echo Starting server at http://localhost:8080
echo Press Ctrl+C to stop
echo.

python -m autotrade.api

pause
