<#
.SYNOPSIS
Limpia la caché temporal y los logs antiguos de CAINE.
#>
Write-Host ">> Limpiando __pycache__ y temporales..." -ForegroundColor Yellow
Get-ChildItem -Path .\ -Include __pycache__ -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path .\logs\screens\ -Include *.png, *.jpg -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "[OK] Caché limpiada." -ForegroundColor Green
