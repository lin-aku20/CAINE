@echo off
cd /d "%~dp0"

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%~dp0launch_caine_hidden.vbs"
set "LNK=%STARTUP%\CAINE Companion.lnk"

if not exist ".venv\Scripts\pythonw.exe" (
    echo No se encontro .venv\Scripts\pythonw.exe
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%LNK%'); $s.TargetPath = '%SystemRoot%\System32\wscript.exe'; $s.Arguments = '\"%VBS%\"'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%SystemRoot%\System32\shell32.dll,220'; $s.Save()"
echo Autoarranque habilitado en: %LNK%
