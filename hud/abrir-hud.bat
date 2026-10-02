@echo off
REM Abre el HUD de JARVIS: arranca el servidor en WSL y abre el navegador cuando responde.
set DISTRO=Ubuntu
if not "%1"=="" set DISTRO=%1
start "JARVIS HUD" /min wsl.exe -d %DISTRO% --cd /mnt/p/jarvis-os --exec ./scripts/hud.sh

REM Al encender el PC, WSL puede tardar en arrancar: espera hasta 60 s a que el HUD responda.
set intentos=0
:esperar
set /a intentos+=1
curl.exe -s -o nul http://localhost:7777/api/estado && goto abrir
if %intentos% geq 60 goto abrir
timeout /t 1 /nobreak >nul
goto esperar

:abrir
start "" http://localhost:7777
