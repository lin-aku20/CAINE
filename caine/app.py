"""Orquestador principal de CAINE."""

from __future__ import annotations

import logging

from interaction.system_actions import SystemActionRouter
from brain.caine_brain import CaineBrain
from caine.config import CaineConfig
from caine.runtime import CaineRuntime
from caine.state import CaineStatus
from memory.conversation_memory import ConversationMemory
from memory.long_term_memory import LongTermMemoryStore
from personality.loader import PersonalityLoader
from voice.voice_pipeline import VoicePipeline


class CaineApp:
    """Aplicacion principal del asistente local."""

    def __init__(self, config: CaineConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("caine.app")
        self.personality_loader = PersonalityLoader(config.personality_file)
        self.conversation_memory = ConversationMemory(limit=config.memory.conversation_limit)
        self.long_term_memory = LongTermMemoryStore(
            storage_file=config.memory.long_term_file,
            legacy_json_file=config.memory.legacy_json_file,
        )
        self.brain = CaineBrain(
            base_url=config.ollama.base_url,
            primary_model=config.ollama.primary_model,
            fallback_model=config.ollama.fallback_model,
            api_key=config.ollama.api_key,
            timeout_seconds=config.ollama.timeout_seconds,
            personality_loader=self.personality_loader,
            conversation_memory=self.conversation_memory,
        )
        self.actions = SystemActionRouter(config=config.actions)
        self.voice = VoicePipeline(config=config.voice)
        self.runtime = CaineRuntime(
            config=config,
            brain=self.brain,
            actions=self.actions,
            memory_store=self.long_term_memory,
            voice=self.voice,
        )

    def run(self, resident: bool = False, interactive_session: bool = True) -> None:
        self.runtime.start_background_features(interactive_session=interactive_session)

        if resident and self.voice.is_enabled():
            self.runtime.run_voice_loop()
            return

        print("CAINE listo. Escribe 'salir' para terminar.")
        print(f"Modelo principal: {self.config.ollama.primary_model}")
        print("Modo voz:", "activo" if self.config.voice.enabled else "desactivado")

        while True:
            user_text = input("\nTu: ").strip()

            if not user_text:
                continue

            if user_text.lower() in {"salir", "exit", "quit"}:
                print("CAINE: El telon cae por ahora, estimado invitado.")
                self.runtime.shutdown()
                break

            reply = self.runtime.handle_text(user_text)
            self.logger.info("Interaccion completada con %s caracteres de respuesta", len(reply))
            print(f"CAINE: {reply}")

            if self.voice.is_enabled():
                self.runtime.state.set(self.runtime.state.snapshot().status, reply[:80])
                self.voice.speak(reply)
            self.runtime.state.set(CaineStatus.WAITING_FOR_USER, "Esperando el siguiente acto.")
