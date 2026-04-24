"""Motor TTS para integrar Voicebox.sh en CAINE."""

import logging
import requests
import os
import tempfile
import time
import winsound
from caine.config import VoiceSettings
from voice.interfaces import VoiceResult

logger = logging.getLogger("caine.voicebox_tts")

class VoiceboxTextToSpeech:
    """Consuume el API local de Voicebox.sh para generar voz de alta calidad."""

    def __init__(self, config: VoiceSettings, host="http://127.0.0.1:17493") -> None:
        self.config = config
        self.host = host
        self.profile_id = None
        self.engine = "kokoro" # Usamos Kokoro por defecto para voces en español

    def prepare(self) -> VoiceResult:
        """Verifica que Voicebox este corriendo y configura el perfil."""
        try:
            # Intentar encontrar un perfil en español
            resp = requests.get(f"{self.host}/profiles", timeout=3)
            if resp.status_code == 200:
                profiles = resp.json()
                
                # 1. Prioridad máxima: Perfil llamado exactamente "caine"
                for p in profiles:
                    if p.get("name", "").lower() == "caine":
                        self.profile_id = p["id"]
                        self.engine = p.get("default_engine", "kokoro")
                        logger.info(f"Perfil Voicebox oficial detectado: {p['name']} ({self.profile_id})")
                        break
                
                # 2. Segunda prioridad: Perfiles en español
                if not self.profile_id:
                    for p in profiles:
                        if p.get("language") == "es" or "spanish" in p.get("name", "").lower():
                            self.profile_id = p["id"]
                            self.engine = p.get("default_engine", "kokoro")
                            logger.info(f"Perfil Voicebox en español encontrado: {p['name']} ({self.profile_id})")
                            break
                
                if not self.profile_id:
                    return VoiceResult(False, "No hay perfiles compatibles en Voicebox.")
                
                return VoiceResult(True, "Voicebox preparado.")
            return VoiceResult(False, "Voicebox no responde en el puerto 17493.")
        except Exception as e:
            return VoiceResult(False, f"Error conectando a Voicebox: {e}")

    def speak(self, text: str) -> VoiceResult:
        """Genera y reproduce el audio."""
        if not self.profile_id:
            prep = self.prepare()
            if not prep.ok: return prep

        payload = {
            "profile_id": self.profile_id,
            "text": text,
            "language": "es",
            "engine": self.engine,
            "normalize": True
        }

        try:
            # Usamos el endpoint de stream para obtener el audio directamente
            # pero Voicebox a veces requiere esperar si el modelo no esta cargado.
            # Intentamos primero con generate para manejar el estado de carga
            gen_resp = requests.post(f"{self.host}/generate", json=payload, timeout=10)
            if gen_resp.status_code != 200:
                return VoiceResult(False, f"Error en Voicebox: {gen_resp.text}")
            
            gen_id = gen_resp.json()["id"]
            
            # Polling corto para esperar a que este listo (especialmente la primera vez)
            max_attempts = 15
            for _ in range(max_attempts):
                status_resp = requests.get(f"{self.host}/history/{gen_id}", timeout=2)
                status = status_resp.json().get("status")
                if status == "completed":
                    break
                if status == "failed":
                    return VoiceResult(False, "La generacion de voz fallo en Voicebox.")
                time.sleep(1)
            else:
                return VoiceResult(False, "Tiempo de espera agotado para Voicebox.")

            # Descargar el audio
            audio_resp = requests.get(f"{self.host}/audio/{gen_id}", timeout=5)
            if audio_resp.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(audio_resp.content)
                    temp_path = f.name
                
                winsound.PlaySound(temp_path, winsound.SND_FILENAME)
                
                try:
                    os.remove(temp_path)
                except:
                    pass
                return VoiceResult(True, "Voz reproducida.")
            
            return VoiceResult(False, "No se pudo obtener el audio de Voicebox.")

        except Exception as e:
            return VoiceResult(False, f"Excepcion en Voicebox TTS: {e}")
