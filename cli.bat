@echo off
:: AutoTrade CLI 快捷入口
:: 用法: cli.bat analyze --symbol 000001 --strategy ma_cross
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat >nul 2>&1
if exist "venv\Scripts\activate.bat"    call venv\Scripts\activate.bat >nul 2>&1

python -m autotrade.triggers.cli %*
