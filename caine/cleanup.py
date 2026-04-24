"""Utilidad para limpiar instancias fantasmas de CAINE y scripts relacionados."""

import os
import psutil
import logging

logger = logging.getLogger("caine.cleanup")

def cleanup_ghost_instances():
    """Busca y termina procesos de CAINE, PowerShell o CMD que esten huerfanos o duplicados."""
    current_pid = os.getpid()
    parent_pid = psutil.Process().ppid()
    count = 0
    
    logger.info(f"Iniciando limpieza desde PID: {current_pid} (Padre: {parent_pid})")
    
    # Patrones que identifican procesos relacionados con CAINE
    caine_patterns = ["caine.main", "caine/main.py", "scripts/health_check.ps1", "caine_setup"]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pid = proc.info['pid']
            if pid == current_pid or pid == parent_pid:
                continue
            
            name = (proc.info['name'] or "").lower()
            cmdline = " ".join(proc.info['cmdline'] or []).lower()
            
            should_kill = False
            
            # 1. Otras instancias de Python ejecutando CAINE
            if "python" in name:
                for pattern in caine_patterns:
                    if pattern in cmdline:
                        print(f"DEBUG: Encontrado proceso Python para matar: {pid} - CMD: {cmdline}")
                        should_kill = True
                        break
            
            # 2. Procesos de PowerShell o CMD fantasmas (Desactivado temporalmente por error 15)
            # elif name in ["powershell.exe", "pwsh.exe", "cmd.exe"]:
            #     # Si el proceso de PS o CMD menciona CAINE en su linea de comandos
            #     if "caine" in cmdline:
            #         should_kill = True
            
            if should_kill:
                logger.info(f"Terminando proceso fantasma: {name} (PID: {pid}) - CMD: {cmdline}")
                proc.terminate()
                count += 1
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
    if count > 0:
        logger.info(f"Limpieza completada. Se terminaron {count} procesos fantasmas.")
    else:
        logger.debug("No se encontraron procesos fantasmas de CAINE.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup_ghost_instances()
