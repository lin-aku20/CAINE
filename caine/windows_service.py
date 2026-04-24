"""Servicio Windows para mantener CAINE residente."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

import servicemanager
import win32event
import win32service
import win32serviceutil


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from caine.config import CaineConfig
from caine.logging_utils import configure_logging


class CaineWindowsService(win32serviceutil.ServiceFramework):
    """Envuelve el runtime residente en un servicio Windows real."""

    _svc_name_ = "CAINE"
    _svc_display_name_ = "CAINE Local AI Assistant"
    _svc_description_ = "Servicio persistente de CAINE para supervision y reinicio automatico."

    def __init__(self, args) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen[str] | None = None
        self.running = True
        self.config = CaineConfig.from_yaml()
        configure_logging(self.config.logging.log_file, self.config.logging.level)

        self._svc_name_ = self.config.service.service_name
        self._svc_display_name_ = self.config.service.display_name
        self._svc_description_ = self.config.service.description

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self) -> None:
        servicemanager.LogInfoMsg("CAINE service starting")
        self.main()

    def main(self) -> None:
        python_executable = sys.executable
        command = [python_executable, str(ROOT_DIR / "main.py"), "--resident", "--headless"]

        while self.running:
            self.process = subprocess.Popen(command, cwd=str(ROOT_DIR))
            while self.running and self.process.poll() is None:
                wait_code = win32event.WaitForSingleObject(self.stop_event, 1000)
                if wait_code == win32event.WAIT_OBJECT_0:
                    self.running = False
                    break

            if not self.running:
                break

            time.sleep(self.config.service.restart_delay_seconds)

        if self.process and self.process.poll() is None:
            self.process.terminate()
        servicemanager.LogInfoMsg("CAINE service stopped")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(CaineWindowsService)
