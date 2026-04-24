@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro .venv\Scripts\python.exe
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python web_chat.py
