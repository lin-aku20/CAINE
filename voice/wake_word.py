"""Wake word local con soporte para variantes textuales."""

from __future__ import annotations

from pathlib import Path

from caine.config import VoiceSettings
from voice.interfaces import VoiceResult


class OpenWakeWordDetector:
    """Detector pragmatico: usa variantes textuales y valida modelos futuros."""

    def __init__(self, config: VoiceSettings) -> None:
        self.config = config

    def prepare(self) -> VoiceResult:
        try:
            import openwakeword  # noqa: F401
        except ImportError:
            return VoiceResult(False, "Falta instalar openwakeword.")

        model_path = Path(self.config.wakeword_model_path)
        if model_path.exists() and any(model_path.iterdir()):
            return VoiceResult(True, "Modelo de wake word dedicado disponible.")

        return VoiceResult(
            True,
            "OpenWakeWord instalado. Se usara deteccion textual hasta cargar un modelo dedicado.",
        )

    def detect_text(self, text: str) -> bool:
        lowered = text.strip().lower()
        return any(variant in lowered for variant in self.config.wake_variants)
