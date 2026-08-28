@echo off
echo Setting up STFU...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ and add to PATH.
    pause
    exit /b 1
)

REM Create venv
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate and install
call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt

REM Create logs dir
if not exist "logs" mkdir logs

REM Install as service
echo.
echo Install as Windows service? (requires NSSM)
set /p install_svc="Type 'yes' to install: "
if /i "%install_svc%"=="yes" (
    where nssm >nul 2>&1
    if errorlevel 1 (
        echo NSSM not found. Download from https://nssm.cc/download
        echo Then run: nssm install STFU python -m stfu --service
    ) else (
        nssm install STFU python -m stfu --service
        nssm set STFU AppDirectory "%~dp0"
        nssm set STFU DisplayName "STFU Volume Control"
        nssm set STFU Start SERVICE_AUTO_START
        nssm set STFU AppStdout "%~dp0logs\service-stdout.log"
        nssm set STFU AppStderr "%~dp0logs\service-stderr.log"
        nssm set STFU AppRotateFiles 1
        nssm set STFU AppRotateBytes 5242880
        echo Service installed and set to auto-start.
    )
)

echo.
echo Setup complete!
echo   Run: python -m stfu
echo   Or:  manage.bat
echo   MCP: python -m stfu --mcp
echo.
pause
