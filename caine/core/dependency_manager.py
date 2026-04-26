import sys
import subprocess
import logging

def is_virtual_env() -> bool:
    """1. Detectar si existe entorno virtual activo y 2. Confirmar que Python pertenece a él."""
    return sys.prefix != sys.base_prefix

def run_cmd(cmd: str) -> bool:
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def install_dependency(module_name: str) -> bool:
    logger = logging.getLogger("caine.auto_repair")
    logger.info(f"Instalando dependencia faltante: {module_name}")
    
    python_exe = sys.executable
    cmd_install = f'"{python_exe}" -m pip install {module_name}'
    
    if run_cmd(cmd_install):
        return True
        
    logger.warning(f"Fallo primera instalación de {module_name}. Intentando reparar pip...")
    
    # Reparar pip
    run_cmd(f'"{python_exe}" -m ensurepip')
    run_cmd(f'"{python_exe}" -m pip install --upgrade pip')
    
    # Reintentar instalación
    logger.info(f"Reintentando instalación de {module_name}...")
    return run_cmd(cmd_install)

def validate_dependency(import_name: str) -> bool:
    python_exe = sys.executable
    cmd_validate = f'"{python_exe}" -c "import {import_name}"'
    return run_cmd(cmd_validate)

def ensure_dependencies() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("caine.auto_repair")
    
    if not is_virtual_env():
        logger.warning("CAINE no está corriendo en un entorno virtual. Se intentará instalar globalmente.")
        
    # Mapeo de nombre de import a nombre en pip
    dependencies = {
        'mss': 'mss',
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'PIL': 'pillow',
        'pyautogui': 'pyautogui'
    }
    
    missing = []
    for import_name, pip_name in dependencies.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append((import_name, pip_name))
            
    if not missing:
        return
        
    logger.info(f"Dependencias faltantes detectadas: {[p for _, p in missing]}. Iniciando auto-reparación...")
    
    for import_name, pip_name in missing:
        success = install_dependency(pip_name)
        if success:
            if validate_dependency(import_name):
                logger.info(f"Dependencia {pip_name} instalada y validada exitosamente.")
            else:
                logger.error(f"Instalación de {pip_name} exitosa pero no se puede importar.")
        else:
            logger.error(f"Error crítico al intentar instalar {pip_name}. CAINE podría fallar.")
            
    logger.info("Auto-reparación completada. Reiniciando subsistemas en caliente...")
