"""Controlador de parametros del sistema operativo para CAINE."""

from interaction.keyboard_controller import KeyboardController

class SystemController:
    """Controla funciones de hardware/OS como volumen, brillo, etc."""

    def __init__(self, keyboard: KeyboardController) -> None:
        self.kb = keyboard
        
    def volume_up(self, steps: int = 2) -> str:
        for _ in range(steps):
            self.kb.hotkey("volumeup")
        return f"Subiendo volumen {steps} niveles."
        
    def volume_down(self, steps: int = 2) -> str:
        for _ in range(steps):
            self.kb.hotkey("volumedown")
        return f"Bajando volumen {steps} niveles."
        
    def volume_mute(self) -> str:
        self.kb.hotkey("volumemute")
        return "Volumen silenciado/restaurado."
