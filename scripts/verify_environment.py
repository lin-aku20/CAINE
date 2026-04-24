"""Verifica dependencias Python y estructura basica del proyecto."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path


REQUIRED_MODULES = [
    "requests",
    "yaml",
    "psutil",
    "pyttsx3",
    "pyautogui",
    "sounddevice",
    "vosk",
    "openwakeword",
    "cv2",
    "pytesseract",
    "PIL",
    "speech_recognition",
    "piper",
]

REQUIRED_PATHS = [
    Path("config.yaml"),
    Path("personality/caine.txt"),
    Path("models/caine.Modelfile"),
    Path("logs"),
]


def main() -> None:
    print("Verificando modulos Python:")
    for module_name in REQUIRED_MODULES:
        try:
            import_module(module_name)
            print(f"  [OK] {module_name}")
        except ImportError:
            print(f"  [MISSING] {module_name}")

    print("\nVerificando rutas:")
    for path in REQUIRED_PATHS:
        print(f"  [{'OK' if path.exists() else 'MISSING'}] {path}")


if __name__ == "__main__":
    main()
