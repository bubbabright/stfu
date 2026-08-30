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
echo Setup complete! No autostart is installed — start STFU manually each
echo session (machine runs for weeks at a time, so this is by design).
echo   Run manually: manage.bat
echo   Or directly:  .venv\Scripts\python.exe -m stfu
echo   MCP:          .venv\Scripts\python.exe -m stfu --mcp
echo.
pause
