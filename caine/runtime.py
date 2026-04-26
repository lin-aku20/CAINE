"""Runtime persistente de CAINE."""

from __future__ import annotations

from typing import Any, Generator
import logging
import threading
import time

from interaction.system_actions import SystemActionRouter
from brain.caine_brain import CaineBrain
from caine.config import CaineConfig
from caine.diagnostics import DiagnosticsManager
from caine.intent_router import IntentRouter
from caine.intent_parser import IntentParser
from caine.action_router import ActionRouter
from caine.overlay import CaineOverlay
from caine.screen_awareness import ScreenAwareness
from caine.state import CaineStatus, StateController
from caine.web_project_builder import WebProjectBuilder
from interaction.app_launcher import AppLauncher
from interaction.keyboard_controller import KeyboardController
from interaction.mouse_controller import MouseController
from memory.long_term_memory import LongTermMemoryStore
from minecraft.assistant import MinecraftAssistant
from voice.voice_pipeline import VoicePipeline


class CaineRuntime:
    """Coordina voz, cerebro, memoria, pantalla y seguridad."""

    def __init__(
        self,
        config: CaineConfig,
        brain: CaineBrain,
        actions: SystemActionRouter,
        memory_store: LongTermMemoryStore,
        voice: VoicePipeline,
    ) -> None:
        self.config = config
        self.brain = brain
        self.actions = actions
        self.memory_store = memory_store
        self.voice = voice
        self.intent_router = IntentRouter()
        self.intent_parser = IntentParser()
        self.state = StateController()
        self.awareness = ScreenAwareness(
            screenshots_dir=config.awareness.screenshots_dir,
            capture_screenshots=config.awareness.capture_screenshots,
        )
        self.overlay = CaineOverlay(
            title=config.overlay.title,
            geometry=config.overlay.geometry,
            always_on_top=config.overlay.always_on_top,
        )
        self.minecraft = MinecraftAssistant()
        self.web_builder = WebProjectBuilder(config.actions.workspace_root)
        self.app_launcher = AppLauncher(self.actions, self.memory_store)
        self.keyboard = KeyboardController(config.actions, config.interaction)
        self.mouse = MouseController(config.actions, config.interaction)
        self.action_router = ActionRouter(self.actions, self.actions.human)
        self.diagnostics = DiagnosticsManager(config.diagnostics.report_file)
        self.logger = logging.getLogger("caine.runtime")
        
        # Conectar el ejecutor de herramientas nativas del LLM al action_router
        self.brain.tool_executor = self._execute_tool_call
        
        self.stop_event = threading.Event()
        self.pending_task_text: str | None = None
        self._presence_thread = None

    def start_background_features(self, interactive_session: bool = True) -> None:
        if interactive_session and self.config.overlay.enabled:
            self.overlay.start()
            self.state.subscribe(self.overlay.update)

        brain_ok = self.brain.connection_test()
        diagnostics = self.diagnostics.run_startup_checks(brain_ok, self.voice, self.awareness)
        detail = "; ".join(f"{item.name}:{'ok' if item.ok else 'warn'}" for item in diagnostics)
        self.state.set(CaineStatus.SLEEP, f"Chequeo inicial completado. {detail}")

        # Iniciar Presence Commentary Engine
        self._presence_thread = threading.Thread(target=self._presence_loop, daemon=True)
        self._presence_thread.start()

    def _execute_tool_call(self, accion: str, destino: str) -> str:
        """Callback invocado por CaineBrain cuando el modelo decide usar una herramienta nativa."""
        self.logger.info("Ejecutando herramienta LLM nativa: %s -> %s", accion, destino)
        self.state.set(CaineStatus.ACTING, f"Ejecutando (LLM): {accion}")
        
        # Mapear la acción JSON al formato del intent_parser/action_router
        action_map = {
            "llamar": "start_call",
            "terminar_llamada": "end_call",
            "enviar_mensaje": "send_message",
            "abrir_app": "open_app",
            "reproducir": "media_play",
            "pausar": "media_pause",
            "volumen_subir": "volume_up",
            "volumen_bajar": "volume_down",
            "volumen_silenciar": "volume_mute",
            "buscar_youtube": "youtube_search",
        }
        
        mapped_action = action_map.get(accion, accion)
        
        # Construir el intent simulado
        intent = {
            "action": mapped_action,
            "target": destino,
            "app": "discord" if accion in ["llamar", "terminar_llamada", "enviar_mensaje"] else "",
            "content": "",
            "tool_call": "control_sistema"
        }
        
        # Ejecutar usando el router de acciones existente
        try:
            result = self.action_router.handle(intent)
            # Registrar el estado real (CONFIRMED vs fallido) en el log
            last = getattr(self.action_router, '_last_action_log', None)
            if last:
                self.logger.info("[ACTION_RESULT] %s", last)
            return str(result) if result else "Acción completada silenciosamente."
        except Exception as e:
            self.logger.error("Error ejecutando tool call nativo: %s", e)
            return f"Error ejecutando la acción: {e}"

    def handle_text(self, user_text: str) -> Any:
        # 1. Intentar el nuevo sistema JARVIS (Parser -> Router)
        parsed_intent = self.intent_parser.parse_intent(user_text)
        if parsed_intent:
            self.state.set(CaineStatus.ACTING, f"Ejecutando macro: {parsed_intent['action']}")
            result = self.action_router.handle(parsed_intent)
            self.memory_store.maybe_store_fact(user_text=user_text, assistant_text=result, intent="macro_accion")
            return result

        # 2. Flujo clásico de comandos y conversación
        screen_context = self.awareness.get_active_context(include_screenshot=False)
        intent = self.intent_router.classify(user_text, active_app=screen_context.process_name)

        self.memory_store.capture_user_preference(user_text)

        if intent.category == "comando_interno":
            self.memory_store.record_command_usage(intent.command_text or "/interno")
            return self._handle_internal_command(intent.command_text)

        if intent.category == "desarrollo_web":
            self.pending_task_text = user_text
            self.state.set(CaineStatus.THINKING, "Preparando una web local.")
            preview = self._preview_web_task(user_text)
            self.memory_store.maybe_store_fact(user_text=user_text, assistant_text=preview, intent=intent.category)
            return preview

        if intent.category == "continuar_tarea":
            if self.pending_task_text and self._looks_like_web_request(self.pending_task_text):
                self.state.set(CaineStatus.ACTING, "Construyendo web local.")
                result = self.web_builder.build_from_request(self.pending_task_text)
                self.pending_task_text = None
                reply = (
                    f"Perfecto. Ya movi la tramoya y deje la web lista en {result.folder}. "
                    f"Abre {result.folder / 'index.html'} para verla."
                )
                self.memory_store.maybe_store_fact(user_text=user_text, assistant_text=reply, intent="desarrollo_web")
                return reply
            return "No tengo una tarea concreta pendiente para ejecutar. Pideme algo especifico y lo monto."

        if intent.category == "accion_sistema":
            self.state.set(CaineStatus.ACTING, f"Ejecutando accion: {user_text}")
            normalized_command = intent.command_text.removeprefix("/accion ").strip()
            self.memory_store.record_command_usage(normalized_command)
            return self.actions.handle_text_command(normalized_command)

        if intent.category == "openjarvis_research":
            self.state.set(CaineStatus.THINKING, f"Investigando: {intent.command_text[:60]}")
            try:
                from interaction.openjarvis_skills import ask_jarvis, is_ready
                if is_ready():
                    research_query = f"Investiga en profundidad sobre: {intent.command_text}. Usa tus herramientas de busqueda si estan disponibles. Responde como CAINE."
                    result = ask_jarvis(research_query)
                    if result:
                        return self.brain._cleanup_message(result)
            except Exception:
                pass
            # Fallback: send to brain directly
            return self.brain.send_message(f"Investiga en profundidad sobre: {intent.command_text}")

        if intent.category == "openjarvis_digest":
            self.state.set(CaineStatus.THINKING, "Preparando el resumen del circo matutino...")
            try:
                from interaction.openjarvis_skills import ask_jarvis, is_ready
                if is_ready():
                    result = ask_jarvis("Hazme un resumen de lo mas importante del dia de hoy: noticias relevantes, estado del sistema y cualquier cosa que deba saber. Presentalo como CAINE, con estilo teatral.")
                    if result:
                        return self.brain._cleanup_message(result)
            except Exception:
                pass
            return self.brain.send_message("Hazme un resumen del dia con todo lo que deberia saber.")

        if intent.category == "memoria":
            self.memory_store.maybe_store_fact(user_text=user_text, assistant_text="Recuerdo registrado.", intent=intent.category)
            self.state.set(CaineStatus.THINKING, "Guardando un recuerdo local.")
            return "Archivado en la memoria del circo, estimado invitado."

        extra_context = self._build_extra_context(screen_context.summary(), user_text)
        self.state.set(CaineStatus.THINKING, f"Procesando {intent.category}.")
        return self.brain.send_message_stream(user_text, extra_context=extra_context)

    def run_voice_loop(self) -> None:
        if not self.voice.is_enabled():
            self.logger.info("Modo voz desactivado en configuracion.")
            return

        while not self.stop_event.is_set():
            # Si no esta en modo "siempre escuchando", esperar wake word
            if not self.config.desktop.always_listen_microphone:
                self.state.set(CaineStatus.LISTENING, "Esperando la wake word.")
                wake = self.voice.listen_for_wake_word(self.stop_event)
                if not wake.ok:
                    time.sleep(0.2)
                    continue
                self.state.set(CaineStatus.LISTENING, "Wake word detectada. Escuchando comando.")
            else:
                self.state.set(CaineStatus.LISTENING, "Escuchando activamente (Modo Continuo)...")

            heard = self.voice.listen_for_command(self.stop_event)
            if not heard.ok or not heard.text.strip():
                if not self.config.desktop.always_listen_microphone:
                    self.logger.debug("No se escucho comando claro.")
                continue

            # Interrupción Humana
            self.voice.stop()
            self.state.set("LISTENING", "Usuario interrumpió.")

            # Reacción Rápida (Reflex)
            quick_reaction = self.brain.quick_reaction()
            self.state.set("SPEAKING", quick_reaction)
            self.voice.speak(quick_reaction)

            # Procesar el comando escuchado
            reply = self.handle_text(heard.text)
            
            # Si es string (macro, app_launcher, interno)
            if isinstance(reply, str):
                self.state.set("SPEAKING", reply[:80])
                self.voice.speak(reply)
            else:
                # Si es generador (LLM Streaming)
                self.state.set("SPEAKING", "Respondiendo...")
                for token in reply:
                    self.voice.speak_stream(token)
                self.voice.flush_stream()
            
            if not self.config.desktop.always_listen_microphone:
                self.state.set("WAIT_FOR_HUMAN", "Listo para el siguiente acto.")
            else:
                time.sleep(0.5)

    def _presence_loop(self) -> None:
        """Presence Commentary Engine"""
        while not self.stop_event.is_set():
            time.sleep(120)
            if not self.voice._speaking_lock.locked() and not self.stop_event.is_set():
                screen_context = self.awareness.get_active_context(include_screenshot=False)
                if "Code" in screen_context.process_name or "Discord" in screen_context.process_name:
                    try:
                        self.voice.speak("Sigo aquí. Avisame si me necesitas.")
                    except Exception:
                        pass

    def shutdown(self) -> None:
        self.stop_event.set()
        self.overlay.stop()

    def _handle_internal_command(self, command_text: str) -> str:
        if command_text == "/status":
            snapshot = self.state.snapshot()
            return f"Estado actual: {snapshot.status}. {snapshot.subtitle}"

        if command_text == "/diagnostico":
            report = self.config.diagnostics.report_file
            return f"El ultimo informe del circo vive en {report}"

        if command_text == "/sleep":
            self.state.set(CaineStatus.SLEEP, "Pausa manual del usuario.")
            return "Bajando el volumen del espectaculo. Quedo en espera."

        return "Comando interno no reconocido."

    def _build_extra_context(self, screen_summary: str, user_text: str) -> str:
        memory_summary = self.memory_store.get_context_summary(query=user_text, limit=self.config.memory.max_context_items)
        profile_summary = self.memory_store.get_user_profile_summary(limit=self.config.memory.max_context_items + 2)
        minecraft_context = self.minecraft.detect()
        parts = []
        if screen_summary:
            parts.append(f"Contexto de pantalla: {screen_summary}")
        if minecraft_context.detected:
            parts.append("Minecraft detectado en ejecucion.")
        if memory_summary:
            parts.append(f"Memoria relevante: {memory_summary}")
        if profile_summary:
            parts.append(f"Perfil del usuario inferido localmente: {profile_summary}")
        behavior_summary = self.memory_store.get_behavior_summary(limit=self.config.memory.max_context_items)
        if behavior_summary:
            parts.append(f"Patrones recientes del usuario: {behavior_summary}")
        return "\n".join(parts)

    def _looks_like_web_request(self, text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in ("web", "pagina", "pÃ¡gina", "landing"))

    def _preview_web_task(self, user_text: str) -> str:
        topic = user_text.strip().rstrip(".!?")
        return (
            f"Ah, eso ya es un acto de construccion real. "
            f"Puedo montarte una web simple dentro del proyecto. "
            f"Si quieres que la ejecute ahora mismo, dime 'hazlo'. Pedido pendiente: {topic}"
        )

