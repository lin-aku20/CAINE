<#
.SYNOPSIS
Valida si el entorno de CAINE esta sano y funcional.
#>
$ErrorActionPreference = "Stop"
$failed = $false

Write-Host ">> Ejecutando Health Check de CAINE..." -ForegroundColor Cyan

# 1. Chequear Dependencias
try {
    python -c "import cv2, pyautogui, pytesseract, sounddevice, vosk" 2>$null
    Write-Host "[OK] Paquetes criticos cargados." -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Faltan paquetes de Python." -ForegroundColor Red
    $failed = $true
}

# 2. Chequear Tesseract
$tess1 = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$tess2 = 'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
if ((Test-Path $tess1) -or (Test-Path $tess2)) {
    Write-Host "[OK] Tesseract OCR detectado." -ForegroundColor Green
} else {
    Write-Host "[WARN] No se encontro Tesseract OCR (fallbacks activados)." -ForegroundColor Yellow
}

# 3. Chequear Ollama
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get
    if ($resp.models.name -contains "caine:latest") {
        Write-Host "[OK] Ollama y modelo caine:latest listos." -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Modelo caine:latest no descargado en Ollama." -ForegroundColor Red
        $failed = $true
    }
} catch {
    Write-Host "[FAIL] Ollama no responde." -ForegroundColor Red
    $failed = $true
}

if ($failed) {
    Write-Host ">> Health Check FALLO. Requiere reparacion." -ForegroundColor Red
    exit 1
} else {
    Write-Host ">> Health Check PASO. Sistema sano." -ForegroundColor Green
    exit 0
}
