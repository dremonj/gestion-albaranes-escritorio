@echo off
rem Genera dist\GestionAlbaranes.exe (un unico archivo que funciona sin instalar Python).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --quiet -r requirements-dev.txt
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed ^
    --name GestionAlbaranes ^
    --icon gestion_albaranes\recursos\icono.ico ^
    --add-data "gestion_albaranes\recursos;recursos" ^
    --collect-data customtkinter ^
    main.py
echo.
echo Listo: dist\GestionAlbaranes.exe
