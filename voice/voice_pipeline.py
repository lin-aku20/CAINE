"""Pipeline de voz real para CAINE."""

from __future__ import annotations

import threading
import time
import queue

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
        self._tts_queue = queue.Queue()
        self._interrupted = False
        self._current_sentence = []
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()

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
            self._interrupted = False
            result = self.tts.speak(text)
            self._listen_pause_until = time.monotonic() + self.config.post_speech_cooldown_seconds
            return result

    def speak_stream(self, token: str) -> None:
        if self._interrupted:
            return
            
        self._current_sentence.append(token)
        text = "".join(self._current_sentence)
        # Split by logical sentence endings
        if any(p in token for p in ['.', '!', '?', '\n']) or len(text) > 80:
            self._tts_queue.put(text.strip())
            self._current_sentence = []

    def flush_stream(self) -> None:
        if self._current_sentence:
            self._tts_queue.put("".join(self._current_sentence).strip())
            self._current_sentence = []

    def stop(self) -> None:
        self._interrupted = True
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
            except queue.Empty:
                break
        self.tts.stop()

    def _tts_worker(self) -> None:
        while True:
            text = self._tts_queue.get()
            if text and not self._interrupted:
                self.speak(text)
                # Micro-pauses for natural pacing
                if text.endswith(','):
                    time.sleep(0.2)
                elif text.endswith('...'):
                    time.sleep(0.5)
            self._tts_queue.task_done()

    def _should_pause_listening(self) -> bool:
        return self._speaking_lock.locked() or time.monotonic() < self._listen_pause_until
