@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"
set "BLATERO_ROOT=%~dp0"
set "BLATERO_APP=%BLATERO_ROOT%"
if exist "%BLATERO_ROOT%app\panel.py" set "BLATERO_APP=%BLATERO_ROOT%app\"

cd /d "%BLATERO_APP%"
set "BLATERO_PY=%BLATERO_APP%.venv\Scripts\python.exe"
set "BLATERO_TOKEN_FILE=%LOCALAPPDATA%\blatero\access-token"
set "BLATERO_PORTABLE=0"
set "BLATERO_START_LOG=%TEMP%\blatero-last-startup-error.log"

if not exist "%BLATERO_PY%" if exist "%BLATERO_APP%runtime\python.exe" (
    set "BLATERO_PY=%BLATERO_APP%runtime\python.exe"
    set "BLATERO_PORTABLE=1"
)

if not exist "%BLATERO_PY%" if exist "%BLATERO_ROOT%runtime\python.exe" (
    set "BLATERO_PY=%BLATERO_ROOT%runtime\python.exe"
    set "BLATERO_PORTABLE=1"
)

if not exist "%BLATERO_PY%" if exist "%BLATERO_ROOT%..\runtime\python.exe" (
    set "BLATERO_PY=%BLATERO_ROOT%..\runtime\python.exe"
    set "BLATERO_PORTABLE=1"
)

if not exist "%BLATERO_PY%" (
    echo Blatero: Python runtime not found.
    echo Expected .venv\Scripts\python.exe, runtime\python.exe or ..\runtime\python.exe
    pause
    exit /b 1
)

if not "%BLATERO_PORTABLE%"=="1" goto data_ready
if defined BLATERO_DATA_DIR goto data_ready
for /f "usebackq delims=" %%D in (`powershell.exe -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"`) do set "BLATERO_DATA_DIR=%%D\Blatero"
if not defined BLATERO_DATA_DIR (
    echo Blatero: Windows Documents folder could not be resolved.
    pause
    exit /b 1
)
:data_ready

"%BLATERO_PY%" startup.py prepare-token "%BLATERO_TOKEN_FILE%" ^
    >nul 2>"%BLATERO_START_LOG%"

if errorlevel 1 (
    echo Blatero: access token could not be prepared.
    if exist "%BLATERO_START_LOG%" type "%BLATERO_START_LOG%"
    pause
    exit /b 1
)

"%BLATERO_PY%" startup.py open-when-ready "%BLATERO_TOKEN_FILE%" --seconds 2 ^
    >nul 2>&1

if not errorlevel 1 (
    exit /b 0
)

netstat -ano | findstr /r /c:":8777 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo Blatero: server is already running, but this launcher cannot open it with the current token.
    echo Close the existing "Blatero server" window and run the shortcut again.
    pause
    exit /b 1
)

"%BLATERO_PY%" release_manager.py apply-pending ^
    >"%LOCALAPPDATA%\blatero\last-update.log" 2>&1
if errorlevel 1 (
    echo Blatero: prepared update could not be applied.
    echo See %LOCALAPPDATA%\blatero\last-update.log
    pause
    exit /b 1
)

set "BLATERO_UPDATE_ACTION_NONE=0"
findstr /c:"action" "%LOCALAPPDATA%\blatero\last-update.log" | findstr /c:"none" >nul 2>&1
if not errorlevel 1 set "BLATERO_UPDATE_ACTION_NONE=1"
findstr /c:"action" "%LOCALAPPDATA%\blatero\last-update.log" | findstr /c:"update_rejected" >nul 2>&1
if not errorlevel 1 set "BLATERO_UPDATE_ACTION_NONE=1"

if "%BLATERO_UPDATE_ACTION_NONE%"=="0" (
    "%BLATERO_PY%" release_manager.py sync-dependencies ^
        >>"%LOCALAPPDATA%\blatero\last-update.log" 2>&1
    if errorlevel 1 (
        "%BLATERO_PY%" release_manager.py schedule-rollback ^
            >>"%LOCALAPPDATA%\blatero\last-update.log" 2>&1
        "%BLATERO_PY%" release_manager.py apply-pending ^
            >>"%LOCALAPPDATA%\blatero\last-update.log" 2>&1
        echo Blatero: update dependencies failed; program files were rolled back.
        echo See %LOCALAPPDATA%\blatero\last-update.log
        pause
        exit /b 1
    )
)

start "" /min "%BLATERO_PY%" startup.py open-when-ready "%BLATERO_TOKEN_FILE%" --seconds 30

title Blatero server
"%BLATERO_PY%" panel.py --token-file "%BLATERO_TOKEN_FILE%"

echo.
echo Blatero server stopped.
pause
