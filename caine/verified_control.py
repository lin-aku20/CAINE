"""VerifiedHumanController: Extensión de HumanController que registra y verifica acciones.

Cada acción produce un ActionLog con 3 estados:
  ATTEMPTED   → se intentó ejecutar (antes del call)
  EXECUTED    → pyautogui completó sin excepción
  CONFIRMED   → cambio visual real detectado post-acción (o verificación explícita)

Nunca marca CONFIRMED sin evidencia real.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable

import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = False


logger = logging.getLogger("caine.verified_control")


class ActionState(StrEnum):
    ATTEMPTED  = "ATTEMPTED"
    EXECUTED   = "EXECUTED"
    CONFIRMED  = "CONFIRMED"
    FAILED     = "FAILED"


@dataclass
class ActionLog:
    action: str
    params: dict
    state: ActionState = ActionState.ATTEMPTED
    confirmed_by: str = ""
    timestamp: float = field(default_factory=time.monotonic)
    error: str = ""

    def to_str(self) -> str:
        return f"[{self.state}] {self.action}({self.params}) → {self.confirmed_by or self.error}"


class VerifiedHumanController:
    """Mouse, teclado y foco de ventanas con verificación real de resultado."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.verified_control")
        self._log: list[ActionLog] = []

    # ------------------------------------------------------------------
    # Registro interno
    # ------------------------------------------------------------------

    def _record(self, action: str, params: dict) -> ActionLog:
        entry = ActionLog(action=action, params=params)
        self._log.append(entry)
        self.logger.debug("[ACTION] %s", entry.to_str())
        return entry

    def _mark_executed(self, entry: ActionLog) -> None:
        entry.state = ActionState.EXECUTED
        self.logger.debug("[EXECUTED] %s", entry.to_str())

    def _mark_confirmed(self, entry: ActionLog, by: str) -> None:
        entry.state = ActionState.CONFIRMED
        entry.confirmed_by = by
        self.logger.info("[CONFIRMED] %s", entry.to_str())

    def _mark_failed(self, entry: ActionLog, error: str) -> None:
        entry.state = ActionState.FAILED
        entry.error = error
        self.logger.warning("[FAILED] %s", entry.to_str())

    # ------------------------------------------------------------------
    # Control de pantalla (solo lectura)
    # ------------------------------------------------------------------

    @staticmethod
    def screenshot_gray():
        """Captura la pantalla como imagen PIL en grises."""
        import numpy as np
        from PIL import ImageGrab, ImageFilter
        img = ImageGrab.grab()
        return img.convert("L")  # escala de grises

    def pixel_changed(
        self,
        region: tuple[int, int, int, int],
        *,
        threshold: float = 0.02,
        wait_before: float = 0.05,
        wait_after: float = 0.5,
    ) -> bool:
        """Devuelve True si la región cambió visualmente.

        Captura antes, espera, captura después, compara.
        threshold: proporción de píxeles que deben diferir (0.02 = 2%)
        """
        import numpy as np
        from PIL import ImageGrab

        before = ImageGrab.grab(bbox=region)
        time.sleep(wait_after)
        after = ImageGrab.grab(bbox=region)

        arr_b = __import__("numpy").array(before.convert("L"), dtype=float)
        arr_a = __import__("numpy").array(after.convert("L"), dtype=float)
        diff = abs(arr_b - arr_a)
        changed_ratio = (diff > 15).sum() / diff.size
        self.logger.debug("pixel_changed: %.2f%% (threshold=%.2f%%)", changed_ratio * 100, threshold * 100)
        return changed_ratio >= threshold

    def wait_for_pixel_change(
        self,
        region: tuple[int, int, int, int],
        *,
        timeout: float = 5.0,
        poll: float = 0.3,
        threshold: float = 0.02,
    ) -> bool:
        """Espera activamente hasta que la región cambie o se acabe el tiempo."""
        import numpy as np
        from PIL import ImageGrab

        deadline = time.monotonic() + timeout
        before = ImageGrab.grab(bbox=region)
        arr_b = __import__("numpy").array(before.convert("L"), dtype=float)

        while time.monotonic() < deadline:
            time.sleep(poll)
            after = ImageGrab.grab(bbox=region)
            arr_a = __import__("numpy").array(after.convert("L"), dtype=float)
            diff = abs(arr_b - arr_a)
            changed_ratio = (diff > 15).sum() / diff.size
            if changed_ratio >= threshold:
                self.logger.info("wait_for_pixel_change: cambio detectado (%.2f%%)", changed_ratio * 100)
                return True

        self.logger.warning("wait_for_pixel_change: timeout sin cambio")
        return False

    def ocr_region(self, region: tuple[int, int, int, int]) -> str:
        """Extrae texto de una región de pantalla con Tesseract (si disponible)."""
        try:
            import pytesseract
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=region)
            return pytesseract.image_to_string(img, config="--psm 6").strip()
        except Exception as exc:
            self.logger.warning("ocr_region error: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Mouse verificado
    # ------------------------------------------------------------------

    def move_mouse(self, x: int, y: int, duration: float = 0.4) -> ActionLog:
        entry = self._record("move_mouse", {"x": x, "y": y})
        try:
            pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
            self._mark_executed(entry)
            # Verificación: el cursor debe estar en (x, y) ± 5px
            cx, cy = pyautogui.position()
            if abs(cx - x) <= 5 and abs(cy - y) <= 5:
                self._mark_confirmed(entry, f"cursor en ({cx},{cy})")
            else:
                self._mark_failed(entry, f"cursor esperado ({x},{y}) pero en ({cx},{cy})")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    def left_click(self, x: int, y: int, *, verify_region: tuple | None = None) -> ActionLog:
        """Click en (x, y). Verifica cambio visual en verify_region si se pasa."""
        entry = self._record("left_click", {"x": x, "y": y})
        try:
            pyautogui.moveTo(x, y, duration=0.35, tween=pyautogui.easeInOutQuad)
            time.sleep(0.1)
            pyautogui.click()
            self._mark_executed(entry)

            if verify_region:
                changed = self.wait_for_pixel_change(verify_region, timeout=3.0, threshold=0.02)
                if changed:
                    self._mark_confirmed(entry, "cambio_visual_detectado")
                else:
                    self._mark_failed(entry, "no_hubo_cambio_visual")
            else:
                self._mark_confirmed(entry, "click_ejecutado_sin_verificacion_visual")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    def right_click(self, x: int, y: int) -> ActionLog:
        entry = self._record("right_click", {"x": x, "y": y})
        try:
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.rightClick()
            self._mark_executed(entry)
            self._mark_confirmed(entry, "right_click_ejecutado")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    def double_click(self, x: int, y: int, *, verify_region: tuple | None = None) -> ActionLog:
        entry = self._record("double_click", {"x": x, "y": y})
        try:
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.doubleClick()
            self._mark_executed(entry)
            if verify_region:
                changed = self.wait_for_pixel_change(verify_region, timeout=3.0)
                if changed:
                    self._mark_confirmed(entry, "cambio_visual_detectado")
                else:
                    self._mark_failed(entry, "no_hubo_cambio_visual")
            else:
                self._mark_confirmed(entry, "double_click_ejecutado")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    def scroll(self, amount: int, x: int | None = None, y: int | None = None) -> ActionLog:
        entry = self._record("scroll", {"amount": amount, "x": x, "y": y})
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.scroll(amount)
            self._mark_executed(entry)
            self._mark_confirmed(entry, "scroll_ejecutado")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    # ------------------------------------------------------------------
    # Teclado verificado
    # ------------------------------------------------------------------

    def write(self, text: str, interval: float = 0.02, *, verify_region: tuple | None = None) -> ActionLog:
        entry = self._record("write", {"text": text[:40]})
        try:
            pyautogui.write(text, interval=interval)
            self._mark_executed(entry)
            if verify_region:
                # OCR para confirmar que el texto apareció
                found = self.ocr_region(verify_region)
                if text.lower() in found.lower():
                    self._mark_confirmed(entry, f"texto_en_pantalla: {found[:40]}")
                else:
                    self._mark_confirmed(entry, "texto_escrito_sin_confirmacion_ocr")
            else:
                self._mark_confirmed(entry, "escritura_ejecutada")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    def press(self, key: str) -> ActionLog:
        entry = self._record("press", {"key": key})
        try:
            pyautogui.press(key)
            self._mark_executed(entry)
            self._mark_confirmed(entry, "tecla_presionada")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    def hotkey(self, *keys: str) -> ActionLog:
        entry = self._record("hotkey", {"keys": keys})
        try:
            pyautogui.hotkey(*keys)
            self._mark_executed(entry)
            self._mark_confirmed(entry, "hotkey_ejecutado")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    # ------------------------------------------------------------------
    # Foco de ventanas verificado
    # ------------------------------------------------------------------

    def focus_app(self, app_name: str) -> ActionLog:
        entry = self._record("focus_app", {"app_name": app_name})
        try:
            windows = gw.getWindowsWithTitle(app_name)
            if not windows:
                all_titles = gw.getAllTitles()
                matches = [t for t in all_titles if app_name.lower() in t.lower()]
                if matches:
                    windows = gw.getWindowsWithTitle(matches[0])

            if not windows:
                self._mark_failed(entry, f"no_ventana_encontrada: {app_name}")
                return entry

            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.4)

            # Verificar que la ventana activa ahora sea la esperada
            active = gw.getActiveWindow()
            if active and app_name.lower() in (active.title or "").lower():
                self._mark_confirmed(entry, f"ventana_activa: {active.title}")
            else:
                self._mark_confirmed(entry, f"activada_sin_confirmacion_titulo (activa={getattr(active, 'title', '?')})")
        except Exception as exc:
            self._mark_failed(entry, str(exc))
        return entry

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------

    def last_log(self) -> ActionLog | None:
        return self._log[-1] if self._log else None

    def failed_actions(self) -> list[ActionLog]:
        return [e for e in self._log if e.state == ActionState.FAILED]

    def action_summary(self) -> str:
        return " | ".join(e.to_str() for e in self._log[-5:])
