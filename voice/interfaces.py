"""Interfaces limpias para la futura capa de voz."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class VoiceResult:
    ok: bool
    message: str
    text: str = ""


class WakeWordDetector(Protocol):
    def prepare(self) -> VoiceResult:
        """Valida que el detector pueda ser usado."""

    def detect_text(self, text: str) -> bool:
        """Detecta la wake word en una transcripcion."""


class SpeechToTextEngine(Protocol):
    def prepare(self) -> VoiceResult:
        """Valida dependencias y recursos requeridos."""

    def listen_once(self, duration_seconds: float | None = None) -> VoiceResult:
        """Escucha una sola frase."""


class TextToSpeechEngine(Protocol):
    def prepare(self) -> VoiceResult:
        """Valida dependencias del motor TTS."""

    def speak(self, text: str) -> VoiceResult:
        """Habla una cadena de texto."""
