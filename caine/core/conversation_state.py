"""MÃ¡quina de estados conversacional estricta de CAINE.

Regla fundamental:
  - DespuÃ©s de RESPOND, CAINE SOLO puede volver a hablar cuando:
    a) Recibe input humano real (teclado / micrÃ³fono verificado)
    b) El AutonomyGovernor autoriza una intervenciÃ³n proactiva

  - CAINE NUNCA puede fabricar mensajes del rol HUMAN.
  - NingÃºn output del modelo puede volver a entrar como input humano.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from enum import StrEnum
from typing import Callable


logger = logging.getLogger("caine.conversation_state")

LAST_CAINE_OUTPUT: str = ""
LAST_CAINE_OUTPUT_TIME: float = 0.0

def register_caine_speech(text: str) -> None:
    global LAST_CAINE_OUTPUT, LAST_CAINE_OUTPUT_TIME
    LAST_CAINE_OUTPUT = text.strip().lower()
    LAST_CAINE_OUTPUT_TIME = time.monotonic()

# ---------------------------------------------------------------------------
# Roles de mensaje â€” separaciÃ³n absoluta
# ---------------------------------------------------------------------------

class MessageRole(StrEnum):
    HUMAN = "human"      # Solo teclado real o micrÃ³fono verificado
    CAINE = "caine"      # Solo generado por Brain â†’ VoiceAuthority
    SYSTEM = "system"    # Eventos internos del sistema


# ---------------------------------------------------------------------------
# Estados conversacionales
# ---------------------------------------------------------------------------

class ConvState(StrEnum):
    BOOT = "BOOT"
    IDLE = "IDLE"
    INITIATE = "INITIATE"                # CAINE inicia (autÃ³nomo, vÃ­a governor)
    WAIT_FOR_HUMAN = "WAIT_FOR_HUMAN"    # Esperando input humano real
    PROCESS_INPUT = "PROCESS_INPUT"      # Brain procesando
    RESPOND = "RESPOND"                  # VoiceAuthority emitiendo
    SLEEP = "SLEEP"


# Transiciones vÃ¡lidas: estado_actual â†’ estados_permitidos
_VALID_TRANSITIONS: dict[ConvState, set[ConvState]] = {
    ConvState.BOOT:           {ConvState.IDLE, ConvState.SLEEP},
    ConvState.IDLE:           {ConvState.WAIT_FOR_HUMAN, ConvState.INITIATE, ConvState.SLEEP, ConvState.PROCESS_INPUT},
    ConvState.INITIATE:       {ConvState.RESPOND, ConvState.IDLE},
    ConvState.WAIT_FOR_HUMAN: {ConvState.PROCESS_INPUT, ConvState.SLEEP, ConvState.IDLE},
    ConvState.PROCESS_INPUT:  {ConvState.RESPOND, ConvState.IDLE},
    ConvState.RESPOND:        {ConvState.WAIT_FOR_HUMAN, ConvState.SLEEP, ConvState.IDLE},
    ConvState.SLEEP:          {ConvState.IDLE, ConvState.WAIT_FOR_HUMAN},
}


class ConversationStateMachine:
    """Controla el flujo conversacional con separaciÃ³n de roles absoluta.

    Uso:
        csm = ConversationStateMachine()
        csm.receive_human_input("hola")   # valida origen real
        csm.enter_processing()
        csm.enter_respond()
        # CAINE habla...
        csm.finish_respond()              # â†’ WAIT_FOR_HUMAN automÃ¡tico
    """

    def __init__(self) -> None:
        self._state = ConvState.BOOT
        self._lock = threading.Lock()
        self._listeners: list[Callable[[ConvState, ConvState], None]] = []
        self._last_human_input_at: float = 0.0
        self._last_respond_at: float = 0.0

    # ------------------------------------------------------------------
    # Estado pÃºblico
    # ------------------------------------------------------------------

    @property
    def state(self) -> ConvState:
        with self._lock:
            return self._state

    def is_waiting_for_human(self) -> bool:
        return self.state in {ConvState.WAIT_FOR_HUMAN, ConvState.IDLE}

    def can_caine_speak(self) -> bool:
        """True solo si la mÃ¡quina estÃ¡ en RESPOND o INITIATE."""
        return self.state in {ConvState.RESPOND, ConvState.INITIATE}

    def seconds_since_last_human_input(self) -> float:
        return time.monotonic() - self._last_human_input_at

    def seconds_since_last_respond(self) -> float:
        return time.monotonic() - self._last_respond_at

    # ------------------------------------------------------------------
    # Transiciones controladas
    # ------------------------------------------------------------------

    def boot_complete(self) -> None:
        self._transition(ConvState.IDLE, "boot complete")

    def receive_human_input(self, text: str, source: str = "keyboard") -> bool:
        """Registra un input VERIFICADO como humano real.

        Args:
            text: Texto del input.
            source: 'keyboard' | 'microphone' â€” NUNCA 'model' o 'internal'.

        Returns:
            True si el input fue aceptado (estado correcto).
        """
        if source not in ("keyboard", "microphone"):
            logger.error(
                "SEGURIDAD: input rechazado â€” fuente no humana '%s'. "
                "CAINE no puede fabricar mensajes del usuario.", source
            )
            return False

        if not text or not text.strip():
            return False

        # Bloquear si el input parece ser output del modelo (heurÃ­stica)
        if _looks_like_model_output(text):
            logger.warning(
                "SEGURIDAD: input rechazado â€” parece output del modelo: %r", text[:80]
            )
            return False
            
        # Filtro Anti-Eco: ignorar si es igual a lo último que dijo CAINE (solo micrófono y dentro de 10 seg)
        global LAST_CAINE_OUTPUT, LAST_CAINE_OUTPUT_TIME
        if source == "microphone" and LAST_CAINE_OUTPUT:
            time_since_speech = time.monotonic() - LAST_CAINE_OUTPUT_TIME
            if time_since_speech < 15.0: # Ventana de 15 segundos para el eco
                lowered_text = text.strip().lower()
                # Permitir la wake word explícita aunque coincida con algo
                if lowered_text != "caine" and len(lowered_text) > 3:
                    if lowered_text in LAST_CAINE_OUTPUT or LAST_CAINE_OUTPUT in lowered_text:
                        logger.warning(
                            "ANTI-ECO: Input rechazado (eco de TTS detectado): %r", text[:80]
                        )
                        return False

        accepted = self._transition(ConvState.PROCESS_INPUT, f"human input via {source}")
        if accepted:
            self._last_human_input_at = time.monotonic()
        return accepted

    def initiate_autonomous(self) -> bool:
        """CAINE inicia una intervenciÃ³n autÃ³noma (solo vÃ­a AutonomyGovernor)."""
        return self._transition(ConvState.INITIATE, "autonomous initiation")

    def enter_processing(self) -> bool:
        return self._transition(ConvState.PROCESS_INPUT, "entering processing")

    def enter_respond(self) -> bool:
        return self._transition(ConvState.RESPOND, "entering respond")

    def finish_respond(self) -> None:
        """DespuÃ©s de responder, CAINE vuelve a esperar input humano."""
        self._last_respond_at = time.monotonic()
        self._transition(ConvState.WAIT_FOR_HUMAN, "respond finished â€” awaiting human")

    def go_sleep(self) -> None:
        self._transition(ConvState.SLEEP, "entering sleep")

    def wake_up(self) -> None:
        self._transition(ConvState.IDLE, "waking up")

    # ------------------------------------------------------------------
    # Observadores
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[ConvState, ConvState], None]) -> None:
        """Suscribirse a cambios de estado: callback(old_state, new_state)."""
        self._listeners.append(callback)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _transition(self, target: ConvState, reason: str) -> bool:
        with self._lock:
            current = self._state
            allowed = _VALID_TRANSITIONS.get(current, set())
            if target not in allowed:
                logger.debug(
                    "TransiciÃ³n bloqueada: %s â†’ %s (%s). Permitidos: %s",
                    current, target, reason, allowed
                )
                return False
            self._state = target
            old = current

        logger.debug("ConvState: %s â†’ %s [%s]", old, target, reason)
        for cb in self._listeners:
            try:
                cb(old, target)
            except Exception:
                pass
        return True


# ---------------------------------------------------------------------------
# HeurÃ­stica de seguridad â€” detectar output de modelo disfrazado de usuario
# ---------------------------------------------------------------------------

_MODEL_OUTPUT_PATTERNS = (
    "lin:",
    "usuario:",
    "user:",
    "\nlin ",
    "\ncaine:",
    "lin dice",
    "lin responde",
)


def _looks_like_model_output(text: str) -> bool:
    """Detecta si el texto parece haber sido generado por el modelo."""
    lowered = text.strip().lower()
    return any(pat in lowered for pat in _MODEL_OUTPUT_PATTERNS)


def normalize_human_input(text: str) -> str:
    """Limpia prefijos duplicados del usuario como 'LIN >>' o 'LIN:'."""
    if not text:
        return ""
    
    cleaned = text.strip()
    
    # Remover múltiples prefijos repetidos
    prefixes = ["lin >>", "lin:", "lin :", "usuario:", "user:", "human:"]
    changed = True
    while changed:
        changed = False
        lower = cleaned.lower()
        for p in prefixes:
            if lower.startswith(p):
                cleaned = cleaned[len(p):].strip()
                changed = True
                break
                
    return cleaned


def validate_caine_output(text: str) -> tuple[bool, str]:
    """Valida que el output del brain no contenga roles fabricados.

    Returns:
        (is_clean, cleaned_text)
    """
    if not text:
        return True, text

    lines = text.split("\n")
    clean_lines: list[str] = []
    found_fabrication = False

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        
        # Ignorar líneas vacías si ya estamos limpiando
        if not stripped:
            clean_lines.append(line)
            continue
            
        # Detectar líneas que simulan al usuario
        if any(lower.startswith(pat) for pat in ("lin:", "lin >>", "usuario:", "user:", "human:")):
            logger.warning("SEGURIDAD: línea de rol fabricado eliminada: %r", stripped)
            found_fabrication = True
            continue
            
        # Limpiar si CAINE pone explícitamente "CAINE:" al inicio de su propia línea
        if lower.startswith("caine:"):
            stripped = stripped[6:].strip()
            line = stripped # Reemplazar la línea completa por la versión sin prefijo
            
        clean_lines.append(line)

    cleaned = "\n".join(clean_lines).strip()

    if found_fabrication:
        logger.error(
            "SEGURIDAD: el modelo intentó fabricar mensajes del usuario. "
            "Output parcialmente saneado."
        )

    return not found_fabrication, cleaned
