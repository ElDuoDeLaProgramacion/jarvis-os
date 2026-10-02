@echo off
REM Crea un entorno de Python e instala lo necesario para la voz y los gestos de JARVIS.
cd /d "%~dp0"
REM Si ya existe (por ejemplo, con JARVIS abierto) no se recrea: solo se actualizan los paquetes.
REM Los gestos (MediaPipe) necesitan Python 3.9 a 3.12: si esta el lanzador "py", se prefiere 3.12 o 3.11.
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :error
pip install -r requirements-gestos.txt || (
  echo.
  echo Aviso: los gestos no se instalaron. MediaPipe necesita Python 3.9 a 3.12.
  echo La voz funciona igual. Para tener gestos: instala Python 3.11, borra la carpeta .venv y vuelve a ejecutar instalar.bat.
)
echo.
echo Listo. Ejecuta jarvis.bat y di "Jarvis" seguido de lo que necesitas.
pause
exit /b 0
:error
echo Algo fallo. Revisa que Python 3.10+ este instalado y en el PATH.
pause
exit /b 1
