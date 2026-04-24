<#
.SYNOPSIS
Actualiza dependencias clave de CAINE de forma segura.
#>
Write-Host ">> Actualizando dependencias a la última versión estable..." -ForegroundColor Yellow
python -m pip install --upgrade requests pyyaml psutil pyttsx3 pyautogui sounddevice vosk opencv-python pytesseract Pillow SpeechRecognition
Write-Host "[OK] Dependencias actualizadas." -ForegroundColor Green
