@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual en .venv
    echo Crea uno con: python -m venv .venv
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python verify_ollama.py
python main.py
