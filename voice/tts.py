"""Placeholder de text-to-speech con pyttsx3."""

from __future__ import annotations

from caine.config import VoiceSettings
from voice.interfaces import VoiceResult


class Pyttsx3TextToSpeech:
    """Capa minima para validar un motor TTS local."""

    def __init__(self, config: VoiceSettings) -> None:
        self.config = config
        self.engine = None

    def prepare(self) -> VoiceResult:
        try:
            import pyttsx3
        except ImportError:
            return VoiceResult(False, "Falta instalar pyttsx3.")

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", self.config.tts_rate)
        return VoiceResult(True, "Motor TTS preparado.")

    def speak(self, text: str) -> VoiceResult:
        if self.engine is None:
            prepared = self.prepare()
            if not prepared.ok:
                return prepared

        self.engine.say(text)
        self.engine.runAndWait()
        return VoiceResult(True, "Audio reproducido.")

    def stop(self) -> None:
        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception:
                pass
