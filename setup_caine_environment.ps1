<#
.SYNOPSIS
Instalador automático para el entorno de CAINE.

.DESCRIPTION
Este script verifica y repara las dependencias de Python, binarios y conexión a Ollama necesarios para despertar a CAINE.
#>

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " CAINE - CONFIGURACIÓN DEL ENTORNO " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar Python
Write-Host ">> Verificando Python..." -ForegroundColor Yellow
if (!(Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python no está instalado o no está en el PATH." -ForegroundColor Red
    exit
}
Write-Host "[OK] Python encontrado." -ForegroundColor Green

# 2. Instalar Dependencias de Python
$packages = @("opencv-python", "pyautogui", "pytesseract", "vosk", "sounddevice", "pyttsx3", "numpy", "pillow", "psutil", "SpeechRecognition", "requests", "pyyaml")
Write-Host "`n>> Instalando y verificando paquetes de Python..." -ForegroundColor Yellow
foreach ($pkg in $packages) {
    python -m pip install $pkg --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $pkg" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Falló la instalación de $pkg" -ForegroundColor Red
    }
}

# 3. Verificar Tesseract OCR (Visión)
Write-Host "`n>> Verificando Tesseract OCR..." -ForegroundColor Yellow
$tesseractPath1 = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$tesseractPath2 = 'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
if ((Test-Path $tesseractPath1) -or (Test-Path $tesseractPath2)) {
    Write-Host "[OK] Tesseract OCR encontrado." -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] Tesseract OCR no encontrado. CAINE no podrá leer la pantalla." -ForegroundColor Yellow
}

# 4. Verificar Modelos de Vosk (Escucha)
Write-Host "`n>> Verificando modelo de Vosk..." -ForegroundColor Yellow
$voskDir = ".\models\vosk"
if ((Test-Path $voskDir) -and ((Get-ChildItem -Path $voskDir).Count -gt 0)) {
    Write-Host "[OK] Modelo de Vosk encontrado en $voskDir" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] No se encontró el modelo Vosk. CAINE no podrá oír." -ForegroundColor Yellow
}

# 5. Validar conexión a Ollama (Cerebro)
Write-Host "`n>> Verificando conexión a Ollama..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -ErrorAction Stop
    if ($response.models.name -contains "caine:latest") {
        Write-Host "[OK] Ollama conectado y modelo caine:latest detectado." -ForegroundColor Green
    } else {
        Write-Host "[ADVERTENCIA] Ollama conectado, pero el modelo 'caine:latest' no está descargado." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] No se pudo conectar a Ollama en el puerto 11434." -ForegroundColor Red
}

# 6. Validar Micrófono
Write-Host "`n>> Verificando acceso al Micrófono..." -ForegroundColor Yellow
# Un check básico en Windows requiere acceder a dispositivos de audio.
# Simularemos el check invocando a python sounddevice si existe.
try {
    $script = 'import sounddevice as sd; print(len(sd.query_devices()))'
    $micCheck = python -c $script 2> $null
} catch {
    $micCheck = 0
}
if ($micCheck -gt 0) {
    Write-Host "[OK] Microfono detectado por sounddevice." -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] No se detectó un dispositivo de audio para grabar." -ForegroundColor Yellow
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host " REVISIÓN DE ENTORNO COMPLETADA " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
