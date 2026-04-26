import subprocess
import sys
import os

def main():
    print("[CAINE MAIN] Iniciando Oído Físico (boot_listener.py)...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    listener_script = os.path.join(base_dir, "boot_listener.py")
    
    if os.path.exists(listener_script):
        # Lanzamos el proceso independiente
        # Se quedará en la consola principal esperando el aplauso.
        try:
            subprocess.run([sys.executable, listener_script], check=True)
        except KeyboardInterrupt:
            print("\n[CAINE MAIN] Sistema apagado manualmente.")
    else:
        print(f"[CAINE MAIN] Error crítico: No se encontró el Oído Físico en {listener_script}")

if __name__ == "__main__":
    main()
