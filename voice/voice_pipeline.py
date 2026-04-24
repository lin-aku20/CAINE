"""Pipeline de voz real para CAINE."""

from __future__ import annotations

import threading
import time

from caine.config import VoiceSettings
from voice.interfaces import VoiceResult
from voice.stt import VoskSpeechToText
from voice.tts import Pyttsx3TextToSpeech
from voice.wake_word import OpenWakeWordDetector


class VoicePipeline:
    """Coordina wake word, STT y TTS evitando feedback simple."""

    def __init__(self, config: VoiceSettings) -> None:
        self.config = config
        self.wake_word = OpenWakeWordDetector(config)
        self.stt = VoskSpeechToText(config)
        self.tts = Pyttsx3TextToSpeech(config)
        self._speaking_lock = threading.Lock()
        self._listen_pause_until = 0.0

    def is_enabled(self) -> bool:
        return self.config.enabled

    def prepare(self) -> list[VoiceResult]:
        return [self.wake_word.prepare(), self.stt.prepare(), self.tts.prepare()]

    def listen_for_wake_word(self, stop_event: threading.Event) -> VoiceResult:
        while not stop_event.is_set():
            if self._should_pause_listening():
                time.sleep(0.1)
                continue

            heard = self.stt.listen_once(duration_seconds=self.config.wake_chunk_seconds)
            if heard.ok and self.wake_word.detect_text(heard.text):
                return VoiceResult(True, "Wake word detectada.", text=heard.text)

        return VoiceResult(False, "Escucha detenida.")

    def listen_for_command(self, stop_event: threading.Event) -> VoiceResult:
        if stop_event.is_set():
            return VoiceResult(False, "Escucha detenida.")
        return self.stt.listen_once(duration_seconds=self.config.command_capture_seconds)

    def speak(self, text: str) -> VoiceResult:
        with self._speaking_lock:
            result = self.tts.speak(text)
            self._listen_pause_until = time.monotonic() + self.config.post_speech_cooldown_seconds
            return result

    def _should_pause_listening(self) -> bool:
        return self._speaking_lock.locked() or time.monotonic() < self._listen_pause_until
