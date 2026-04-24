@echo off
setlocal
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\OpenClaw Gateway.lnk"
if exist "%LINK%" del "%LINK%"
echo Autoarranque de OpenClaw desactivado.
