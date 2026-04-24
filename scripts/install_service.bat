@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python caine\windows_service.py --startup auto install
sc description CAINE "Servicio persistente de CAINE para supervision y reinicio automatico."
sc failure CAINE reset= 86400 actions= restart/5000/restart/5000/restart/5000
python caine\windows_service.py start
