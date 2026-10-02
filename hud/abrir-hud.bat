@echo off
REM Abre el HUD de JARVIS: arranca el servidor en WSL y el navegador en Windows.
set DISTRO=Ubuntu
if not "%1"=="" set DISTRO=%1
start "JARVIS HUD" /min wsl.exe -d %DISTRO% --cd /mnt/p/jarvis-os --exec ./scripts/hud.sh
timeout /t 2 /nobreak >nul
start "" http://localhost:7777
