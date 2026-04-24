# install_service.ps1
# Instala CAINE como un servicio de Windows para operar en 24/7 con Wake Word.

$ErrorActionPreference = "Stop"

# Requiere elevacion
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Este script requiere permisos de Administrador para instalar el servicio de Windows."
    Write-Warning "Por favor, corre PowerShell como Administrador e intentalo de nuevo."
    exit
}

$WorkspacePath = (Get-Item "..\").FullName
$PythonPath = "python"
$ServiceScript = "$WorkspacePath\caine\windows_service.py"

Write-Host "Instalando servicio CAINE..."
Write-Host "Workspace: $WorkspacePath"

# Intentar instalar
try {
    Start-Process -FilePath $PythonPath -ArgumentList "$ServiceScript --startup auto install" -Wait -NoNewWindow
    Write-Host "Servicio instalado correctamente."
} catch {
    Write-Error "Fallo la instalacion del servicio: $_"
    exit
}

# Iniciar servicio
try {
    Start-Process -FilePath $PythonPath -ArgumentList "$ServiceScript start" -Wait -NoNewWindow
    Write-Host "Servicio iniciado. CAINE ahora esta escuchando tu voz en segundo plano (24/7)."
} catch {
    Write-Warning "El servicio se instalo pero no se pudo iniciar automaticamente."
}

Write-Host ""
Write-Host "Si necesitas ver los logs, revisa logs/actions.log o usa 'Get-Service CAINE'."
