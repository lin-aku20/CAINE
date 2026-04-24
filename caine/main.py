"""Entrada principal de la entidad persistente CAINE."""

from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys
import time
import logging
import time
from collections import deque

import pytesseract

from brain.ai_brain import DesktopCompanionBrain
from avatar.overlay import CaineAvatarOverlay
from caine.app import CaineApp
from caine.config import CaineConfig
from caine.core.motivation import MotivationEngine
from caine.core.presence_loop import PresenceLoop
from events.event_bus import CaineEvent, EventBus
from caine.logging_utils import configure_logging
from caine.state import CaineStatus, StateSnapshot
from world.context_engine import ContextEngine, WorldState
from world.screen_watcher import ScreenObservation, ScreenWatcher
from voice.voice_system import CompanionVoiceSystem
from caine.cleanup import cleanup_ghost_instances


class PersistentCaineEntity:
    """Entidad local persistente: observa, comenta, escucha, actua y vuelve a dormir."""

    def __init__(self, config: CaineConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("caine.entity")
        self.core_app = CaineApp(config=config)
        self.runtime = self.core_app.runtime
        self.screen_watcher = ScreenWatcher(
            config=config,
            scan_interval=config.desktop.scan_interval_seconds,
            ocr_every_n_scans=config.desktop.ocr_every_n_scans,
            diff_threshold=config.desktop.diff_threshold,
        )
        self.context_engine = ContextEngine(config=config)
        self.event_bus = EventBus()
        self.motivation = MotivationEngine()
        self.presence = PresenceLoop(self.event_bus, self.motivation)
        self.companion_brain = DesktopCompanionBrain(
            brain=self.core_app.brain,
            memory_store=self.core_app.long_term_memory,
            reaction_cooldown_seconds=config.autonomy.commentary_cooldown_seconds,
            presence_interval_seconds=config.desktop.presence_interval_seconds,
        )
        self.avatar = CaineAvatarOverlay(
            open_chat_terminal=config.desktop.open_chat_terminal,
            avatar_dir=config.desktop.avatar_dir,
            overlay_always_on_top=config.desktop.overlay_always_on_top,
            terminal_always_on_top=config.desktop.terminal_always_on_top,
            hide_when_idle=True,
        )
        self.voice_output = CompanionVoiceSystem(config=config)
        self.stop_signal = asyncio.Event()
        self.world_state = WorldState()
        self.last_observation = ScreenObservation(
            timestamp="",
            active_app="",
            window_title="",
            extracted_text="",
            dominant_color_bgr=(0, 0, 0),
            new_window=False,
            text_changed=False,
            ui_changed=False,
            change_score=0.0,
        )
        self._last_commentary_at = 0.0
        self._event_commentary_at: dict[str, float] = {}
        self._commentary_window: deque[float] = deque()
        self._wire_event_handlers()

    async def run(self) -> None:
        self._configure_ocr()
        self.avatar.start()
        self.runtime.state.subscribe(self._on_state_change)
        self.runtime.start_background_features(interactive_session=False)
        self.avatar.add_chat_line("CAINE", "El circo digital respira bajo la mesa, Lin. Di 'Caine' y tiro del telon.")

        tasks = [
            asyncio.create_task(self.event_bus.run(self.stop_signal), name="event_bus"),
            asyncio.create_task(self._chat_loop(), name="chat_loop"),
            asyncio.create_task(self.presence.run(self.stop_signal), name="presence_loop"),
        ]
        if self.config.world.enabled:
            tasks.append(asyncio.create_task(self._world_loop(), name="world_loop"))
        if self.config.awareness.enabled:
            tasks.append(asyncio.create_task(self._screen_loop(), name="screen_loop"))
        if self.core_app.voice.is_enabled():
            tasks.append(asyncio.create_task(self._wake_loop(), name="wake_loop"))

        try:
            await asyncio.gather(*tasks)
        finally:
            self.stop_signal.set()
            await self.event_bus.shutdown()
            self.runtime.shutdown()
            self.avatar.stop()

    async def _world_loop(self) -> None:
        while not self.stop_signal.is_set():
            state, events = await asyncio.to_thread(self.context_engine.sample)
            self.world_state = state
            self.motivation.update_from_world(
                user_activity=state.user_activity,
                focus_duration=state.focus_duration,
                detected_context=state.detected_context,
            )
            self._reflect_world_on_avatar(state)

            for event_name, payload in events:
                await self.event_bus.emit(event_name, payload)

            await asyncio.sleep(self.config.world.scan_interval_seconds)

    async def _screen_loop(self) -> None:
        async def handle_observation(observation: ScreenObservation) -> None:
            self.last_observation = observation
            if not self.config.desktop.auto_talk_screen_events:
                return
            if time.monotonic() - self._last_commentary_at < self.config.autonomy.commentary_cooldown_seconds:
                return

            reaction = await asyncio.to_thread(self.companion_brain.react_to_screen, observation)
            if reaction.should_talk and reaction.message.strip():
                await self._deliver_reply(reaction.message, speak=True, source="screen")
                return

            presence = await asyncio.to_thread(self.companion_brain.ambient_presence, observation)
            if presence.should_talk and presence.message.strip():
                await self._deliver_reply(presence.message, speak=True, source="presence")

        await self.screen_watcher.watch(handle_observation)

    async def _wake_loop(self) -> None:
        while not self.runtime.stop_event.is_set():
            # Si no esta en modo continuo, esperar wake word
            if not self.config.desktop.always_listen_microphone:
                self.runtime.state.set(CaineStatus.WAITING_FOR_USER, "Escuchando wake word...")
                wake = await asyncio.to_thread(self.core_app.voice.listen_for_wake_word, self.runtime.stop_event)
                if not wake.ok:
                    await asyncio.sleep(0.2)
                    continue
                self.runtime.state.set(CaineStatus.LISTENING, "Escuchando comando...")
            else:
                self.runtime.state.set(CaineStatus.LISTENING, "Escuchando (Modo Continuo)...")

            # Escuchar el comando real
            heard = await asyncio.to_thread(self.core_app.voice.listen_for_command, self.runtime.stop_event)
            if not heard.ok or not heard.text.strip():
                if not self.config.desktop.always_listen_microphone:
                    self.runtime.state.set(CaineStatus.WAITING_FOR_USER, "No entendi. Vuelvo a esperar.")
                await asyncio.sleep(0.1)
                continue

            self.avatar.add_chat_line("LIN", heard.text)
            reply = await asyncio.to_thread(self.runtime.handle_text, heard.text)
            await self._deliver_reply(reply, speak=True, source="voice")
            
            # Pausa de seguridad
            if self.config.desktop.always_listen_microphone:
                await asyncio.sleep(0.5)

    async def _chat_loop(self) -> None:
        while not self.stop_signal.is_set():
            user_text = self.avatar.get_user_message_nowait()
            if not user_text:
                await asyncio.sleep(0.5)
                continue

            if user_text == "__SLEEP__":
                self.runtime.state.set(CaineStatus.SLEEP, "Dormido por orden manual.")
                self.avatar.add_chat_line("CAINE", "Zzz... cortando transmision manual.")
                continue
            if user_text == "__MUTE__":
                self._is_muted = not getattr(self, "_is_muted", False)
                estado = "silenciada" if self._is_muted else "activada"
                self.avatar.add_chat_line("SISTEMA", f"Voz {estado}.")
                continue
            if user_text == "__OBSERVE__":
                self.runtime.state.set(CaineStatus.OBSERVING, "Observacion forzada activa.")
                await self.event_bus.emit("autonomous_thought", {"reason": "forced_observation"})
                continue

            if user_text == "__MIC__":
                self.avatar.set_mic_state(True)
                heard = await asyncio.to_thread(self.core_app.voice.listen_for_command, self.runtime.stop_event)
                self.avatar.set_mic_state(False)
                if not heard.ok or not heard.text.strip():
                    self.avatar.add_chat_line("CAINE", "Nada, nada, nada... el micro no me regalo una frase util.")
                    self.runtime.state.set(CaineStatus.SLEEP, "Microfono sin frase clara.")
                    await asyncio.sleep(0.5)
                    continue
                self.avatar.add_chat_line("LIN", heard.text)
                user_text = heard.text

            reply = await asyncio.to_thread(self.runtime.handle_text, user_text)
            await self._deliver_reply(reply, speak=True, source="chat")

    async def _handle_context_event(self, event: CaineEvent) -> None:
        self.motivation.react_to_event(event.name)

        if event.name in {"app_closed", "user_focus_change"}:
            previous_app = str(event.payload.get("app") or event.payload.get("from") or "").strip()
            focus_duration = float(event.payload.get("focus_duration") or event.payload.get("previous_focus_duration") or 0.0)
            if previous_app and focus_duration > 5:
                self.core_app.long_term_memory.record_app_focus(previous_app, focus_duration)
                if "minecraft" in previous_app.lower():
                    self.core_app.long_term_memory.record_game_play(previous_app, focus_duration)

        if event.name not in {"game_detected", "long_inactivity", "repeated_behavior", "user_focus_change", "app_opened"}:
            return

        if not self._can_comment_on_event(event.name):
            return
        if not self.motivation.should_intervene(event.name):
            return

        if event.name == "game_detected":
            self.runtime.state.set(CaineStatus.EXCITED, "Un juego ha irrumpido en la pista digital.")
        elif event.name in {"app_opened", "user_focus_change"}:
            self.runtime.state.set(CaineStatus.OBSERVING, "Observo un cambio de foco en el escenario.")

        prompt = self._build_autonomous_prompt(event)
        reply = await asyncio.to_thread(
            self.core_app.brain.send_message,
            "Haz un comentario autonomo, breve y con mucha personalidad de CAINE. Maximo 2 frases.",
            extra_context=prompt,
        )
        await self._deliver_reply(reply, speak=True, source=event.name)

    async def _handle_background_event(self, event: CaineEvent) -> None:
        if event.name == "long_inactivity":
            self.runtime.state.set(CaineStatus.OBSERVING, "El escenario esta quieto. CAINE vigila.")

    async def _deliver_reply(self, reply: str, speak: bool, source: str) -> None:
        cleaned = reply.strip()
        if not cleaned:
            return

        self.avatar.show_message(cleaned)
        self.avatar.add_chat_line("CAINE", cleaned)
        self._mark_commentary(source)

        if speak and not getattr(self, "_is_muted", False):
            self.runtime.state.set(CaineStatus.SPEAKING, cleaned[:120])
            await self.voice_output.speak(cleaned)

        self.runtime.state.set(CaineStatus.WAITING_FOR_USER, "El telon cae. CAINE espera tu respuesta.")

    def _wire_event_handlers(self) -> None:
        self.event_bus.subscribe("app_opened", self._handle_context_event)
        self.event_bus.subscribe("game_detected", self._handle_context_event)
        self.event_bus.subscribe("long_inactivity", self._handle_context_event)
        self.event_bus.subscribe("repeated_behavior", self._handle_context_event)
        self.event_bus.subscribe("user_focus_change", self._handle_context_event)
        self.event_bus.subscribe("*", self._handle_background_event)

    def _can_comment_on_event(self, event_name: str) -> bool:
        if not self.config.autonomy.enabled:
            return False

        now = time.monotonic()
        if now - self._last_commentary_at < self.config.autonomy.commentary_cooldown_seconds:
            return False

        last_for_event = self._event_commentary_at.get(event_name, 0.0)
        if now - last_for_event < self.config.autonomy.same_event_cooldown_seconds:
            return False

        while self._commentary_window and now - self._commentary_window[0] > 3600:
            self._commentary_window.popleft()
        if len(self._commentary_window) >= self.config.autonomy.max_commentary_per_hour:
            return False
        return True

    def _mark_commentary(self, source: str) -> None:
        now = time.monotonic()
        self._last_commentary_at = now
        self._event_commentary_at[source] = now
        self._commentary_window.append(now)

    def _build_autonomous_prompt(self, event: CaineEvent) -> str:
        style = self.motivation.response_style()
        behavior_summary = self.core_app.long_term_memory.get_behavior_summary(limit=5)
        screen_summary = self.last_observation.summary() if self.last_observation.timestamp else ""
        world_summary = (
            f"app activa={self.world_state.active_app}; "
            f"contexto={self.world_state.detected_context}; "
            f"actividad={self.world_state.user_activity}; "
            f"foco={self.world_state.focus_duration:.1f}s"
        )
        return (
            f"Evento autonomo: {event.name}\n"
            f"Payload: {event.payload}\n"
            f"Estado del mundo: {world_summary}\n"
            f"Pantalla reciente: {screen_summary}\n"
            f"Habitos del usuario: {behavior_summary}\n"
            f"Estilo energetico actual de CAINE: {style}\n"
            f"Lin prefiere acompanamiento presente pero no pesado.\n"
            f"No seas Alexa. No seas asistente generico. Suena como CAINE."
        )

    def _reflect_world_on_avatar(self, state: WorldState) -> None:
        if state.user_activity == "idle":
            self.runtime.state.set(CaineStatus.SLEEP, "La pista queda en calma. CAINE observa desde bambalinas.")
            return

        if state.detected_context.startswith("juego:"):
            self.runtime.state.set(CaineStatus.OBSERVING, f"Observando el acto principal: {state.detected_context}.")
            return

        if state.changed and state.active_app:
            self.runtime.state.set(CaineStatus.OBSERVING, f"Nuevo foco detectado: {state.active_app}.")

    def _on_state_change(self, snapshot: StateSnapshot) -> None:
        self.avatar.apply_snapshot(snapshot)

    def _configure_ocr(self) -> None:
        if self.config.desktop.tesseract_cmd.strip():
            pytesseract.pytesseract.tesseract_cmd = self.config.desktop.tesseract_cmd.strip()


def _run_health_check() -> None:
    print(">> Ejecutando auto-diagnostico (Health Check)...")
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/health_check.ps1"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(">> [ERROR] CAINE detecto problemas en su entorno.")
            print(result.stdout)
            print(">> Ejecuta '.\\scripts\\auto_repair.ps1' para intentar una reparacion automatica.")
            sys.exit(1)
        print(">> Auto-diagnostico superado. CAINE esta sano.")
    except Exception as e:
        print(f">> [ADVERTENCIA] No se pudo correr el Health Check: {e}")


def main() -> None:
    cleanup_ghost_instances()
    _run_health_check()

    parser = argparse.ArgumentParser(description="CAINE persistent desktop entity")
    parser.add_argument("--legacy", action="store_true", help="Usa el modo de consola legado.")
    parser.add_argument("--resident", action="store_true", help="Usa el runtime de voz legado.")
    parser.add_argument("--headless", action="store_true", help="Ejecuta el modo legado sin overlay.")
    args = parser.parse_args()

    config = CaineConfig.from_yaml()
    configure_logging(config.logging.log_file, config.logging.level)

    if args.legacy or args.resident:
        app = CaineApp(config=config)
        app.run(resident=args.resident, interactive_session=not args.headless)
        return

    entity = PersistentCaineEntity(config=config)
    asyncio.run(entity.run())


if __name__ == "__main__":
    main()
