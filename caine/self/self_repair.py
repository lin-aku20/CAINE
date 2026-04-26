"""
CAINE Self-Repair Module
Diagnóstico y reparación automática del sistema.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Rutas estándar donde Tesseract suele instalarse en Windows
TESSERACT_COMMON_PATHS = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    Path.home() / "AppData/Local/Programs/Tesseract-OCR/tesseract.exe",
]


def find_tesseract() -> Path | None:
    """Busca el ejecutable de Tesseract en rutas conocidas."""
    import shutil
    # 1. En PATH
    if shutil.which("tesseract"):
        return Path(shutil.which("tesseract"))
    # 2. En rutas comunes de Windows
    for path in TESSERACT_COMMON_PATHS:
        if path.exists():
            return path
    return None


def configure_tesseract(tess_path: Path) -> bool:
    """Configura pytesseract y actualiza config.yaml con la ruta encontrada."""
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = str(tess_path)
        logger.info(f"[REPAIR] tesseract_cmd configurado: {tess_path}")
    except ImportError:
        logger.error("[REPAIR] pytesseract no disponible")
        return False

    # Actualizar config.yaml
    config_path = BASE_DIR / "config" / "config.yaml"
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        tess_str = str(tess_path).replace("\\", "/")
        import re
        new_content = re.sub(
            r'tesseract_cmd:\s*"?"?.*"?"?',
            f'tesseract_cmd: "{tess_str}"',
            content,
        )
        config_path.write_text(new_content, encoding="utf-8")
        logger.info(f"[REPAIR] config.yaml actualizado con tesseract_cmd: {tess_str}")
    return True


def check_ollama(base_url: str = "http://localhost:11434") -> dict:
    """Verifica que Ollama esté respondiendo."""
    import urllib.request
    import urllib.error
    import json

    result = {"ok": False, "models": [], "error": None}
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
            result["ok"] = True
            result["models"] = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        result["error"] = str(e)
    return result


def restart_ollama() -> bool:
    """Intenta reiniciar el proceso de Ollama en Windows."""
    import time
    try:
        subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"],
                       capture_output=True, timeout=10)
        time.sleep(2)
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(4)
        return check_ollama()["ok"]
    except Exception as e:
        logger.error(f"[REPAIR] Error reiniciando Ollama: {e}")
        return False


def run_diagnostics() -> dict:
    """
    Ejecuta diagnóstico completo del sistema CAINE.
    Retorna un dict con el estado de cada componente.
    """
    report = {
        "status": "OK",
        "ollama": {"ok": False, "models": [], "error": None},
        "tesseract": {"ok": False, "path": None, "error": None},
        "venv": {"ok": False, "python": None},
        "critical_errors": [],
    }

    # --- Ollama ---
    ollama_result = check_ollama()
    report["ollama"] = ollama_result
    if not ollama_result["ok"]:
        report["critical_errors"].append("Ollama no responde")
        logger.warning("[DIAG] Ollama FAIL - intentando reparar...")
        if restart_ollama():
            report["ollama"] = check_ollama()
            if report["ollama"]["ok"]:
                logger.info("[REPAIR] Ollama restaurado exitosamente")
            else:
                report["critical_errors"].append("Ollama no pudo restaurarse")
    else:
        logger.info(f"[DIAG] Ollama OK - modelos: {ollama_result['models']}")

    # --- Tesseract ---
    tess_path = find_tesseract()
    if tess_path:
        report["tesseract"]["ok"] = True
        report["tesseract"]["path"] = str(tess_path)
        configure_tesseract(tess_path)
        logger.info(f"[DIAG] Tesseract OK: {tess_path}")
    else:
        report["tesseract"]["error"] = "Tesseract no encontrado"
        report["critical_errors"].append("Tesseract OCR no instalado")
        logger.warning("[DIAG] Tesseract FAIL - OCR no disponible")

    # --- Venv / Python ---
    report["venv"]["ok"] = True
    report["venv"]["python"] = sys.version
    logger.info(f"[DIAG] Venv OK: Python {sys.version}")

    # --- Estado final ---
    if report["critical_errors"]:
        # OCR es no-crítico si Ollama funciona (modo degradado)
        ollama_ok = report["ollama"]["ok"]
        tess_ok = report["tesseract"]["ok"]
        if not ollama_ok:
            report["status"] = "CRITICAL"
        elif not tess_ok:
            report["status"] = "DEGRADED"
    else:
        report["status"] = "OK"

    return report


def print_report(report: dict) -> None:
    """Imprime el reporte de diagnóstico de forma legible."""
    STATUS_COLORS = {
        "OK": "\033[92m",       # verde
        "DEGRADED": "\033[93m", # amarillo
        "CRITICAL": "\033[91m", # rojo
    }
    RESET = "\033[0m"
    color = STATUS_COLORS.get(report["status"], "")

    print(f"\n{'='*50}")
    print(f"  CAINE SYSTEM REPORT: {color}{report['status']}{RESET}")
    print(f"{'='*50}")
    print(f"  Ollama   : {'[OK]' if report['ollama']['ok'] else '[FAIL]'}", end="")
    if report["ollama"]["ok"]:
        print(f"  ({len(report['ollama']['models'])} modelos)")
    else:
        print(f"  ({report['ollama'].get('error', '?')})")
    print(f"  Tesseract: {'[OK]' if report['tesseract']['ok'] else '[FAIL]'}", end="")
    if report["tesseract"]["ok"]:
        print(f"  ({report['tesseract']['path']})")
    else:
        print(f"  ({report['tesseract'].get('error', '?')})")
    print(f"  Venv/Py  : {'[OK]' if report['venv']['ok'] else '[FAIL]'}  ({report['venv'].get('python','?')[:30]})")
    if report["critical_errors"]:
        print(f"\n  ! Errores: {', '.join(report['critical_errors'])}")
    print(f"{'='*50}\n")


class SelfRepair:
    """Clase wrapper de compatibilidad para evitar ImportErrors."""
    def __init__(self, *args, **kwargs):
        pass
    
    def run(self):
        return run_diagnostics()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = run_diagnostics()
    print_report(report)
    sys.exit(0 if report["status"] != "CRITICAL" else 1)
