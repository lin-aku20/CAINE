@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python caine\windows_service.py stop
python caine\windows_service.py remove
