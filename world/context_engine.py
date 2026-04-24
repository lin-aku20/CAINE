"""Observacion continua del mundo local de CAINE."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import ctypes
import logging
import time

import psutil
import pytesseract

from caine.config import CaineConfig
from caine.screen_awareness import ScreenAwareness
from world.desktop_awareness import DesktopAwareness


@dataclass(slots=True)
class WorldState:
    active_app: str = ""
    window_title: str = ""
    user_activity: str = "active"
    focus_duration: float = 0.0
    detected_context: str = ""
    last_event: str = ""
    running_apps: list[str] = field(default_factory=list)
    ocr_text: str = ""
    screenshot_path: str = ""
    changed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class ContextEngine:
    """Mantiene un estado continuo de lo que ocurre en la PC."""

    def __init__(self, config: CaineConfig) -> None:
        self.config = config
        self.awareness = ScreenAwareness(
            screenshots_dir=config.awareness.screenshots_dir,
            capture_screenshots=config.awareness.capture_screenshots,
        )
        self.desktop = DesktopAwareness()
        self.logger = logging.getLogger("caine.context_engine")
        self.world_state = WorldState()
        self._last_app = ""
        self._last_title = ""
        self._focus_started_at = time.monotonic()
        self._last_snapshot_at = 0.0
        self._last_ocr_at = 0.0
        self._known_running_apps: set[str] = set()

    def sample(self) -> tuple[WorldState, list[tuple[str, dict[str, object]]]]:
        desktop_ctx = self.desktop.get_context()
        now_mono = time.monotonic()
        events: list[tuple[str, dict[str, object]]] = []

        active_app = desktop_ctx.active_app_exe or "escritorio"
        title = desktop_ctx.active_window_title or "Sin titulo"
        changed = active_app != self._last_app or title != self._last_title

        if changed:
            previous = self._last_app
            previous_focus_duration = max(0.0, now_mono - self._focus_started_at)
            self._focus_started_at = now_mono
            if previous:
                events.append(("app_closed", {"app": previous, "focus_duration": previous_focus_duration}))
            if active_app:
                events.append(("app_opened", {"app": active_app, "title": title}))
                events.append(
                    (
                        "user_focus_change",
                        {"from": previous, "to": active_app, "title": title, "previous_focus_duration": previous_focus_duration},
                    )
                )
            self._last_app = active_app
            self._last_title = title

        focus_duration = max(0.0, now_mono - self._focus_started_at)
        idle_seconds = self._seconds_since_last_input()
        user_activity = "idle" if idle_seconds >= self.config.world.inactivity_seconds else "active"
        if user_activity == "idle" and self.world_state.user_activity != "idle":
            events.append(("long_inactivity", {"idle_seconds": idle_seconds, "active_app": active_app}))

        running_apps = self._running_apps() if self.config.world.detect_running_apps else []
        detected_context = self._detect_context(active_app, title, running_apps)
        if "minecraft" in detected_context.lower():
            events.append(("game_detected", {"game": active_app or "minecraft", "title": title}))
        if focus_duration >= self.config.world.repeated_behavior_seconds:
            events.append(("repeated_behavior", {"app": active_app, "focus_duration": focus_duration}))

        screenshot_path = ""
        if self.config.awareness.capture_screenshots and now_mono - self._last_snapshot_at >= self.config.world.snapshot_interval_seconds:
            path = self.awareness.capture_silent_screenshot()
            screenshot_path = str(path) if path else ""
            self._last_snapshot_at = now_mono

        ocr_text = ""
        if screenshot_path and now_mono - self._last_ocr_at >= self.config.world.ocr_interval_seconds:
            ocr_text = self._read_ocr(Path(screenshot_path))
            self._last_ocr_at = now_mono

        state = WorldState(
            active_app=active_app,
            window_title=title,
            user_activity=user_activity,
            focus_duration=focus_duration,
            detected_context=detected_context,
            last_event=events[-1][0] if events else "",
            running_apps=running_apps,
            ocr_text=ocr_text,
            screenshot_path=screenshot_path,
            changed=changed,
        )
        self.world_state = state
        self._emit_running_app_events(running_apps, events)
        return state, events

    def _running_apps(self) -> list[str]:
        apps = sorted(
            {
                proc.info["name"].replace(".exe", "")
                for proc in psutil.process_iter(["name"])
                if proc.info.get("name")
            }
        )
        return apps

    def _emit_running_app_events(
        self,
        running_apps: list[str],
        events: list[tuple[str, dict[str, object]]],
    ) -> None:
        current = set(running_apps)
        if not self._known_running_apps:
            self._known_running_apps = current
            return
        opened = current - self._known_running_apps
        closed = self._known_running_apps - current
        for app in sorted(opened):
            events.append(("app_opened", {"app": app, "source": "process_scan"}))
        for app in sorted(closed):
            events.append(("app_closed", {"app": app, "source": "process_scan"}))
        self._known_running_apps = current

    def _detect_context(self, active_app: str, title: str, running_apps: list[str]) -> str:
        lowered = f"{active_app} {title}".lower()
        if any(token in lowered for token in self.config.desktop.game_keywords):
            return f"juego:{active_app or title}"
        if "youtube" in lowered:
            return "video"
        if "spotify" in lowered:
            return "musica"
        if "discord" in lowered:
            return "chat"
        if active_app and active_app.lower() in {app.lower() for app in running_apps}:
            return active_app
        return title or active_app or "escritorio"

    def _read_ocr(self, image_path: Path) -> str:
        try:
            from PIL import Image

            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang="eng+spa", config="--psm 6")
            return " ".join(text.split())[:500]
        except Exception as error:
            self.logger.debug("OCR de contexto fallo: %s", error)
            return ""

    def _seconds_since_last_input(self) -> int:
        try:
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
            return int(millis / 1000)
        except Exception:
            return 0
