@echo off
set PY=%~dp0.venv\Scripts\python.exe

:menu
cls
echo ============================
echo   STFU Manager
echo ============================
echo.
echo  1. Start (foreground, dev/manual use)
echo  2. Start MCP Server (stdio)
echo.
echo  -- Modules (Scheduled Tasks) --
echo  3. Register all 3 modules (web / overlay / night-light-helper)
echo  4. Start module task
echo  5. Stop module task
echo  6. Module task status
echo  7. Exit
echo.
set /p choice="Choose [1-7]: "

if "%choice%"=="1" goto start_fg
if "%choice%"=="2" goto start_mcp
if "%choice%"=="3" goto register_all
if "%choice%"=="4" goto start_task
if "%choice%"=="5" goto stop_task
if "%choice%"=="6" goto status_task
if "%choice%"=="7" goto end
echo Invalid choice.
timeout /t 1 /nobreak >nul
goto menu

:start_fg
echo Starting STFU (foreground + overlay)...
"%PY%" -m stfu
goto menu

:start_mcp
echo Starting MCP server (stdio)...
"%PY%" -m stfu --mcp
goto menu

:register_all
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Module web
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Module overlay
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Module night-light-helper
pause
goto menu

:start_task
set /p taskmod="Module [web/overlay/night-light-helper]: "
if /i "%taskmod%"=="web" schtasks /run /tn "STFU_Web"
if /i "%taskmod%"=="overlay" schtasks /run /tn "STFU_Overlay"
if /i "%taskmod%"=="night-light-helper" schtasks /run /tn "STFU_NightLightHelper"
timeout /t 1 /nobreak >nul
goto menu

:stop_task
set /p taskmod="Module [web/overlay/night-light-helper]: "
if /i "%taskmod%"=="web" schtasks /end /tn "STFU_Web"
if /i "%taskmod%"=="overlay" schtasks /end /tn "STFU_Overlay"
if /i "%taskmod%"=="night-light-helper" schtasks /end /tn "STFU_NightLightHelper"
timeout /t 1 /nobreak >nul
goto menu

:status_task
schtasks /query /tn "STFU_Web" /v /fo list
schtasks /query /tn "STFU_Overlay" /v /fo list
schtasks /query /tn "STFU_NightLightHelper" /v /fo list
pause
goto menu

:end
