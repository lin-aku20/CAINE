@echo off
title CAINE Launcher
cd /d "%~dp0"

echo ==========================================
echo  Iniciando CAINE...
echo ==========================================

if exist ".venv\Scripts\python.exe" (
    echo [OK] Entorno virtual detectado.
    ".venv\Scripts\python.exe" -m caine.main
) else (
    echo [ADVERTENCIA] No se encontro .venv. Usando Python global...
    python -m caine.main
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] CAINE se cerro de forma inesperada.
    pause
)
