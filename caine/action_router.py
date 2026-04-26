"""Enrutador de acciones basado en intents para CAINE."""

from __future__ import annotations
import logging
import time
import webbrowser
import urllib.parse

from interaction.system_actions import SystemActionRouter
from caine.human_control import HumanController
from caine.core.action_result import ActionResult
from caine.app_control.discord_vision_agent import DiscordVisionAgent
from caine.app_control.universal_messaging_agent import UniversalMessagingAgent

class ActionRouter:
    """Procesa intenciones estructuradas y ejecuta macros complejas."""
    
    def __init__(self, system_actions: SystemActionRouter, human_operator: HumanController) -> None:
        self.logger = logging.getLogger("caine.action_router")
        self.system_actions = system_actions
        self.human = human_operator
        self.discord = DiscordVisionAgent(human_operator)
        self.universal_msg = UniversalMessagingAgent(human_operator)

    @staticmethod
    def _coerce_action_result(result, fallback_message: str) -> ActionResult:
        if isinstance(result, ActionResult):
            return result
        if result is None:
            return ActionResult(False, fallback_message)
        return ActionResult(True, str(result))

    def _do_handle(self, intent: dict[str, str]):
        action = intent.get("action")
        app = intent.get("app")
        target = intent.get("target")
        content = intent.get("content")

        self.logger.info("[ROUTER] executing %s", action)

        if action == "open_app":
            if app:
                return self.system_actions.open_app(app)
            return "No especificaste qué aplicación abrir."

        if action == "shutdown_pc":
            return self.system_actions.shutdown_pc()

        # --- MULTIMEDIA ---
        if action == "media_pause":
            self.human.press("playpause")
            return "Multimedia pausada."
        if action == "media_play":
            self.human.press("playpause")
            return "Reproduciendo multimedia."
        if action == "media_next":
            self.human.press("nexttrack")
            return "Siguiente pista."
        if action == "media_prev":
            self.human.press("prevtrack")
            return "Pista anterior."

        # --- VOLUMEN ---
        if action == "volume_up":
            for _ in range(5):
                self.human.press("volumeup")
            return "Volumen del sistema incrementado."
        if action == "volume_down":
            for _ in range(5):
                self.human.press("volumedown")
            return "Volumen del sistema reducido."
        if action == "volume_mute":
            self.human.press("volumemute")
            return "Volumen del sistema silenciado/restaurado."

        # --- YOUTUBE ---
        if action == "youtube_search":
            if target:
                query = urllib.parse.quote_plus(target)
                url = f"https://www.youtube.com/results?search_query={query}"
                webbrowser.open(url)
                return f"Buscando '{target}' en YouTube."
            else:
                webbrowser.open("https://www.youtube.com/")
                return "Abriendo YouTube."

        if action == "end_call":
            return self.system_actions.cortar_llamada()

        # Mensajería Universal (Multi-App)
        if action == "send_message":
            if not content:
                return "¿Qué mensaje quieres enviar?"
                
            supported_apps = ["discord", "whatsapp", "telegram", "messenger", "signal"]
            app_lower = app.lower() if app else "discord"
            
            resolved_name = intent.get("resolved_name") or target
            phone = intent.get("phone")
            
            # Si es una de las soportadas, ejecutamos directo
            if app_lower in supported_apps:
                return self.universal_msg.send_message(app_lower, resolved_name, content, phone)
            else:
                # Fallback al agente universal por si el usuario pide otra
                return self.universal_msg.send_message(app_lower, resolved_name, content, phone)

        # Llamadas Universales (Multi-App)
        if action == "hacer_llamada":
            supported_apps = ["discord", "whatsapp", "signal"]
            app_lower = app.lower() if app else "whatsapp"
            
            resolved_name = intent.get("resolved_name") or target
            phone = intent.get("phone")
            
            return self.universal_msg.make_call(app_lower, resolved_name, content, phone)

        # Discord Specific Macros
        if app == "discord":
            if action == "start_call":
                open_result = self._coerce_action_result(
                    self.discord.open_discord(),
                    "No pude abrir Discord."
                )
                if not open_result.success:
                    return open_result

                focus_result = self._coerce_action_result(
                    self.discord.focus_chat(target),
                    "No pude enfocar el chat de Discord."
                )
                if not focus_result.success:
                    return focus_result

                return self.discord.start_call()
                
            if action == "read_messages":
                open_result = self._coerce_action_result(
                    self.discord.open_discord(),
                    "No pude abrir Discord."
                )
                if not open_result.success:
                    return open_result

                if target:
                    focus_result = self._coerce_action_result(
                        self.discord.focus_chat(target),
                        "No pude enfocar el chat de Discord."
                    )
                    if not focus_result.success:
                        return focus_result
                return self.discord.read_last_messages()
                
            if action == "play_audio":
                open_result = self._coerce_action_result(
                    self.discord.open_discord(),
                    "No pude abrir Discord."
                )
                if not open_result.success:
                    return open_result

                if target:
                    focus_result = self._coerce_action_result(
                        self.discord.focus_chat(target),
                        "No pude enfocar el chat de Discord."
                    )
                    if not focus_result.success:
                        return focus_result
                return self.discord.play_last_audio()
                
            if action == "end_call":
                open_result = self._coerce_action_result(
                    self.discord.open_discord(),
                    "No pude abrir Discord."
                )
                if not open_result.success:
                    return open_result
                return self.discord.end_call()

        return "La intención fue analizada pero no tengo una rutina definida para ejecutarla."

    def handle(self, intent: dict[str, str]) -> str:
        try:
            result = self._do_handle(intent)
            if isinstance(result, ActionResult):
                return result.message
            if result is None:
                return "Acción ejecutada."
            return str(result)
        except Exception as e:
            self.logger.error(f"Action failed: {e}")
            return f"Fallo crítico en acción: {e}"
