import os
import time
import subprocess
import threading
from typing import Optional

class VoiceAuthority:
    def __init__(self, ui_controller=None):
        """
        Controlador central de voz de CAINE.
        Soporta APIs de alta calidad (ElevenLabs/OpenAI) o fallbacks como edge-tts/pyttsx3.
        ui_controller: Referencia a la clase CaineDesktopUI para animar el orbe durante la reproducción.
        """
        self.ui_controller = ui_controller
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "") # o config
        self.voice_id = "Adam" # Voz genérica tipo Jarvis
        self._is_speaking = False

    def speak(self, text: str):
        """Método público para iniciar la reproducción de voz."""
        if not text:
            return
            
        print(f"[VOZ] CAINE: {text}")
        
        # Sincronización con la UI
        if self.ui_controller:
            self.ui_controller.log(f"> {text}")
            self.ui_controller.set_speaking(True)
        
        self._is_speaking = True
        
        try:
            if self.api_key:
                self._speak_elevenlabs(text)
            else:
                # Fallback gratuito: Edge-TTS o PyTTSX3
                self._speak_fallback(text)
        except Exception as e:
            print(f"[VOZ] Error en el motor TTS: {e}")
            self._speak_pyttsx3(text) # Fallback último recurso
        finally:
            self._is_speaking = False
            if self.ui_controller:
                self.ui_controller.set_speaking(False)

    def _play_mp3_native(self, file_path: str):
        """Reproduce MP3 nativamente en Windows usando la API Multimedia (winmm.dll)."""
        import ctypes
        import time
        
        # Generar un alias único para no chocar con reproducciones simultáneas
        alias = "caine_voice"
        winmm = ctypes.windll.winmm
        
        # Cerrar el alias si estaba abierto previamente
        winmm.mciSendStringW(f"close {alias}", None, 0, None)
        
        # Abrir el archivo
        res_open = winmm.mciSendStringW(f"open \"{file_path}\" type mpegvideo alias {alias}", None, 0, None)
        if res_open != 0:
            print(f"[VOZ] Error nativo mciSendString (Open): {res_open}")
            return
            
        # Obtener duración (en ms) para poder esperar
        length_buffer = ctypes.create_unicode_buffer(256)
        winmm.mciSendStringW(f"status {alias} length", length_buffer, 256, None)
        
        try:
            length_ms = int(length_buffer.value)
        except ValueError:
            length_ms = 2000 # fallback si falla el parseo

        # Reproducir
        winmm.mciSendStringW(f"play {alias}", None, 0, None)
        
        # Esperar a que termine para poder apagar el orbe visual sincronizadamente
        time.sleep(length_ms / 1000.0)
        
        # Limpiar
        winmm.mciSendStringW(f"close {alias}", None, 0, None)

    def _speak_elevenlabs(self, text: str):
        """Integración con ElevenLabs API."""
        import requests
        import tempfile
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8
            }
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            temp_path = os.path.join(tempfile.gettempdir(), "caine_voice.mp3")
            with open(temp_path, "wb") as f:
                f.write(response.content)
            
            # Reproducir nativamente
            self._play_mp3_native(temp_path)
        else:
            raise Exception(f"ElevenLabs HTTP {response.status_code}")

    def _speak_fallback(self, text: str):
        """Usa edge-tts como fallback (voces neurales gratuitas de Microsoft)."""
        import tempfile
        import asyncio
        temp_path = os.path.join(tempfile.gettempdir(), "caine_voice.mp3")
        voice = "es-MX-JorgeNeural"
        
        try:
            # edge-tts es una librería async — ejecutar en un nuevo event loop
            async def _generate():
                import edge_tts
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(temp_path)
            
            # Crear un nuevo event loop aislado para este hilo
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_generate())
            loop.close()
            
            # Reproducir nativamente
            if os.name == 'nt':
                self._play_mp3_native(temp_path)
            else:
                subprocess.run(['play', temp_path])
        except ImportError:
            # edge-tts no instalado, fallback a cmd
            try:
                subprocess.run(
                    ["edge-tts", "--voice", voice, "--text", text, "--write-media", temp_path],
                    check=True, capture_output=True
                )
                self._play_mp3_native(temp_path)
            except Exception as e2:
                print(f"[VOZ] edge-tts cmd falló: {e2}")
                self._speak_pyttsx3(text)
        except Exception as e:
            print(f"[VOZ] edge-tts falló: {e}")
            self._speak_pyttsx3(text)

    def _speak_pyttsx3(self, text: str):
        """Usa SAPI nativo en un proceso aislado para evitar conflictos de event loop."""
        try:
            # Correr pyttsx3 en un proceso separado para evitar 'run loop already started'
            script = (
                f"import pyttsx3; e=pyttsx3.init(); "
                f"e.say({repr(text)}); e.runAndWait()"
            )
            subprocess.Popen(
                ["python", "-c", script],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        except Exception as e:
            print(f"[VOZ] pyttsx3 falló: {e}")

    def speak_async(self, text: str):
        """Lanza la voz en un hilo separado para no bloquear la interfaz principal."""
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
        return t
