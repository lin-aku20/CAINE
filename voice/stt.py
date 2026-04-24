"""Speech-to-text para CAINE con fallback automático y grabación robusta via sounddevice.

Backend prioritario: SpeechRecognition + Google (vía sounddevice para evitar dependencia de pyaudio).
Fallback: Vosk (requiere modelo descargado en models/vosk).
"""

from __future__ import annotations

from pathlib import Path
import json
import logging
import io
import wave
import numpy as np

from caine.config import VoiceSettings
from voice.interfaces import VoiceResult

logger = logging.getLogger("caine.stt")


class VoskSpeechToText:
    """STT con fallback automático y grabación vía sounddevice."""

    def __init__(self, config: VoiceSettings) -> None:
        self.config = config
        self.model = None
        self._backend: str = "unknown"

    def prepare(self) -> VoiceResult:
        # Intentar primero con SpeechRecognition + sounddevice
        try:
            import speech_recognition as sr  # noqa: F401
            import sounddevice as sd  # noqa: F401
            self._backend = "google"
            logger.info("STT backend: speech_recognition (vía sounddevice)")
            return VoiceResult(True, "STT listo con Google/SoundDevice.")
        except ImportError:
            logger.warning("speech_recognition o sounddevice no disponible, intentando Vosk...")

        # Fallback: Vosk local
        try:
            from vosk import Model
        except ImportError:
            return VoiceResult(False, "Faltan dependencias críticas (speech_recognition o vosk).")

        model_path = Path(self.config.vosk_model_path)
        if not model_path.exists() or not any(model_path.iterdir()):
            return VoiceResult(False, f"No hay modelo Vosk en {model_path} y Google STT falló.")

        try:
            self.model = Model(str(model_path))
            self._backend = "vosk"
            logger.info("STT backend: Vosk local")
            return VoiceResult(True, "Vosk listo para escuchar.")
        except Exception as e:
            return VoiceResult(False, f"Error cargando Vosk: {e}")

    def listen_once(self, duration_seconds: float | None = None) -> VoiceResult:
        if self._backend == "unknown":
            prepared = self.prepare()
            if not prepared.ok:
                return prepared

        if self._backend == "google":
            return self._listen_google(duration_seconds)
        return self._listen_vosk(duration_seconds)

    def _listen_google(self, duration_seconds: float | None) -> VoiceResult:
        try:
            import speech_recognition as sr
            import sounddevice as sd
        except ImportError:
            return VoiceResult(False, "speech_recognition o sounddevice no disponible.")

        duration = float(duration_seconds or self.config.command_capture_seconds)
        fs = self.config.sample_rate # típicamente 16000

        try:
            logger.debug("Grabando %ss con sounddevice...", duration)
            # Grabación síncrona
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            
            # Convertir buffer numpy a WAV en memoria
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(fs)
                wf.writeframes(recording.tobytes())
            
            buffer.seek(0)
            
            # Reconocimiento usando el buffer WAV
            recognizer = sr.Recognizer()
            with sr.AudioFile(buffer) as source:
                audio = recognizer.record(source)
            
            text = recognizer.recognize_google(audio, language="es-MX")
            text = text.strip()
            
            if not text:
                return VoiceResult(False, "Silencio detectado.")
                
            logger.info("Google STT (sd) resultado: %s", text)
            return VoiceResult(True, "Transcripción completada.", text=text)

        except sr.UnknownValueError:
            return VoiceResult(False, "No se entendió el audio.")
        except sr.RequestError as e:
            logger.warning("Error de conexión Google STT: %s", e)
            return VoiceResult(False, f"Error de red: {e}")
        except Exception as e:
            logger.error("Error inesperado en STT (sd): %s", e)
            return VoiceResult(False, str(e))

    def _listen_vosk(self, duration_seconds: float | None) -> VoiceResult:
        if self.model is None:
            prepared = self.prepare()
            if not prepared.ok: return prepared

        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer
        except ImportError:
            return VoiceResult(False, "Vosk o SoundDevice no disponibles.")

        duration = float(duration_seconds or self.config.command_capture_seconds)
        fs = self.config.sample_rate
        
        try:
            audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="int16")
            sd.wait()

            recognizer = KaldiRecognizer(self.model, fs)
            recognizer.AcceptWaveform(audio.tobytes())
            result = json.loads(recognizer.FinalResult())
            text = result.get("text", "").strip()

            if not text:
                return VoiceResult(False, "No se detectó voz clara (Vosk).")
                
            return VoiceResult(True, "Transcripción completada (Vosk).", text=text)
        except Exception as e:
            return VoiceResult(False, str(e))
