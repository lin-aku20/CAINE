@echo off
cd /d "%~dp0"

set "OPENCLAW_URL=http://127.0.0.1:18789/#token=c0d88c3cee9e403accf84ac9d1f94d30c26b24b996096d8c"
set "CAINE_WEB_URL=http://127.0.0.1:8765"
set "OLLAMA_EXE=C:\Users\melin\AppData\Local\Programs\Ollama\ollama.exe"

set "OLLAMA_UP="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":11434 .*LISTENING"') do (
    set "OLLAMA_UP=1"
    goto :ollama_checked
)
:ollama_checked
if not defined OLLAMA_UP (
    start "" "%OLLAMA_EXE%"
)

set "OPENCLAW_UP="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":18789 .*LISTENING"') do (
    set "OPENCLAW_UP=1"
    goto :openclaw_checked
)
:openclaw_checked
if not defined OPENCLAW_UP (
    start "" wscript.exe "%~dp0launch_openclaw_hidden.vbs"
)

set "WEB_UP="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8765 .*LISTENING"') do (
    set "WEB_UP=1"
    goto :web_checked
)
:web_checked
if not defined WEB_UP (
    start "" /min cmd /c "%~dp0run_caine_web.bat"
)

timeout /t 3 /nobreak >nul
start "" "%OPENCLAW_URL%"
timeout /t 1 /nobreak >nul
start "" "%CAINE_WEB_URL%"
