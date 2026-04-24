"""Contexto de pantalla y ventana activa."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psutil


@dataclass(slots=True)
class ScreenContext:
    app_name: str = ""
    window_title: str = ""
    process_name: str = ""
    screenshot_path: str = ""

    def summary(self) -> str:
        parts = []
        if self.app_name:
            parts.append(f"app activa: {self.app_name}")
        if self.window_title:
            parts.append(f"ventana: {self.window_title}")
        if self.process_name:
            parts.append(f"proceso: {self.process_name}")
        return " | ".join(parts)


class ScreenAwareness:
    """Obtiene contexto visual local sin ser intrusivo."""

    def __init__(self, screenshots_dir: Path, capture_screenshots: bool = True) -> None:
        self.screenshots_dir = Path(screenshots_dir)
        self.capture_screenshots = capture_screenshots
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def get_active_context(self, include_screenshot: bool = False) -> ScreenContext:
        context = self._active_window_context()
        if include_screenshot and self.capture_screenshots:
            screenshot_path = self.capture_silent_screenshot()
            context.screenshot_path = str(screenshot_path) if screenshot_path else ""
        return context

    def _active_window_context(self) -> ScreenContext:
        try:
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            process_name = process.name()
            app_name = process_name.replace(".exe", "")
            return ScreenContext(app_name=app_name, window_title=title, process_name=process_name)
        except Exception:
            return ScreenContext()

    MAX_SCREENSHOTS = 10

    def capture_silent_screenshot(self) -> Path | None:
        try:
            import pyautogui
        except ImportError:
            return None

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        target = self.screenshots_dir / f"screen_{timestamp}.png"
        try:
            image = pyautogui.screenshot()
            image.save(target)
            self._purge_old_screenshots()
            return target
        except Exception:
            return None

    def _purge_old_screenshots(self) -> None:
        """Borra las capturas mas antiguas, conservando solo las ultimas MAX_SCREENSHOTS."""
        existing = sorted(self.screenshots_dir.glob("screen_*.png"))
        to_delete = existing[: max(0, len(existing) - self.MAX_SCREENSHOTS)]
        for old in to_delete:
            try:
                old.unlink()
            except Exception:
                pass
