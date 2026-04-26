import logging
import time
import os
from pathlib import Path

from caine.perception.desktop_vision import DesktopVisionAgent, UIElement
from caine.human_control import HumanController
from caine.core.action_result import ActionResult
from caine.app_control.discord_call_agent import DiscordCallAgent
import pygetwindow as gw

class DiscordVisionAgent:
    """Agente visual específico para Discord que utiliza percepción en lugar de clics ciegos."""
    
    def __init__(self, human: HumanController) -> None:
        self.logger = logging.getLogger("caine.discord_vision")
        self.human = human
        self.vision = DesktopVisionAgent()
        self.call_agent = DiscordCallAgent(human, self.vision)
        
        base_dir = Path(__file__).resolve().parent.parent
        self.assets_dir = base_dir / "assets"

    def open_discord(self) -> ActionResult:
        self.logger.info("[DISCORD] Opening via Vision")
        windows = gw.getWindowsWithTitle("Discord")
        
        if not windows:
            self.logger.info("[DISCORD] Launching executable")
            local_appdata = Path(os.environ.get("LOCALAPPDATA", "C:/Users/melin/AppData/Local"))
            discord_dir = local_appdata / "Discord"
            if discord_dir.exists():
                exes = sorted(discord_dir.rglob("Discord.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
                if exes:
                    os.startfile(str(exes[0]))
                    time.sleep(4.0)
                    windows = gw.getWindowsWithTitle("Discord")
        
        if windows:
            win = windows[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(1.0) # Wait for UI to render
                self.vision.capture_screen() # update baseline
                return ActionResult(True, "Discord abierto y enfocado.")
            except Exception as e:
                return ActionResult(False, f"Fallo al enfocar Discord: {e}")
        return ActionResult(False, "No pude abrir Discord.")

    def focus_chat(self, username: str) -> ActionResult:
        """Busca y enfoca un chat usando comandos pero con validación visual."""
        self.logger.info("[DISCORD] Visual chat focus: %s", username)
        
        # En Discord el buscador de canales/usuarios se activa con Ctrl+K
        import pyautogui
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.5)
        
        self.human.write(username, interval=0.05)
        time.sleep(1.5)

        # El baseline debe tomarse ANTES de confirmar la selección; si se toma
        # después, wait_for_visual_change puede perder el cambio del chat.
        self.vision.last_screen = self.vision.capture_screen(grayscale=True)
        self.human.press("enter")

        # Validación visual: el cambio al abrir un DM puede ser sutil, así que
        # usamos un threshold menor. Si no cambia, reintentamos con ↓ + Enter.
        if self.vision.wait_for_visual_change(timeout=4.0, threshold=0.005):
            return ActionResult(True, f"Chat con {username} enfocado visualmente.")

        self.logger.warning("[DISCORD] No se detectó cambio visual al abrir el chat. Reintentando con flecha abajo.")

        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.4)
        self.human.write(username, interval=0.05)
        time.sleep(1.2)
        self.vision.last_screen = self.vision.capture_screen(grayscale=True)
        self.human.press("down")
        time.sleep(0.2)
        self.human.press("enter")

        if self.vision.wait_for_visual_change(timeout=4.0, threshold=0.005):
            return ActionResult(True, f"Chat con {username} enfocado visualmente tras reintento.")

        self.logger.warning("[DISCORD] No se detectó cambio visual al abrir el chat.")
        return ActionResult(False, f"Se intentó abrir chat con {username}, pero no se detectó cambio en la interfaz.")

    def start_call(self, call_type: str = "voice") -> ActionResult:
        """Delega al DiscordCallAgent especializado.

        Args:
            call_type: 'voice' para llamada de voz, 'video' para videollamada.
        """
        if call_type == "video":
            return self.call_agent.start_video_call()
        return self.call_agent.start_voice_call()

    def send_message(self, text: str) -> ActionResult:
        """Escribe un mensaje asumiendo que el campo de texto está enfocado, o valida la acción."""
        self.logger.info("[DISCORD] Sending visual message")
        time.sleep(0.8) # 800 ms wait as requested before typing
        self.human.write(text, interval=0.02)
        self.human.press("enter")
        
        # Validar si apareció en pantalla
        if self.vision.wait_for_visual_change(timeout=2.0, threshold=0.005):
            self.logger.info("[VISION] Mensaje confirmado visualmente.")
            return ActionResult(True, "Mensaje enviado y confirmado.")
        return ActionResult(True, "Mensaje enviado (sin confirmación visual explícita).")
        
    def end_call(self) -> ActionResult:
        """Finaliza una llamada (ejemplo con botón rojo)."""
        icon_path = str(self.assets_dir / "discord_end_call_icon.png")
        element = self.vision.find_icon(icon_path, min_confidence=0.6)
        if element:
            self.human.move_and_click(*element.center)
            return ActionResult(True, "Llamada finalizada.")
        return ActionResult(False, "No se encontró el botón de finalizar.")
