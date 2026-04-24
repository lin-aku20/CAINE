<#
.SYNOPSIS
Intenta reparar el entorno ejecutando el setup principal.
#>
Write-Host ">> Iniciando reparación de entorno..." -ForegroundColor Yellow
& .\setup_caine_environment.ps1
Write-Host "[OK] Reparación finalizada." -ForegroundColor Green
