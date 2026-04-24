@echo off
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%~dp0launch_openclaw_hidden.vbs"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$startup = [Environment]::ExpandEnvironmentVariables('%STARTUP%\\OpenClaw Gateway.lnk'); " ^
  "$target = [Environment]::ExpandEnvironmentVariables('%TARGET%'); " ^
  "$workdir = [Environment]::ExpandEnvironmentVariables('%~dp0'); " ^
  "$icon = [Environment]::ExpandEnvironmentVariables('%SystemRoot%\\System32\\shell32.dll,220'); " ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$lnk = $ws.CreateShortcut($startup); " ^
  "$lnk.TargetPath = $target; " ^
  "$lnk.WorkingDirectory = $workdir; " ^
  "$lnk.IconLocation = $icon; " ^
  "$lnk.Save()"

echo Autoarranque de OpenClaw activado.
