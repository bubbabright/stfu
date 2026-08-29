@echo off
echo Setting up STFU...
echo.

REM Check uv
where uv >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv not found. Install from https://astral.sh/uv and add to PATH.
    pause
    exit /b 1
)

REM Create canonical venv
if not exist ".venv" (
    echo Creating virtual environment with uv...
    uv venv .venv
)

echo Installing dependencies...
uv pip install -r requirements.txt --python .venv\Scripts\python.exe

REM Create logs dir
if not exist "logs" mkdir logs

echo.
echo Register STFU's autostart tasks? (web module: at boot, no login required;
echo overlay + Dark Mode/Night Light helper: at logon, interactive session)
set /p install_tasks="Type 'yes' to install: "
if /i "%install_tasks%"=="yes" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Module web
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Module overlay
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Module night-light-helper
    echo All 3 tasks registered.
)

echo.
echo Setup complete!
echo   Run manually: .venv\Scripts\python.exe -m stfu
echo   Or:           manage.bat
echo   MCP:          .venv\Scripts\python.exe -m stfu --mcp
echo.
pause
