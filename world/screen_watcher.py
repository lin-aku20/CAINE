"""Observador de pantalla para CAINE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import asyncio
import logging

import cv2
import numpy as np
import pyautogui
import pytesseract

from caine.config import CaineConfig
from caine.screen_awareness import ScreenAwareness


@dataclass(slots=True)
class ScreenObservation:
    timestamp: str
    active_app: str
    window_title: str
    extracted_text: str
    dominant_color_bgr: tuple[int, int, int]
    new_window: bool
    text_changed: bool
    ui_changed: bool
    change_score: float
    screenshot_path: str = ""

    def summary(self) -> str:
        parts = [f"app={self.active_app or 'desconocida'}"]
        if self.window_title:
            parts.append(f"ventana={self.window_title}")
        if self.new_window:
            parts.append("nueva_ventana")
        if self.text_changed:
            parts.append("texto_nuevo")
        if self.ui_changed:
            parts.append(f"cambio_ui={self.change_score:.3f}")
        if self.extracted_text:
            parts.append(f"texto='{self.extracted_text[:120]}'")
        return " | ".join(parts)


class ScreenWatcher:
    """Captura cuadros de pantalla sin inyectarse en apps o juegos."""

    def __init__(
        self,
        config: CaineConfig,
        scan_interval: float = 1.2,
        ocr_every_n_scans: int = 3,
        diff_threshold: float = 0.025,
    ) -> None:
        self.config = config
        self.scan_interval = scan_interval
        self.ocr_every_n_scans = ocr_every_n_scans
        self.diff_threshold = diff_threshold
        self.logger = logging.getLogger("caine.screen_watcher")
        self.awareness = ScreenAwareness(
            screenshots_dir=config.awareness.screenshots_dir,
            capture_screenshots=config.awareness.capture_screenshots,
        )
        pyautogui.FAILSAFE = False
        self._last_small_frame: np.ndarray | None = None
        self._last_window_title = ""
        self._last_text = ""
        self._scan_count = 0

    async def watch(self, callback) -> None:
        while True:
            observation = await asyncio.to_thread(self.capture_observation)
            await callback(observation)
            await asyncio.sleep(self.scan_interval)

    def capture_observation(self) -> ScreenObservation:
        self._scan_count += 1
        screen_context = self.awareness.get_active_context(include_screenshot=False)
        try:
            screenshot = pyautogui.screenshot()
        except Exception as error:
            self.logger.debug("No pude capturar pantalla: %s", error)
            return ScreenObservation(
                timestamp=datetime.now(UTC).isoformat(),
                active_app=screen_context.app_name,
                window_title=screen_context.window_title,
                extracted_text=self._last_text,
                dominant_color_bgr=(0, 0, 0),
                new_window=screen_context.window_title != self._last_window_title,
                text_changed=False,
                ui_changed=False,
                change_score=0.0,
            )
        rgb_frame = np.array(screenshot)
        bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
        small_frame = cv2.resize(bgr_frame, (320, 180), interpolation=cv2.INTER_AREA)

        dominant = self._dominant_color(small_frame)
        change_score = self._frame_change_score(small_frame)
        ui_changed = change_score >= self.diff_threshold
        new_window = screen_context.window_title != self._last_window_title

        should_ocr = new_window or ui_changed or self._scan_count % self.ocr_every_n_scans == 0
        extracted_text = self._extract_text(small_frame) if should_ocr else self._last_text
        text_changed = extracted_text.strip() != self._last_text.strip()

        screenshot_path = ""
        if (new_window or text_changed) and self.config.awareness.capture_screenshots:
            path = self.awareness.capture_silent_screenshot()
            screenshot_path = str(path) if path else ""

        observation = ScreenObservation(
            timestamp=datetime.now(UTC).isoformat(),
            active_app=screen_context.app_name,
            window_title=screen_context.window_title,
            extracted_text=extracted_text.strip(),
            dominant_color_bgr=dominant,
            new_window=new_window,
            text_changed=text_changed,
            ui_changed=ui_changed,
            change_score=change_score,
            screenshot_path=screenshot_path,
        )

        self._last_small_frame = small_frame
        self._last_window_title = screen_context.window_title
        self._last_text = extracted_text.strip()
        return observation

    def _extract_text(self, frame_bgr: np.ndarray) -> str:
        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            text = pytesseract.image_to_string(gray, lang="eng+spa", config="--psm 6")
            return " ".join(text.split())
        except Exception as error:
            self.logger.debug("OCR no disponible o fallo: %s", error)
            return self._last_text

    def _frame_change_score(self, small_frame: np.ndarray) -> float:
        if self._last_small_frame is None:
            return 0.0
        diff = cv2.absdiff(self._last_small_frame, small_frame)
        return float(np.mean(diff)) / 255.0

    def _dominant_color(self, small_frame: np.ndarray) -> tuple[int, int, int]:
        mean_color = small_frame.mean(axis=(0, 1))
        return tuple(int(channel) for channel in mean_color)
