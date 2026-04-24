"""Control seguro de teclado para CAINE."""

from __future__ import annotations

from interaction.action_guard import ActionGuard
from caine.config import ActionSettings, InteractionSettings


class KeyboardController:
    """Simula teclado respetando el guard actual."""

    def __init__(self, action_settings: ActionSettings, interaction_settings: InteractionSettings) -> None:
        self.guard = ActionGuard(action_settings)
        self.settings = interaction_settings

    def hotkey(self, combo: str) -> str:
        if not self.guard.can_use_power_actions():
            return "El teclado libre exige modo power o admin."
        if not self.guard.is_allowed_hotkey(combo):
            return f"El atajo '{combo}' no esta autorizado."

        try:
            import pyautogui
        except ImportError:
            return "Falta pyautogui para tocar el teclado del escenario."

        keys = [part.strip() for part in combo.split("+") if part.strip()]
        pyautogui.hotkey(*keys)
        return f"Atajo ejecutado: {combo}"

    def type_text(self, text: str) -> str:
        if not self.guard.can_use_admin_actions():
            return "Escribir texto arbitrario exige modo admin."
        try:
            import pyautogui
        except ImportError:
            return "Falta pyautogui para escribir en escena."

        pyautogui.write(text, interval=self.settings.typing_interval_seconds)
        return "Texto escrito en la ventana activa."
