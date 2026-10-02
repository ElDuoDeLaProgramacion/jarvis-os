@echo off
REM Abre el HUD de JARVIS en su propia ventana (sin navegador).
REM Opciones: --distro NombreExacto   --pantalla-completa
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo El HUD aun no esta instalado. Ejecuta primero instalar.bat en esta carpeta.
  pause
  exit /b 1
)
start "" .venv\Scripts\pythonw.exe jarvis_hud.py %*
