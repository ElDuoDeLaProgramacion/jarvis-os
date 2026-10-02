@echo off
REM Inicia JARVIS por voz. Mantén pulsada F9 para hablar.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python jarvis_voz.py %*
