@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo Blatero: Python Launcher not found. Install Python 3.12 first.
    pause
    exit /b 1
)

py -3.12 install_blatero.py --gui
if errorlevel 1 pause
