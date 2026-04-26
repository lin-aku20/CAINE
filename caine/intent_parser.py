"""Módulo de interpretación semántica — Tool Calling para CAINE.

Convierte órdenes de lenguaje natural a herramientas estructuradas.
Cuando detecta una intención de acción, emite un tool_call en lugar
de dejar que el brain genere texto.

REGLA: CAINE NO SIMULA ACCIONES. Solo confirma DESPUÉS de ejecutar.
"""

from __future__ import annotations
import logging
import re
from caine.memory.contact_manager import ContactManager

logger = logging.getLogger("caine.intent_parser")


# Mapeo de alias → app normalizada
_APP_ALIASES = {
    "discord": "discord",
    "instagram": "instagram", "insta": "instagram",
    "tiktok": "tiktok", "tik tok": "tiktok",
    "facebook": "facebook", "fb": "facebook",
    "github": "github",
    "kick": "kick",
    "curseforge": "curseforge", "curse forge": "curseforge",
    "youtube": "youtube", "yt": "youtube",
    "spotify": "spotify",
    "chrome": "chrome", "navegador": "chrome", "browser": "chrome",
    "whatsapp": "whatsapp",
}

# Apps que soportan llamadas
_CALL_APPS = {"discord", "whatsapp"}

# Apps que soportan mensajes
_MSG_APPS = {"discord", "whatsapp", "instagram", "facebook"}


def _extract_target_after(text: str, trigger: str) -> str:
    """Extrae el target después de un trigger (ej. 'llama a jackstar' → 'jackstar')."""
    idx = text.find(trigger)
    if idx == -1:
        return ""
    after = text[idx + len(trigger):].strip()
    # Cortar en preposiciones comunes
    for stop in [" en ", " por ", " de ", " para ", " usando "]:
        if stop in after:
            after = after.split(stop)[0].strip()
    # Limpiar puntuación final
    after = after.rstrip(".,!?;:")
    return after


def _detect_app(text: str) -> str:
    """Detecta la app mencionada en el texto."""
    lowered = text.lower()
    for alias, normalized in _APP_ALIASES.items():
        if alias in lowered:
            return normalized
    return ""


class IntentParser:
    """Extrae intenciones estructuradas (tool calls) a partir de texto natural."""

    # Definición de herramientas disponibles
    TOOLS = [
        {
            "name": "iniciar_llamada_discord",
            "description": "Inicia una llamada real en Discord hacia un contacto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contacto": {"type": "string", "description": "Usuario de Discord a llamar"}
                },
                "required": ["contacto"]
            }
        },
        {
            "name": "enviar_mensaje_discord",
            "description": "Envía un mensaje real en Discord a un contacto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contacto": {"type": "string", "description": "Usuario de Discord"},
                    "mensaje": {"type": "string", "description": "Contenido del mensaje"}
                },
                "required": ["contacto", "mensaje"]
            }
        },
        {
            "name": "abrir_aplicacion",
            "description": "Abre una aplicación. Si no existe localmente, abre versión web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "Nombre de la aplicación"}
                },
                "required": ["app"]
            }
        },
        {
            "name": "human_action",
            "description": "Ejecuta una acción de mouse o teclado como segundo operador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "accion": {"type": "string", "enum": ["mover_mouse", "click_izquierdo", "click_derecho", "escribir", "presionar_tecla"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "texto": {"type": "string"},
                    "tecla": {"type": "string"}
                },
                "required": ["accion"]
            }
        },
    ]

    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.intent_parser")
        self.contact_mgr = ContactManager()

    def parse_intent(self, text: str) -> dict[str, str] | None:
        """Parsea texto a tool_call estructurado.

        Returns:
            dict con keys: app, action, target, content, tool_call
            None si no es un intent de acción (es conversación normal)
        """
        lowered = text.strip().lower()

        intent = {
            "app": "",
            "action": "unknown",
            "target": "",
            "content": "",
            "tool_call": "",
        }

        # --- Detectar app mencionada ---
        intent["app"] = _detect_app(lowered)

        # --- YOUTUBE EXCLUSIVO ---
        # Si el texto menciona youtube de cualquier forma, forzar búsqueda
        is_yt = "youtube" in lowered or lowered.endswith(" yt") or " yt " in lowered or "ver video" in lowered or "ver videos" in lowered or "busca un video" in lowered
        if is_yt:
            intent["action"] = "youtube_search"
            intent["app"] = "youtube"
            
            # Filtro agresivo de stopwords para aislar el término real
            stopwords = [
                'busca', 'buscar', 'buscame', 'en', 'youtube', 'yt', 'reproduce', 
                'quiero', 'ver', 'video', 'videos', 'de', 'a', 'pon', 'ponme', 
                'un', 'el', 'la', 'los', 'las', 'sobre', 'algun', 'algo', 'musica',
                'escuchar', 'poner'
            ]
            words = lowered.split()
            target_words = [w for w in words if w not in stopwords]
            intent["target"] = " ".join(target_words)
            
            # Al forzar esta ruta, no seguimos evaluando otras acciones
            # así evitamos que 'reproduce en youtube' active 'media_play'.
            # A menos que el target esté vacío, en cuyo caso solo abre youtube.
            
            self.logger.info(
                "[TOOL_CALL] YOUTUBE OVERRIDE -> action=%s target=%s",
                intent["action"], intent["target"]
            )
            return intent

        # --- LLAMADAS ---
        call_triggers = ["llama a ", "llamar a ", "inicia llamada con ", "inicia una llamada con ",
                         "hazle una llamada a ", "call "]
        for trigger in call_triggers:
            if trigger in lowered:
                intent["action"] = "start_call"
                intent["target"] = _extract_target_after(lowered, trigger)
                intent["tool_call"] = "iniciar_llamada_discord"
                # Si no mencionó app pero pidió llamar, asumir Discord
                if not intent["app"]:
                    intent["app"] = "discord"
                break

        # --- COLGAR ---
        if intent["action"] == "unknown":
            if any(t in lowered for t in ["corta llamada", "colgar", "corta la llamada", "cuelga", "termina la llamada"]):
                intent["action"] = "end_call"
                intent["app"] = intent["app"] or "discord"

        # --- LLAMADAS ---
        if intent["action"] == "unknown":
            call_triggers = ["llamada", "llama ", "llamar "]
            found_trigger = ""
            for trigger in call_triggers:
                if trigger in lowered or lowered.startswith(trigger.strip()):
                    found_trigger = trigger
                    break
                    
            if found_trigger:
                intent["action"] = "hacer_llamada"
                intent["tool_call"] = "hacer_llamada"
                
                # Detectar app objetivo
                supported_apps = ["discord", "whatsapp", "signal"]
                for supp_app in supported_apps:
                    if f"en {supp_app}" in lowered or f"por {supp_app}" in lowered:
                        intent["app"] = supp_app
                        break
                        
                target_marker = ""
                if " a " in lowered:
                    target_marker = " a "
                    
                if target_marker:
                    parts_marker = lowered.split(target_marker, 1)
                    after_marker = parts_marker[1].strip()
                    
                    parts = after_marker.split(" ", 1)
                    if len(parts) >= 1:
                        intent["target"] = parts[0].strip().rstrip(".,!?")
                        
                    if len(parts) == 2:
                        intent["content"] = parts[1].strip().rstrip(".,!?")
                        
                if not intent.get("app"):
                    intent["app"] = "whatsapp" # Default for calls
                    
                # Resolver alias usando ContactManager
                if intent.get("target") and intent.get("app"):
                    contact_data = self.contact_mgr.resolve_alias(intent["app"], intent["target"])
                    intent["alias"] = intent["target"]
                    intent["resolved_name"] = contact_data.get("resolved_name")
                    intent["phone"] = contact_data.get("phone")

        # --- MENSAJES ---
        if intent["action"] == "unknown":
            msg_triggers = ["mensaje", "decile", "dile", "manda", "envía", "envia", "escribe", "escribile", "enviá"]
            found_trigger = ""
            for trigger in msg_triggers:
                if trigger in lowered:
                    found_trigger = trigger
                    break
                    
            if found_trigger:
                intent["action"] = "send_message"
                intent["tool_call"] = "enviar_mensaje"
                
                # Detectar app objetivo
                supported_apps = ["discord", "whatsapp", "telegram", "messenger", "signal"]
                for supp_app in supported_apps:
                    if f"en {supp_app}" in lowered or f"por {supp_app}" in lowered:
                        intent["app"] = supp_app
                        break
                        
                target_marker = ""
                if " a " in lowered:
                    target_marker = " a "
                elif " para " in lowered:
                    target_marker = " para "
                    
                if target_marker:
                    parts_marker = lowered.split(target_marker, 1)
                    before_marker = parts_marker[0].strip()
                    after_marker = parts_marker[1].strip()
                    
                    parts = after_marker.split(" ", 1)
                    if len(parts) >= 1:
                        intent["target"] = parts[0].strip().rstrip(".,!?")
                        
                    if len(parts) == 2:
                        # Caso 1: "mandale mensaje a <usuario> <mensaje>"
                        content_raw = parts[1].strip()
                        for prefix in ["que le dices ", "que le diga ", "que diga ", "diciendo ", "diciendole "]:
                            if content_raw.startswith(prefix):
                                content_raw = content_raw[len(prefix):].strip()
                                break
                        intent["content"] = content_raw.rstrip(".,!?")
                    else:
                        # Caso 2: "enviá <mensaje> a <usuario>" (sin texto después del usuario)
                        # El mensaje debe estar en before_marker
                        content_before = before_marker.replace(found_trigger, "", 1).strip()
                        # Quitar menciones a la app de content_before
                        for supp_app in supported_apps:
                            for drop in [f"un mensaje en {supp_app}", f"mensaje en {supp_app}", f"en {supp_app}", f"por {supp_app}"]:
                                if drop in content_before:
                                    content_before = content_before.replace(drop, "", 1).strip()
                        
                        for drop in ["un mensaje", "mensaje"]:
                            if drop in content_before:
                                content_before = content_before.replace(drop, "", 1).strip()
                        if content_before:
                            intent["content"] = content_before.rstrip(".,!?")
                            
                if not intent.get("app"):
                    intent["app"] = "discord"

                # Resolver alias usando ContactManager
                if intent.get("target") and intent.get("app"):
                    contact_data = self.contact_mgr.resolve_alias(intent["app"], intent["target"])
                    intent["alias"] = intent["target"] # Preservamos el alias original
                    intent["resolved_name"] = contact_data.get("resolved_name")
                    intent["phone"] = contact_data.get("phone")

        # --- ABRIR APP ---
        if intent["action"] == "unknown":
            open_triggers = ["abre ", "abrir ", "abrí ", "abrirme ", "abre el ", "abre la ", "open "]
            for trigger in open_triggers:
                if lowered.startswith(trigger) or f" {trigger}" in lowered:
                    intent["action"] = "open_app"
                    intent["tool_call"] = "abrir_aplicacion"
                    app_name = _extract_target_after(lowered, trigger)
                    # Normalizar nombre de app
                    detected = _detect_app(app_name)
                    intent["app"] = detected or app_name
                    break

        # --- CONTROL MULTIMEDIA ---
        if intent["action"] == "unknown":
            # Exclusión: Si menciona favorita, canción, nombre específico o spotify, NO hacer play/pause ciego. Ir al LLM.
            if not any(k in lowered for k in ["favorit", "spotify", "cancion", "canción", "cambia la"]):
                if any(t in lowered for t in ["pausa", "pausar", "para la musica", "para la música"]):
                    intent["action"] = "media_pause"
                elif any(t in lowered for t in ["reproduce", "reanuda", "play", "ponle play", "dale play", "pon musica"]):
                    intent["action"] = "media_play"
                elif any(t in lowered for t in ["siguiente", "pasa la", "next"]):
                    intent["action"] = "media_next"
                elif any(t in lowered for t in ["anterior", "retrocede", "prev"]):
                    intent["action"] = "media_prev"

        # --- CONTROL DE VOLUMEN ---
        if intent["action"] == "unknown":
            if any(t in lowered for t in ["sube el volumen", "mas volumen", "más volumen", "subile"]):
                intent["action"] = "volume_up"
            elif any(t in lowered for t in ["baja el volumen", "menos volumen", "bajale"]):
                intent["action"] = "volume_down"
            elif any(t in lowered for t in ["silencia", "mutea", "silencio", "mute", "quita el sonido"]):
                intent["action"] = "volume_mute"



        # --- APAGAR ---
        if intent["action"] == "unknown":
            if "apaga" in lowered and any(t in lowered for t in ["pc", "computadora", "equipo", "ordenador"]):
                intent["action"] = "shutdown_pc"

        # --- LEER MENSAJES ---
        if intent["action"] == "unknown":
            if any(t in lowered for t in ["lee los mensajes", "lee el chat", "lee los ultimos mensajes", "leer mensajes"]):
                intent["action"] = "read_messages"
                intent["app"] = intent["app"] or "discord"

        # --- REPRODUCIR AUDIO (DISCORD/GENERAL) ---
        if intent["action"] == "unknown":
            if any(t in lowered for t in ["reproduce el audio", "escucha el audio", "reproduce audio", "pon el audio"]):
                intent["action"] = "play_audio"
                intent["app"] = intent["app"] or "discord"

        # --- EMERGENCY STOP ---
        if intent["action"] == "unknown":
            if any(t in lowered for t in ["detente", "para caine", "abortar", "stop"]):
                intent["action"] = "emergency_stop"

        # --- Si no reconocimos nada → es conversación normal ---
        if intent["action"] == "unknown" and intent["app"] == "":
            return None

        self.logger.info(
            "[TOOL_CALL] tool=%s app=%s action=%s target=%s",
            intent["tool_call"] or "none", intent["app"], intent["action"], intent["target"]
        )
        return intent
