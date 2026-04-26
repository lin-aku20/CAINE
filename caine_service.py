"""caine_service.py — Servicio residente de CAINE.

Se ejecuta en segundo plano desde el arranque del sistema.
Escucha la wake word de forma pasiva (bajo consumo CPU).
Cuando detecta la wake word, lanza la entidad principal de CAINE.

Instalación como servicio Windows:
    python caine_service.py install
    python caine_service.py start
    python caine_service.py --startup auto install

Inicio manual para pruebas:
    python caine_service.py debug
    python caine_service.py --foreground   (sin servicio Windows)

Para startup simple en HKCU (alternativa al servicio):
    python caine_service.py --register-startup
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
import time
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ------------------------------------------------------------------
# Configuración básica de logging antes de importar módulos del proyecto
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CAINE-SERVICE] %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(ROOT_DIR / "logs" / "caine_service.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("caine.service")

# Crear directorio de logs si no existe
(ROOT_DIR / "logs").mkdir(exist_ok=True)

VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
MAIN_SCRIPT = ROOT_DIR / "caine" / "main.py"

WAKE_VARIANTS = ["caine", "despierta", "hey caine", "oye caine", "kai", "cayne"]


# ---------------------------------------------------------------------------
# Wake Listener — escucha pasiva de wake word via Vosk
# ---------------------------------------------------------------------------

class WakeListener:
    """Escucha el micrófono de forma pasiva con Vosk (bajo consumo CPU)."""

    def __init__(self, on_wake_detected: callable) -> None:
        self._on_wake = on_wake_detected
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running.set()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="wake-listener")
        self._thread.start()
        logger.info("WakeListener iniciado. Wake words: %s", WAKE_VARIANTS)

    def stop(self) -> None:
        self._running.clear()

    def _listen_loop(self) -> None:
        try:
            import vosk
            import sounddevice as sd
            import json
        except ImportError as e:
            logger.error("Dependencias de voz no disponibles: %s. Wake word deshabilitado.", e)
            return

        # Cargar modelo Vosk (pequeño, para wake word)
        model_path = ROOT_DIR / "models" / "vosk-model-small-es"
        if not model_path.exists():
            # Fallback: cualquier modelo disponible
            models_dir = ROOT_DIR / "models"
            candidates = list(models_dir.glob("vosk-model*")) if models_dir.exists() else []
            if not candidates:
                logger.warning(
                    "No hay modelo Vosk disponible para wake word. "
                    "Descarga uno en https://alphacephei.com/vosk/models"
                )
                return
            model_path = candidates[0]

        try:
            model = vosk.Model(str(model_path))
            rec = vosk.KaldiRecognizer(model, 16000)
        except Exception as e:
            logger.error("No se pudo cargar el modelo Vosk: %s", e)
            return

        logger.info("Wake word activa con modelo: %s", model_path.name)

        try:
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=4096,
                dtype="int16",
                channels=1,
            ) as stream:
                while self._running.is_set():
                    try:
                        data, _ = stream.read(4096)
                        if rec.AcceptWaveform(bytes(data)):
                            result = json.loads(rec.Result())
                            text = result.get("text", "").strip().lower()
                            if text and self._is_wake_word(text):
                                logger.info("Wake word detectada: %r", text)
                                self._on_wake()
                    except Exception as e:
                        logger.debug("Error en bucle de escucha: %s", e)
                        time.sleep(0.5)
        except Exception as e:
            logger.error("Error en stream de audio: %s", e)

    @staticmethod
    def _is_wake_word(text: str) -> bool:
        return any(variant in text for variant in WAKE_VARIANTS)


# ---------------------------------------------------------------------------
# Process Manager — gestiona el proceso principal de CAINE
# ---------------------------------------------------------------------------

class CaineProcessManager:
    """Lanza y supervisa el proceso principal de CAINE."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._cooldown_seconds = 30.0
        self._last_launch_at: float = 0.0

    def launch_caine(self) -> bool:
        """Lanza la entidad principal de CAINE si no está ya corriendo.

        Returns:
            True si se lanzó un nuevo proceso.
        """
        with self._lock:
            # Verificar si ya está corriendo
            if self._process and self._process.poll() is None:
                logger.info("CAINE ya está en ejecución (pid=%d). Ignorando lanzamiento.", self._process.pid)
                return False

            # Cooldown entre lanzamientos
            if time.monotonic() - self._last_launch_at < self._cooldown_seconds:
                logger.debug("Cooldown de lanzamiento activo. Ignorando.")
                return False

            logger.info("Lanzando CAINE desde el servicio residente...")
            try:
                self._process = subprocess.Popen(
                    [PYTHON, str(MAIN_SCRIPT)],
                    cwd=str(ROOT_DIR),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                )
                self._last_launch_at = time.monotonic()
                logger.info("CAINE lanzado con pid=%d", self._process.pid)
                return True
            except Exception as e:
                logger.error("No se pudo lanzar CAINE: %s", e)
                return False

    def terminate(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None:
                logger.info("Terminando proceso CAINE (pid=%d).", self._process.pid)
                self._process.terminate()

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None


# ---------------------------------------------------------------------------
# Servicio residente (modo foreground o Windows Service)
# ---------------------------------------------------------------------------

class CAINEResidentService:
    """Servicio residente principal."""

    def __init__(self) -> None:
        self._process_manager = CaineProcessManager()
        self._wake_listener = WakeListener(on_wake_detected=self._on_wake)
        self._running = True

    def _on_wake(self) -> None:
        """Callback cuando se detecta la wake word."""
        logger.info("Wake word recibida. Iniciando CAINE...")
        launched = self._process_manager.launch_caine()
        if not launched:
            logger.info("CAINE ya estaba activo o en cooldown.")

    def run_foreground(self) -> None:
        """Corre el servicio en primer plano (para pruebas)."""
        logger.info("CAINE Resident Service iniciado en modo foreground.")
        logger.info("Esperando wake word: %s", WAKE_VARIANTS)
        logger.info("Presiona Ctrl+C para detener.")

        self._wake_listener.start()

        try:
            while self._running:
                time.sleep(5)
                # Health check del proceso CAINE
                if not self._process_manager.is_running():
                    logger.debug("CAINE no está activo. Servicio en espera de wake word.")
        except KeyboardInterrupt:
            logger.info("Servicio detenido por usuario.")
        finally:
            self._wake_listener.stop()
            self._process_manager.terminate()

    def stop(self) -> None:
        self._running = False
        self._wake_listener.stop()
        self._process_manager.terminate()


# ---------------------------------------------------------------------------
# Windows Service via pywin32
# ---------------------------------------------------------------------------

def _try_run_as_windows_service() -> None:
    """Intenta correr como servicio Windows si pywin32 está disponible."""
    try:
        import servicemanager
        import win32event
        import win32service
        import win32serviceutil

        class CAINEWindowsService(win32serviceutil.ServiceFramework):
            _svc_name_ = "CAINEResident"
            _svc_display_name_ = "CAINE Resident AI Service"
            _svc_description_ = (
                "Servicio residente de CAINE. Escucha wake word y lanza "
                "la entidad principal automáticamente."
            )

            def __init__(self, args) -> None:
                super().__init__(args)
                self._stop_event = win32event.CreateEvent(None, 0, 0, None)
                self._service = CAINEResidentService()

            def SvcStop(self) -> None:
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                self._service.stop()
                win32event.SetEvent(self._stop_event)

            def SvcDoRun(self) -> None:
                servicemanager.LogInfoMsg("CAINE Resident Service iniciado.")
                # Correr en hilo separado para no bloquear el SCM
                thread = threading.Thread(target=self._service.run_foreground, daemon=True)
                thread.start()
                win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
                servicemanager.LogInfoMsg("CAINE Resident Service detenido.")

        win32serviceutil.HandleCommandLine(CAINEWindowsService)

    except ImportError:
        logger.warning("pywin32 no disponible. Corriendo en modo foreground.")
        CAINEResidentService().run_foreground()


# ---------------------------------------------------------------------------
# Registro en Startup de Windows (alternativa al servicio)
# ---------------------------------------------------------------------------

def register_startup() -> None:
    """Registra caine_service.py en HKCU\\Run para inicio automático con Windows."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        entry_name = "CAINEResident"
        cmd = f'"{PYTHON}" "{ROOT_DIR / "caine_service.py"}" --foreground'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, entry_name, 0, winreg.REG_SZ, cmd)

        print(f"✓ CAINE registrado en startup de Windows.")
        print(f"  Comando: {cmd}")
        print(f"  Se iniciará automáticamente al próximo reinicio.")
    except Exception as e:
        print(f"✗ No se pudo registrar en startup: {e}")


def unregister_startup() -> None:
    """Elimina la entrada de startup."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, "CAINEResident")
        print("✓ CAINE eliminado del startup de Windows.")
    except FileNotFoundError:
        print("CAINE no estaba registrado en startup.")
    except Exception as e:
        print(f"✗ Error al eliminar startup: {e}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CAINE Resident Service — escucha wake word y lanza CAINE."
    )
    parser.add_argument(
        "--foreground", action="store_true",
        help="Corre el servicio en primer plano (sin instalarlo como servicio Windows)."
    )
    parser.add_argument(
        "--register-startup", action="store_true",
        help="Registra este script en el startup de Windows (HKCU Run)."
    )
    parser.add_argument(
        "--unregister-startup", action="store_true",
        help="Elimina la entrada de startup de Windows."
    )
    # Argumentos de control del servicio Windows (install/start/stop/remove)
    known, remaining = parser.parse_known_args()

    if known.register_startup:
        register_startup()
    elif known.unregister_startup:
        unregister_startup()
    elif known.foreground:
        CAINEResidentService().run_foreground()
    else:
        # Intentar como servicio Windows (requiere pywin32)
        _try_run_as_windows_service()
