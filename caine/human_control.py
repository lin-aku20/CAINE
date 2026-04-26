"""Capa de control humano para CAINE.

Permite automatizar acciones físicas de teclado, ratón y foco de ventanas.
Se añaden salvaguardias para evitar ejecuciones no deseadas.
"""

from __future__ import annotations

import logging
import time

import pyautogui
import pygetwindow as gw

# Desactivar failsafe para evitar que el script crashee si el mouse toca las esquinas
pyautogui.FAILSAFE = False


class HumanController:
    """Implementa el control físico del sistema operativo (mouse, teclado, ventanas)."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.human_control")

    def press_key(self, key: str):
        pyautogui.press(key)

    def type_text(self, text: str):
        pyautogui.write(text, interval=0.02)

    def press_hotkey(self, *keys):
        pyautogui.hotkey(*keys)
        time.sleep(0.3)

    def click(self, x: int, y: int):
        pyautogui.click(x, y)

    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> str:
        """Mueve el ratón a una posición (x, y)."""
        self.logger.info("[HUMAN_ACTION] Moviendo ratón a (%s, %s)", x, y)
        pyautogui.moveTo(x, y, duration=duration)
        return f"Ratón movido a {x}, {y}."

    def drag_to(self, x: int, y: int, duration: float = 0.4) -> str:
        """Arrastra el ratón a una posición (x, y)."""
        self.logger.info("[HUMAN_ACTION] Arrastrando ratón a (%s, %s)", x, y)
        pyautogui.dragTo(x, y, duration=duration)
        return f"Ratón arrastrado a {x}, {y}."

    def left_click(self) -> str:
        self.logger.info("[HUMAN_ACTION] click")
        pyautogui.click()
        return "Clic izquierdo realizado."

    def move_and_click(self, x: int, y: int, duration: float = 0.5) -> str:
        """Mueve el ratón fluidamente al centro del elemento y hace clic."""
        self.logger.info("[HUMAN_ACTION] move_and_click at (%s, %s)", x, y)
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
        pyautogui.click()
        return f"Clic en {x}, {y}."

    def right_click(self) -> str:
        self.logger.info("[HUMAN_ACTION] right_click")
        pyautogui.rightClick()
        return "Clic derecho realizado."

    def double_click(self) -> str:
        self.logger.info("[HUMAN_ACTION] double_click")
        pyautogui.doubleClick()
        return "Doble clic realizado."

    def write(self, text: str, interval: float = 0.02) -> str:
        """Escribe texto simulando tecleo humano."""
        self.logger.info("[HUMAN_ACTION] typing: %s", text)
        pyautogui.write(text, interval=interval)
        return f"Texto escrito: '{text}'."

    def press(self, key: str) -> str:
        """Presiona una tecla específica (ej: 'enter', 'tab')."""
        self.logger.info("[HUMAN_ACTION] press_key: %s", key)
        pyautogui.press(key)
        return f"Tecla '{key}' presionada."

    def hotkey(self, *keys: str) -> str:
        """Ejecuta un atajo de teclado (ej: 'ctrl', 'c')."""
        self.logger.info("[HUMAN_ACTION] hotkey: %s", keys)
        pyautogui.hotkey(*keys)
        return f"Atajo '{'+'.join(keys)}' ejecutado."

    def scroll(self, amount: int) -> str:
        self.logger.info("[HUMAN_ACTION] scroll: %s", amount)
        pyautogui.scroll(amount)
        return f"Scroll aplicado ({amount})."

    def send_message(self, text: str) -> str:
        """Envía un mensaje rápidamente seguido de enter."""
        self.logger.info("[HUMAN_ACTION] send_message: %s", text)
        pyautogui.write(text, interval=0.01)
        pyautogui.press("enter")
        return f"Mensaje enviado: '{text}'."

    def focus_app(self, app_name: str) -> str:
        """Enfoca una ventana por nombre aproximado."""
        self.logger.info("[HUMAN_ACTION] focus_app: %s", app_name)
        windows = gw.getWindowsWithTitle(app_name)
        if not windows:
            # Reintentar en minúsculas
            all_windows = gw.getAllTitles()
            matches = [t for t in all_windows if app_name.lower() in t.lower()]
            if matches:
                windows = gw.getWindowsWithTitle(matches[0])
                
        if windows:
            win = windows[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                # Pequeña pausa para asegurar que el foco se asiente
                time.sleep(0.3)
                return f"Ventana '{win.title}' enfocada exitosamente."
            except Exception as e:
                self.logger.warning("Fallo al activar ventana %s: %s", win.title, e)
                return f"Encontré la ventana '{win.title}', pero no pude activarla: {e}"
                
        return f"No se encontró ninguna ventana con el título '{app_name}'."

    def safe_press(self, key: str) -> str:
        try:
            return self.press(key)
        except TypeError:
            return self.press(str(key))

    def click_screen_center(self):
        import pyautogui
        w, h = pyautogui.size()
        pyautogui.click(w//2, h-120)

    def click_relative(self, x_ratio: float, y_ratio: float):
        import pyautogui
        w, h = pyautogui.size()
        pyautogui.click(int(w * x_ratio), int(h * y_ratio))
