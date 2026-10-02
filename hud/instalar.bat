@echo off
REM Instala el programa del HUD de JARVIS (ventana propia, sin navegador).
cd /d "%~dp0"
REM Si ya existe (por ejemplo, con JARVIS abierto) no se recrea: solo se actualizan los paquetes.
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :error
echo.
echo Listo. Ejecuta abrir-hud.bat para abrir el HUD.
pause
exit /b 0
:error
echo Algo fallo. Revisa que Python 3.10+ este instalado y en el PATH.
pause
exit /b 1
