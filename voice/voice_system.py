"""Sistema de voz para el companion desktop."""

from __future__ import annotations

import asyncio
from io import BytesIO
import logging
from pathlib import Path
import tempfile
import wave
import winsound

import numpy as np
import pyttsx3

from caine.config import CaineConfig
from voice.stt import VoskSpeechToText
from voice.voicebox_tts import VoiceboxTextToSpeech

try:
    from piper import PiperVoice
except ImportError:  # pragma: no cover
    PiperVoice = None

try:
    import win32com.client
except ImportError:  # pragma: no cover
    win32com = None


class CompanionVoiceSystem:
    """TTS con personalidad y microfono local usando Vosk."""

    def __init__(self, config: CaineConfig) -> None:
        self.config = config
        self.enable_microphone = config.desktop.microphone_enabled
        self.logger = logging.getLogger("caine.voice_system")
        self.stt = VoskSpeechToText(config.voice)
        self.sapi_voice = None
        self.engine = None
        self.piper_voice = None
        self.voicebox_tts = VoiceboxTextToSpeech(config.voice)
        self._configure_voice()

    async def speak(self, text: str) -> None:
        await asyncio.to_thread(self._speak_sync, text)

    def _speak_sync(self, text: str) -> None:
        styled = self._style_text(text)

        # Preferencia 1: Voicebox (Calidad Premium)
        if self.voicebox_tts.prepare().ok:
            if self.voicebox_tts.speak(styled).ok:
                return

        # Preferencia 2: Piper (Calidad Alta Local)
        if self.piper_voice is not None:
            self._speak_with_piper(styled)
            return

        if self.sapi_voice is not None:
            # SAPI 5 Pitch and Rate using XML
            # Pitch range is typically -10 to 10
            xml = (
                f"<pitch absmiddle='{self.config.desktop.sapi_pitch}'>"
                f"<rate absspeed='{self.config.desktop.sapi_rate}'>"
                f"{styled}"
                f"</rate></pitch>"
            )
            self.sapi_voice.Speak(xml, 1) # 1 = SVSFIsXML
            return

        assert self.engine is not None
        self.engine.say(styled)
        self.engine.runAndWait()

    async def listen_once(self, timeout: float | None = None) -> str:
        if not self.enable_microphone:
            return ""
        seconds = timeout or self.config.desktop.microphone_phrase_seconds
        result = await asyncio.to_thread(self.stt.listen_once, seconds)
        return result.text if result.ok else ""

    def _configure_voice(self) -> None:
        if self.config.desktop.use_piper_voice and PiperVoice is not None:
            model_path = Path(self.config.desktop.piper_model_path)
            config_path = Path(self.config.desktop.piper_config_path)
            if model_path.exists() and config_path.exists():
                try:
                    self.piper_voice = PiperVoice.load(model_path, config_path)
                    self.logger.info("Voz Piper seleccionada: %s", model_path.name)
                    return
                except Exception as error:
                    self.logger.warning("No pude cargar Piper: %s", error)

        if win32com is not None:
            try:
                self.sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                selected = self._select_sapi_voice()
                if selected:
                    self.logger.info("Voz SAPI seleccionada: %s", selected)
                    return
            except Exception as error:
                self.logger.warning("No pude inicializar SAPI.SpVoice: %s", error)
                self.sapi_voice = None

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", self.config.desktop.voice_rate)
        self.engine.setProperty("volume", 1.0)
        self._select_pyttsx3_voice()

    def _speak_with_piper(self, text: str) -> None:
        assert self.piper_voice is not None
        audio_chunks = list(self.piper_voice.synthesize(text))
        if not audio_chunks:
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            wav_path = temp_file.name

        with wave.open(wav_path, "wb") as wav_file:
            first = audio_chunks[0]
            wav_file.setnchannels(first.sample_channels)
            wav_file.setsampwidth(first.sample_width)
            wav_file.setframerate(first.sample_rate)

            for chunk in audio_chunks:
                audio_float = chunk.audio_float_array
                audio_int16 = np.clip(audio_float * 32767.0, -32768, 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

        winsound.PlaySound(wav_path, winsound.SND_FILENAME)

    def _select_sapi_voice(self) -> str:
        assert self.sapi_voice is not None
        hint = self.config.desktop.voice_name_hint.lower()
        voices = self.sapi_voice.GetVoices()
        
        # 1. Intentar coincidencia con el nombre sugerido (ej: Pablo, David)
        if hint:
            for index in range(voices.Count):
                voice = voices.Item(index)
                desc = voice.GetDescription()
                if hint in desc.lower():
                    self.sapi_voice.Voice = voice
                    return desc

        # 2. Intentar cualquier voz masculina en español (para voz profunda)
        for index in range(voices.Count):
            voice = voices.Item(index)
            desc = voice.GetDescription().lower()
            if ("spanish" in desc or "español" in desc) and ("male" in desc or "hombre" in desc or "pablo" in desc or "david" in desc or "raul" in desc):
                self.sapi_voice.Voice = voice
                return voice.GetDescription()

        # 3. Fallback a cualquier voz en español
        for index in range(voices.Count):
            voice = voices.Item(index)
            desc = voice.GetDescription().lower()
            if "spanish" in desc or "español" in desc:
                self.sapi_voice.Voice = voice
                return voice.GetDescription()

        if voices.Count:
            self.sapi_voice.Voice = voices.Item(0)
            return self.sapi_voice.Voice.GetDescription()

        return ""

    def _select_pyttsx3_voice(self) -> None:
        assert self.engine is not None
        hint = self.config.desktop.voice_name_hint.lower()
        selected_id = None
        for voice in self.engine.getProperty("voices"):
            name = getattr(voice, "name", "").lower()
            voice_id = getattr(voice, "id", "")
            languages = " ".join(str(item) for item in getattr(voice, "languages", []))
            if hint in name or "es-" in languages.lower() or "spanish" in name:
                selected_id = voice_id
                break

        if selected_id:
            self.engine.setProperty("voice", selected_id)

    def _style_text(self, text: str) -> str:
        cleaned = " ".join(text.split())
        if not cleaned:
            return cleaned
        if not cleaned.endswith((".", "!", "?")):
            cleaned += "."
        return cleaned
