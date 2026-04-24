"""Capa de decision del companion desktop."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time

from brain.caine_brain import CaineBrain
from memory.long_term_memory import LongTermMemoryStore
from world.screen_watcher import ScreenObservation


@dataclass(slots=True)
class BrainReaction:
    should_talk: bool
    message: str
    reason: str


class DesktopCompanionBrain:
    """Wrapper del cerebro conversacional para companion desktop."""

    def __init__(
        self,
        brain: CaineBrain,
        memory_store: LongTermMemoryStore,
        reaction_cooldown_seconds: float = 18.0,
        presence_interval_seconds: float = 75.0,
    ) -> None:
        self.brain = brain
        self.memory_store = memory_store
        self.reaction_cooldown_seconds = reaction_cooldown_seconds
        self.presence_interval_seconds = presence_interval_seconds
        self.logger = logging.getLogger("caine.desktop_brain")
        self._last_reaction_at = 0.0
        self._last_presence_at = 0.0
        self._ignored_window_terms = {
            "install",
            "uninstall",
            "setup",
            "update",
            "loading",
            "copying",
            "removing",
        }

    def react_to_screen(self, observation: ScreenObservation) -> BrainReaction:
        """Decide si vale la pena hablar por un cambio de pantalla."""
        if not self._should_react(observation):
            return BrainReaction(False, "", "Sin cambio relevante o en cooldown.")

        prompt = self._build_screen_prompt(observation)
        reply = self.brain.send_message(
            (
                "Observa el contexto de pantalla y reacciona solo si hay algo realmente util. "
                "Maximo 2 frases cortas. Nada de monologos. Si no amerita comentario, guarda silencio."
            ),
            extra_context=prompt,
        )
        self._last_reaction_at = time.monotonic()
        self.memory_store.maybe_store_fact(
            user_text=f"[screen-event] {observation.summary()}",
            assistant_text=reply,
            intent="screen_awareness",
        )
        return BrainReaction(True, reply, "Cambio relevante de pantalla.")

    def chat(self, user_text: str, screen_summary: str = "") -> str:
        """Respuesta de chat explicita del usuario."""
        extra_context = (
            "Prioriza absolutamente la peticion del usuario. "
            "Usa el contexto de pantalla solo si es directamente relevante.\n"
            f"Contexto actual del companion: {screen_summary}"
            if screen_summary
            else "Prioriza absolutamente la peticion del usuario."
        )
        reply = self.brain.send_message(user_text, extra_context=extra_context)
        self.memory_store.maybe_store_fact(user_text=user_text, assistant_text=reply, intent="chat")
        return reply

    def ambient_presence(self, observation: ScreenObservation) -> BrainReaction:
        """Mantiene presencia ocasional, especialmente en juegos."""
        if not self._should_offer_presence(observation):
            return BrainReaction(False, "", "No toca comentario ambiental.")

        reply = self.brain.send_message(
            (
                "Estas acompanando al usuario mientras juega o usa una app. "
                "Haz un comentario breve, con personalidad, que suene presente pero no invasivo. "
                "Maximo 1 frase."
            ),
            extra_context=self._build_screen_prompt(observation),
        )
        self._last_presence_at = time.monotonic()
        return BrainReaction(True, reply, "Presencia ambiental.")

    def _should_react(self, observation: ScreenObservation) -> bool:
        if time.monotonic() - self._last_reaction_at < self.reaction_cooldown_seconds:
            return False

        title = observation.window_title.lower()
        if any(term in title for term in self._ignored_window_terms):
            return False

        if observation.extracted_text and len(observation.extracted_text.strip()) < 8:
            return False

        if observation.new_window:
            return True
        if observation.text_changed and observation.extracted_text:
            return True
        if observation.ui_changed and observation.change_score >= 0.08:
            return True
        return False

    def _should_offer_presence(self, observation: ScreenObservation) -> bool:
        if time.monotonic() - self._last_presence_at < self.presence_interval_seconds:
            return False
        active = observation.active_app.lower()
        title = observation.window_title.lower()
        game_like = any(keyword in active or keyword in title for keyword in ("minecraft", "roblox", "genshin", "vrchat", "javaw"))
        if not game_like:
            return False
        if observation.change_score < 0.03:
            return False
        return True

    def _build_screen_prompt(self, observation: ScreenObservation) -> str:
        return (
            f"Observacion local:\n"
            f"- App activa: {observation.active_app}\n"
            f"- Ventana: {observation.window_title}\n"
            f"- Texto visible: {observation.extracted_text[:400]}\n"
            f"- Cambio UI: {observation.ui_changed} ({observation.change_score:.3f})\n"
            f"- Nueva ventana: {observation.new_window}\n"
            f"- Color dominante BGR: {observation.dominant_color_bgr}\n"
            f"- No puedes interactuar con el programa ni modificar juegos: solo observar.\n"
            f"- Si reaccionas, se breve y especifico."
        )
