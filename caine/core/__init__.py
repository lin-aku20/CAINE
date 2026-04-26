"""Núcleo autónomo de CAINE.

Módulos del núcleo (orden de importación seguro):
  - motivation          → motor pseudo-emocional
  - conversation_state  → máquina de estados conversacional + seguridad de roles
  - autonomy_governor   → control de intervenciones autónomas
  - voice_authority     → única autoridad de salida (texto/TTS/overlay)
  - graceful_failure    → capa de fallos naturales
  - presence_loop       → bucle de presencia continua
"""

from caine.core.motivation import MotivationEngine, MotivationState
from caine.core.conversation_state import (
    ConversationStateMachine,
    ConvState,
    MessageRole,
    validate_caine_output,
)
from caine.core.autonomy_governor import AutonomyGovernor, GovernorConfig
from caine.core.voice_authority import VoiceAuthority
from caine.core.graceful_failure import GracefulContext, graceful_caine_response
from caine.core.presence_loop import PresenceLoop

__all__ = [
    "MotivationEngine",
    "MotivationState",
    "ConversationStateMachine",
    "ConvState",
    "MessageRole",
    "validate_caine_output",
    "AutonomyGovernor",
    "GovernorConfig",
    "VoiceAuthority",
    "GracefulContext",
    "graceful_caine_response",
    "PresenceLoop",
]
