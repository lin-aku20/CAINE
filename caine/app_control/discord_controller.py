"""Controlador humanoide para Discord."""

import logging
import os
import time
from pathlib import Path

import pyautogui
import pygetwindow as gw
import pyperclip
from caine.vision.discord_vision import find_and_click
try:
    import pytesseract
except ImportError:
    pytesseract = None

class DiscordController:
    """Implementa el control humanoide específicamente para la interfaz de Discord."""
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.discord")
        pyautogui.FAILSAFE = False

    def open_discord(self) -> str:
        """Abre Discord o lo trae al frente si ya está abierto."""
        self.logger.info("[DISCORD] Opening")
        windows = gw.getWindowsWithTitle("Discord")
        
        if not windows:
            self.logger.info("[DISCORD] Launching executable")
            local_appdata = Path(os.environ.get("LOCALAPPDATA", "C:/Users/melin/AppData/Local"))
            discord_dir = local_appdata / "Discord"
            if discord_dir.exists():
                exes = sorted(discord_dir.rglob("Discord.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
                if exes:
                    os.startfile(str(exes[0]))
                    time.sleep(4.0)  # Esperar arranque pesado de Electron
                    windows = gw.getWindowsWithTitle("Discord")
        
        if windows:
            win = windows[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
                return "Discord abierto y enfocado."
            except Exception as e:
                self.logger.warning("[DISCORD] Fallo al enfocar: %s", e)
                return f"Discord está abierto pero falló el enfoque: {e}"
        return "No pude abrir Discord."

    def focus_chat(self, username: str) -> str:
        """Busca a un usuario mediante CTRL+K y entra a su chat."""
        self.logger.info("[DISCORD] Chat focused: %s", username)
        
        # 1. Abrir buscador rápido
        self.logger.info("[HUMAN_ACTION] hotkey: ctrl+k")
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.5)
        
        # 2. Escribir el nombre
        self.logger.info("[HUMAN_ACTION] typing: %s", username)
        pyautogui.write(username, interval=0.05)
        time.sleep(1.5) # Esperar a que Discord busque en el servidor
        
        # 3. Presionar Enter
        self.logger.info("[HUMAN_ACTION] press_key: enter")
        pyautogui.press("enter")
        time.sleep(2.0) # Esperar carga de chat según solicitud
        return f"Chat con {username} enfocado."

    def send_message(self, text: str) -> str:
        """Escribe y envía un mensaje en el chat actualmente enfocado."""
        self.logger.info("[DISCORD] Sending message")
        
        self.logger.info("[HUMAN_ACTION] typing: %s", text)
        pyautogui.write(text, interval=0.02)
        
        self.logger.info("[HUMAN_ACTION] press_key: enter")
        pyautogui.press("enter")
        return "Mensaje enviado."

    def start_call(self) -> str:
        """Inicia una llamada intentando localizar el botón visualmente."""
        self.logger.info("[DISCORD] Starting call")
        
        base_dir = Path(__file__).resolve().parent.parent
        icon_path = str(base_dir / "assets" / "discord_call_icon.png")
        
        if find_and_click(icon_path, tries=5):
            self.logger.info("Call started")
            return "Llamada iniciada exitosamente."
            
        return "Botón de llamada no encontrado después de los reintentos."

    def end_call(self) -> str:
        """Finaliza una llamada en curso."""
        self.logger.info("[DISCORD] Ending call")
        try:
            end_btn = pyautogui.locateCenterOnScreen("assets/discord_end_call.png", confidence=0.8)
            if end_btn:
                self.logger.info("[HUMAN_ACTION] click at %s", end_btn)
                pyautogui.click(end_btn)
                return "Llamada terminada."
        except Exception:
            pass
            
        self.logger.info("[HUMAN_ACTION] click (end_call fallback)")
        return "Intento de cortar llamada completado."

    def read_last_messages(self) -> str:
        """Lee la pantalla usando Tesseract OCR para encontrar los últimos mensajes."""
        self.logger.info("[DISCORD] Reading last messages")
        if not pytesseract:
            return "El módulo pytesseract no está instalado."
            
        try:
            screenshot = pyautogui.screenshot()
            width, height = screenshot.size
            # Recortar asumiendo que el chat está en el centro-derecha inferior
            chat_region = screenshot.crop((width // 4, height // 4, width - 50, height - 80))
            
            # Ejecutar OCR
            text = pytesseract.image_to_string(chat_region, lang='spa+eng')
            if not text.strip():
                return "El OCR no detectó ningún texto claro en la región de chat."
                
            return f"Últimos mensajes detectados en pantalla:\n{text[:800]}"
        except Exception as e:
            self.logger.error("[DISCORD] OCR Falló: %s", e)
            return f"Fallo al escanear la pantalla: {e}. ¿Está Tesseract OCR instalado en Windows?"

    def play_last_audio(self) -> str:
        """Detecta y da clic al botón de play de un mensaje de voz."""
        self.logger.info("[DISCORD] Playing last audio")
        try:
            play_btn = pyautogui.locateCenterOnScreen("assets/discord_play.png", confidence=0.8)
            if play_btn:
                self.logger.info("[HUMAN_ACTION] click at %s", play_btn)
                pyautogui.click(play_btn)
                return "Audio en reproducción."
        except Exception:
            pass
            
        self.logger.info("[HUMAN_ACTION] click (play audio fallback)")
        return "Intento de reproducir audio completado. (Falta assets/discord_play.png)"
