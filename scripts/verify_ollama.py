"""Verificacion rapida de conectividad con Ollama y modelos esperados."""

from brain.caine_brain import CaineBrain
from caine.config import CaineConfig
from memory.conversation_memory import ConversationMemory
from personality.loader import PersonalityLoader


def main() -> None:
    config = CaineConfig.from_yaml()
    brain = CaineBrain(
        base_url=config.ollama.base_url,
        primary_model=config.ollama.primary_model,
        fallback_model=config.ollama.fallback_model,
        timeout_seconds=config.ollama.timeout_seconds,
        personality_loader=PersonalityLoader(config.personality_file),
        conversation_memory=ConversationMemory(limit=config.memory.conversation_limit),
    )
    ok, message = brain.connection_test()
    print("[OK]" if ok else "[ERROR]", message)


if __name__ == "__main__":
    main()
