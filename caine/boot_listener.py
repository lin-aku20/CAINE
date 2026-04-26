import time
import subprocess
import os
import sys

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("Error: sounddevice o numpy no están instalados. Instálalos con 'pip install sounddevice numpy'")
    sys.exit(1)

# Umbral de volumen para considerar un aplauso
CLAP_THRESHOLD = 0.5  # Ajustar según sensibilidad del micrófono
# Frecuencia de muestreo
SAMPLE_RATE = 44100
# Tamaño del bloque (latencia)
BLOCK_SIZE = 1024

def process_audio(indata, frames, time_info, status):
    if status:
        print(status)
    
    # Calcular la amplitud RMS (Root Mean Square) del bloque de audio
    rms = np.sqrt(np.mean(indata**2))
    
    if rms > CLAP_THRESHOLD:
        print(f"[BOOT] ¡Aplauso detectado! (Amplitud: {rms:.2f}) Iniciando CAINE GUI...")
        raise sd.CallbackStop()

def listen_for_clap():
    print(f"[BOOT] CAINE Boot Listener activo. Escuchando aplausos en segundo plano (Umbral: {CLAP_THRESHOLD})...")
    
    try:
        # Iniciamos el stream de audio de entrada
        with sd.InputStream(callback=process_audio, channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE):
            # Mantenemos el hilo vivo mientras escucha
            while True:
                sd.sleep(100)
    except sd.CallbackStop:
        # Cuando se detecta el aplauso, lanzamos la GUI
        launch_gui()
    except KeyboardInterrupt:
        print("[BOOT] Listener terminado por el usuario.")
    except Exception as e:
        print(f"[BOOT] Error en el stream de audio: {e}")

def launch_gui():
    # Obtener la ruta del ejecutable principal de la GUI
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gui_script = os.path.join(base_dir, "caine", "gui", "desktop_ui.py")
    
    if os.path.exists(gui_script):
        print(f"[BOOT] Lanzando segundo escritorio: {gui_script}")
        # Lanzar el script como un subproceso independiente
        subprocess.Popen([sys.executable, gui_script], 
                         creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
    else:
        print(f"[BOOT] Error: No se encontró el script de la GUI en {gui_script}")

if __name__ == "__main__":
    listen_for_clap()
