@echo off
rem Arranca la aplicacion. La primera vez prepara el entorno (tarda un minuto).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Preparando la aplicacion por primera vez...
    python -m venv .venv || goto :sin_python
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :error
)
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:sin_python
echo.
echo No se ha encontrado Python. Instalalo desde https://www.python.org/downloads/
echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
pause
exit /b 1

:error
echo.
echo No se han podido instalar las librerias. Comprueba tu conexion a Internet.
pause
exit /b 1
