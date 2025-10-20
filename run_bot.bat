@echo off
setlocal enabledelayedexpansion

REM Change to the script directory
pushd "%~dp0"

REM Create virtual environment if it does not exist
if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating virtual environment in .venv ...
  py -3 -m venv .venv 2>nul
  if errorlevel 1 (
    echo [setup] Python launcher not available, trying "python"...
    python -m venv .venv
  )
)

REM Activate the virtual environment
call ".venv\Scripts\activate.bat"

REM Upgrade pip and install dependencies
python -m pip install --upgrade pip
if exist "requirements.txt" (
  pip install -r requirements.txt
)

REM Create runtime directories
if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"
if not exist "reports" mkdir "reports"

set PYTHONUNBUFFERED=1

echo [run] Starting bot...
python "bot.py"
set EXIT_CODE=%ERRORLEVEL%

popd
endlocal & exit /b %EXIT_CODE%