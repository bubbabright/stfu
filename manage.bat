@echo off
:menu
cls
echo ============================
echo   STFU Manager
echo ============================
echo.
echo  1. Start (foreground)
echo  2. Start (no overlay)
echo  3. Install as Service
echo  4. Start Service
echo  5. Stop Service
echo  6. Uninstall Service
echo  7. Start MCP Server
echo  8. Exit
echo.
set /p choice="Choose [1-8]: "

if "%choice%"=="1" goto start_fg
if "%choice%"=="2" goto start_nooverlay
if "%choice%"=="3" goto install_svc
if "%choice%"=="4" goto start_svc
if "%choice%"=="5" goto stop_svc
if "%choice%"=="6" goto uninstall_svc
if "%choice%"=="7" goto start_mcp
if "%choice%"=="8" goto end
echo Invalid choice.
timeout /t 1 /nobreak >nul
goto menu

:start_fg
echo Starting STFU (foreground + overlay)...
python -m stfu
goto menu

:start_nooverlay
echo Starting STFU (no overlay)...
python -m stfu --no-overlay
goto menu

:install_svc
echo Installing STFU service...
nssm install STFU python -m stfu --service
nssm set STFU AppDirectory "%~dp0"
nssm set STFU DisplayName "STFU Volume Control"
nssm set STFU Description "HTPC volume control with web UI, overlay, and MCP"
nssm set STFU Start SERVICE_AUTO_START
nssm set STFU AppStdout "%~dp0logs\service-stdout.log"
nssm set STFU AppStderr "%~dp0logs\service-stderr.log"
nssm set STFU AppRotateFiles 1
nssm set STFU AppRotateBytes 5242880
echo Service installed. Auto-starts on boot.
timeout /t 2 /nobreak >nul
goto menu

:start_svc
echo Starting STFU service...
nssm start STFU
echo Started.
timeout /t 1 /nobreak >nul
goto menu

:stop_svc
echo Stopping STFU service...
nssm stop STFU
echo Stopped.
timeout /t 1 /nobreak >nul
goto menu

:uninstall_svc
echo Uninstalling STFU service...
nssm stop STFU
nssm remove STFU confirm
echo Uninstalled.
timeout /t 1 /nobreak >nul
goto menu

:start_mcp
echo Starting MCP server (stdio)...
python -m stfu --mcp
goto menu

:end
