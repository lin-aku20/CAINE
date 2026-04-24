"""Sistema de autoreparacion de CAINE."""

import subprocess
import logging

class SelfRepair:
    """Invoca scripts de recuperacion cuando el sistema falla."""
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.self_repair")
        
    def trigger_repair(self) -> bool:
        self.logger.warning("Iniciando secuencia de auto-reparacion del entorno...")
        try:
            res = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/auto_repair.ps1"],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                self.logger.info("Auto-reparacion exitosa.")
                return True
            else:
                self.logger.error("Fallo la auto-reparacion: %s", res.stdout)
                return False
        except Exception as e:
            self.logger.error("Error al invocar script de reparacion: %s", e)
            return False
