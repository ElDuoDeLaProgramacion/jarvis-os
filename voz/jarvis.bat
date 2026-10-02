@echo off
REM Inicia JARVIS por voz y gestos. Di "Jarvis" y lo que necesitas.
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo La voz aun no esta instalada. Ejecuta primero instalar.bat en esta carpeta.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python jarvis_voz.py %*
