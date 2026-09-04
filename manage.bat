@echo off
set PY=%~dp0.venv\Scripts\python.exe

:menu
cls
echo ============================
echo   STFU Manager (manual — no scheduled tasks)
echo ============================
echo.
echo  1. Start ALL (web + overlay + night-light-helper + tint, one window each)
echo  2. Start Web only
echo  3. Start Overlay only
echo  4. Start Night-Light-Helper only
echo  5. Start Tint Overlay only
echo  6. Start (single foreground process, dev/manual use)
echo  7. Start MCP Server (stdio)
echo  8. Stop ALL stfu processes
echo  9. Status (list running stfu processes)
echo  10. Exit
echo  11. Start Caption Capture only
echo  12. Set MQTT Broker URL
echo  13. Show MQTT Config
echo  14. Exit (Alt)
echo.
set /p choice="Choose [1-14]: "

if "%choice%"=="1" goto start_all
if "%choice%"=="2" goto start_web
if "%choice%"=="3" goto start_overlay
if "%choice%"=="4" goto start_nlh
if "%choice%"=="5" goto start_tint
if "%choice%"=="6" goto start_fg
if "%choice%"=="7" goto start_mcp
if "%choice%"=="8" goto stop_all
if "%choice%"=="9" goto status
if "%choice%"=="10" goto end
if "%choice%"=="11" goto start_cc
if "%choice%"=="12" goto set_mqtt
if "%choice%"=="13" goto show_mqtt
if "%choice%"=="14" goto end
echo Invalid choice.
timeout /t 1 /nobreak >nul
goto menu

:start_all
start "STFU Web" cmd /k "%PY%" -m stfu --no-overlay
start "STFU Overlay" cmd /k "%PY%" -m stfu --overlay-only
start "STFU Night-Light-Helper" cmd /k "%PY%" -m stfu --night-light-helper
start "STFU Tint" cmd /k "%PY%" -m stfu --tint-only
start "STFU Caption Capture" cmd /k "%PY%" -m stfu --cc-only
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

:start_tint
start "STFU Tint" cmd /k "%PY%" -m stfu --tint-only
goto menu

:start_fg
echo Starting STFU (foreground + overlay)...
"%PY%" -m stfu
goto menu

:start_mcp
echo Starting MCP server (stdio)...
"%PY%" -m stfu --mcp
goto menu

:start_cc
start "STFU Caption Capture" cmd /k "%PY%" -m stfu --cc-only
goto menu

:set_mqtt
set /p MQTT_BROKER="Enter MQTT Broker URL (e.g. mqtt.hoboguppy.com): "
powershell -NoProfile -Command "(Get-Content stfu.toml) -replace '(?<=broker = \")[^\"]*', '%MQTT_BROKER%' | Set-Content stfu.toml"
echo MQTT broker updated to %MQTT_BROKER%
timeout /t 2 /nobreak >nul
goto menu

:show_mqtt
echo.
powershell -NoProfile -Command "Select-String -Path stfu.toml -Pattern 'broker|mqtt' | Select-Object -First 10"
echo.
pause
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
