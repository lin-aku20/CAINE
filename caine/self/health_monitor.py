"""Monitor de salud de los subsistemas de CAINE."""

import asyncio
import logging
import psutil

try:
    import requests
except ImportError:
    requests = None

class HealthMonitor:
    """Supervisa el estado del LLM, RAM y CPU en background."""
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.health")
        self.ollama_ok = True
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        
    async def run(self, stop_signal: asyncio.Event) -> None:
        self.logger.info("Health Monitor activado.")
        while not stop_signal.is_set():
            for _ in range(120):
                if stop_signal.is_set():
                    return
                await asyncio.sleep(1.0)
            
            self._check_ollama()
            self._check_resources()

    def _check_ollama(self) -> None:
        if not requests:
            return
            
        try:
            r = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
            was_ok = self.ollama_ok
            self.ollama_ok = r.status_code == 200
            if not self.ollama_ok and was_ok:
                self.logger.error("Se perdio conexion con Ollama en caliente.")
        except Exception:
            self.ollama_ok = False
            self.logger.error("Ollama caido. Se requiere intervencion.")
            
    def _check_resources(self) -> None:
        try:
            self.cpu_usage = psutil.cpu_percent()
            self.ram_usage = psutil.virtual_memory().percent
            if self.cpu_usage > 90.0:
                self.logger.warning("ALERTA: Consumo de CPU critico (%s%%)", self.cpu_usage)
        except Exception:
            pass
