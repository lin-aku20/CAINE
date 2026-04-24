@echo off
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CAINE Companion.lnk"
if exist "%LNK%" del "%LNK%"
echo Autoarranque deshabilitado.
