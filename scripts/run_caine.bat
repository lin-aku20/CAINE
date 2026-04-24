@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo No se encontro el entorno virtual en .venv
    echo Crea uno con: python -m venv .venv
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "main.py"
