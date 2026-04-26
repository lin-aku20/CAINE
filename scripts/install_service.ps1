# install_service.ps1 — Instala CAINE como servicio residente de Windows
#
# Opciones:
#   -Mode Service     → Instala como servicio Windows real (requiere pywin32, admin)
#   -Mode Startup     → Registra en HKCU\Run (sin admin, reinicio necesario)
#   -Mode Both        → Intenta servicio Windows; fallback a startup
#   -Uninstall        → Elimina el servicio o entrada de startup
#
# Uso:
#   .\scripts\install_service.ps1 -Mode Startup
#   .\scripts\install_service.ps1 -Mode Service   (como Administrador)
#   .\scripts\install_service.ps1 -Uninstall

param(
    [ValidateSet("Service", "Startup", "Both")]
    [string]$Mode = "Both",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SystemPython = (Get-Command python -ErrorAction SilentlyContinue)?.Source
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { $SystemPython }

if (-not $PythonExe) {
    Write-Error "No se encontro Python. Asegurate de que el venv este creado."
    exit 1
}

$ServiceScript = Join-Path $ProjectRoot "caine_service.py"
$ServiceName   = "CAINEResident"
$StartupName   = "CAINEResident"
$StartupKey    = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

Write-Host ""
Write-Host "=== CAINE Resident Service Installer ===" -ForegroundColor Cyan
Write-Host "Python: $PythonExe" -ForegroundColor DarkGray
Write-Host "Script: $ServiceScript" -ForegroundColor DarkGray
Write-Host ""

if ($Uninstall) {
    Write-Host "Desinstalando CAINE Resident Service..." -ForegroundColor Yellow
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($svc) {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        & $PythonExe $ServiceScript remove 2>$null
        Write-Host "  Servicio Windows eliminado." -ForegroundColor Green
    }
    if ((Get-ItemProperty -Path $StartupKey -Name $StartupName -ErrorAction SilentlyContinue)) {
        Remove-ItemProperty -Path $StartupKey -Name $StartupName
        Write-Host "  Entrada de startup eliminada." -ForegroundColor Green
    }
    Write-Host "CAINE Resident Service desinstalado." -ForegroundColor Green
    exit 0
}

function Install-AsWindowsService {
    Write-Host "Instalando como servicio Windows..." -ForegroundColor Cyan
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Warning "  Requiere privilegios de Administrador. Usa -Mode Startup en su lugar."
        return $false
    }
    try {
        & $PythonExe $ServiceScript --startup auto install
        if ($LASTEXITCODE -ne 0) { throw "Error al instalar." }
        Start-Service -Name $ServiceName
        Write-Host "  Servicio instalado e iniciado." -ForegroundColor Green
        return $true
    } catch {
        Write-Warning "  No se pudo instalar como servicio: $_"
        return $false
    }
}

function Install-AsStartupEntry {
    Write-Host "Registrando en startup (HKCU\Run)..." -ForegroundColor Cyan
    $cmd = "`"$PythonExe`" `"$ServiceScript`" --foreground"
    try {
        Set-ItemProperty -Path $StartupKey -Name $StartupName -Value $cmd
        Write-Host "  Startup registrado. Activo en el proximo inicio de sesion." -ForegroundColor Green
        Write-Host "  Comando: $cmd" -ForegroundColor DarkGray
        return $true
    } catch {
        Write-Warning "  No se pudo registrar startup: $_"
        return $false
    }
}

switch ($Mode) {
    "Service" { if (-not (Install-AsWindowsService)) { exit 1 } }
    "Startup" { if (-not (Install-AsStartupEntry))   { exit 1 } }
    "Both" {
        if (-not (Install-AsWindowsService)) {
            Write-Host "Fallback a startup entry..." -ForegroundColor Yellow
            if (-not (Install-AsStartupEntry)) { Write-Error "Instalacion fallida."; exit 1 }
        }
    }
}

Write-Host ""
Write-Host "=== Verificacion ===" -ForegroundColor Cyan
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
Write-Host "  Servicio Windows: $(if ($svc) { $svc.Status } else { 'no instalado' })"
$sv  = (Get-ItemProperty -Path $StartupKey -Name $StartupName -ErrorAction SilentlyContinue).$StartupName
Write-Host "  Startup HKCU\Run: $(if ($sv) { 'registrado' } else { 'no registrado' })"

Write-Host ""
$resp = Read-Host "Iniciar CAINE en segundo plano ahora? [S/n]"
if ($resp -eq "" -or $resp.ToUpper() -eq "S") {
    Start-Process -FilePath $PythonExe -ArgumentList "`"$ServiceScript`" --foreground" -WindowStyle Hidden
    Write-Host "CAINE Resident Service activo." -ForegroundColor Green
}
