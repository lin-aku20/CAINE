# ============================================================
# CAINE - Instalador Automático de Tesseract OCR
# Ejecutar como ADMINISTRADOR
# ============================================================

param(
    [string]$TesseractVersion = "5.5.0.20241111",
    [string]$InstallPath = "C:\Program Files\Tesseract-OCR"
)

$ErrorActionPreference = "Stop"

function Write-Status($msg, $color = "Cyan") {
    Write-Host "[$([datetime]::Now.ToString('HH:mm:ss'))] $msg" -ForegroundColor $color
}

Write-Status "=== CAINE - Instalador Tesseract OCR ===" "Magenta"

# --- Verificar si ya está instalado ---
$tessExe = Join-Path $InstallPath "tesseract.exe"
if (Test-Path $tessExe) {
    $ver = & $tessExe --version 2>&1 | Select-Object -First 1
    Write-Status "[OK] Tesseract ya instalado: $ver" "Green"
} else {
    Write-Status "Descargando Tesseract v$TesseractVersion..." "Yellow"

    $url = "https://github.com/tesseract-ocr/tesseract/releases/download/$($TesseractVersion.Split('.')[0..2] -join '.')/tesseract-ocr-w64-setup-$TesseractVersion.exe"
    $installer = "$env:TEMP\tesseract_setup.exe"

    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($url, $installer)
        Write-Status "Descarga completa. Instalando silenciosamente..." "Yellow"
        Start-Process -FilePath $installer -ArgumentList "/SILENT /NORESTART /DIR=`"$InstallPath`"" -Wait -Verb RunAs
        Write-Status "[OK] Tesseract instalado en: $InstallPath" "Green"
    } catch {
        Write-Status "[ERROR] Fallo descarga/instalación: $($_.Exception.Message)" "Red"
        Write-Status "Descarga manual: https://github.com/tesseract-ocr/tesseract/releases/latest" "Yellow"
        exit 1
    }
}

# --- Configurar PATH del sistema ---
Write-Status "Verificando PATH del sistema..." "Cyan"
$syspath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($syspath -notlike "*Tesseract-OCR*") {
    Write-Status "Agregando Tesseract al PATH del sistema..." "Yellow"
    [System.Environment]::SetEnvironmentVariable("PATH", "$syspath;$InstallPath", "Machine")
    $env:PATH = "$env:PATH;$InstallPath"
    Write-Status "[OK] PATH actualizado" "Green"
} else {
    Write-Status "[OK] Tesseract ya está en PATH" "Green"
}

# --- Actualizar config.yaml de CAINE ---
$configFile = "$PSScriptRoot\..\config\config.yaml"
Write-Status "Actualizando config.yaml de CAINE..." "Cyan"

if (Test-Path $configFile) {
    $content = Get-Content $configFile -Raw
    # Reemplazar tesseract_cmd vacío
    $newContent = $content -replace 'tesseract_cmd:\s*""', "tesseract_cmd: `"$($tessExe -replace '\\', '/')`""
    $newContent | Set-Content $configFile -Encoding UTF8
    Write-Status "[OK] config.yaml actualizado con ruta: $tessExe" "Green"
} else {
    Write-Status "[WARN] config.yaml no encontrado en: $configFile" "Yellow"
}

# --- Validar instalación ---
Write-Status "Validando instalación..." "Cyan"
try {
    $ver = & "$tessExe" --version 2>&1 | Select-Object -First 1
    Write-Status "[OK] Validación exitosa: $ver" "Green"

    # Test OCR básico con imagen en blanco
    $venvPython = "$PSScriptRoot\..\. venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Status "Probando pytesseract con Python..." "Cyan"
        & $venvPython -c @"
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'$tessExe'
from PIL import Image, ImageDraw
img = Image.new('RGB', (200, 50), color='white')
d = ImageDraw.Draw(img)
d.text((10, 10), 'CAINE OK', fill='black')
text = pytesseract.image_to_string(img).strip()
print('[OCR TEST] Resultado:', text)
"@ 2>&1
    }
} catch {
    Write-Status "[ERROR] Validación fallida: $($_.Exception.Message)" "Red"
}

Write-Status "=== Instalación completa ===" "Magenta"
Write-Status "Reinicia CAINE para aplicar cambios." "Yellow"
