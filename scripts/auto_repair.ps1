<#
.SYNOPSIS
Intenta reparar el entorno ejecutando instaladores base.
#>

Write-Host ">> Ejecutando Auto Repair de CAINE..." -ForegroundColor Yellow

Write-Host ">> Reinstalando dependencias desde requirements.txt..." -ForegroundColor Cyan
python -m pip install -r .\requirements.txt

Write-Host ">> Verificando entorno principal..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File .\setup_caine_environment.ps1

Write-Host ">> Auto Repair Finalizado. Ejecuta health_check.ps1 para validar." -ForegroundColor Green
