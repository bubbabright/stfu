@echo off
set PY=%~dp0.venv\Scripts\python.exe

:menu
cls
echo ============================
echo   STFU Manager (manual — no scheduled tasks)
echo ============================
echo.
echo  1. Start ALL (web + overlay + night-light-helper, one window each)
echo  2. Start Web only
echo  3. Start Overlay only
echo  4. Start Night-Light-Helper only
echo  5. Start (single foreground process, dev/manual use)
echo  6. Start MCP Server (stdio)
echo  7. Stop ALL stfu processes
echo  8. Status (list running stfu processes)
echo  9. Exit
echo.
set /p choice="Choose [1-9]: "

if "%choice%"=="1" goto start_all
if "%choice%"=="2" goto start_web
if "%choice%"=="3" goto start_overlay
if "%choice%"=="4" goto start_nlh
if "%choice%"=="5" goto start_fg
if "%choice%"=="6" goto start_mcp
if "%choice%"=="7" goto stop_all
if "%choice%"=="8" goto status
if "%choice%"=="9" goto end
echo Invalid choice.
timeout /t 1 /nobreak >nul
goto menu

:start_all
start "STFU Web" cmd /k "%PY%" -m stfu --no-overlay
start "STFU Overlay" cmd /k "%PY%" -m stfu --overlay-only
start "STFU Night-Light-Helper" cmd /k "%PY%" -m stfu --night-light-helper
goto menu

:start_web
start "STFU Web" cmd /k "%PY%" -m stfu --no-overlay
goto menu

:start_overlay
start "STFU Overlay" cmd /k "%PY%" -m stfu --overlay-only
goto menu

:start_nlh
start "STFU Night-Light-Helper" cmd /k "%PY%" -m stfu --night-light-helper
goto menu

:start_fg
echo Starting STFU (foreground + overlay)...
"%PY%" -m stfu
goto menu

:start_mcp
echo Starting MCP server (stdio)...
"%PY%" -m stfu --mcp
goto menu

:stop_all
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*-m stfu*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Stopped.
timeout /t 1 /nobreak >nul
goto menu

:status
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*-m stfu*' } | Select ProcessId,CommandLine | Format-Table -AutoSize"
pause
goto menu

:end
