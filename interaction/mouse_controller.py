"""Control seguro de mouse para CAINE."""

from __future__ import annotations

from interaction.action_guard import ActionGuard
from caine.config import ActionSettings, InteractionSettings


class MouseController:
    """Controla el mouse con guardas sencillas."""

    def __init__(self, action_settings: ActionSettings, interaction_settings: InteractionSettings) -> None:
        self.guard = ActionGuard(action_settings)
        self.settings = interaction_settings

    def move_to(self, x: int, y: int) -> str:
        if not self.guard.can_use_admin_actions():
            return "Mover el mouse libremente exige modo admin."

        try:
            import pyautogui
        except ImportError:
            return "Falta pyautogui para mover el puntero."

        width, height = pyautogui.size()
        margin = self.settings.safe_screen_margin
        clamped_x = max(margin, min(width - margin, x))
        clamped_y = max(margin, min(height - margin, y))
        pyautogui.moveTo(clamped_x, clamped_y, duration=self.settings.mouse_duration_seconds)
        return f"Mouse movido a {clamped_x}, {clamped_y}."

    def click(self, button: str = "left") -> str:
        if not self.guard.can_use_admin_actions():
            return "Hacer click exige modo admin."
        try:
            import pyautogui
        except ImportError:
            return "Falta pyautogui para hacer click."

        pyautogui.click(button=button)
        return f"Click {button} ejecutado."
