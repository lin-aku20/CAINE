"""AutonomyGovernor — Gobernador de intervenciones autónomas de CAINE.

Controla cuándo CAINE puede hablar sin ser invocado por el usuario.

Principios:
  - CAINE debe sentirse vivo, no ansioso.
  - Máximo 1 intervención autónoma cada N minutos (default: 8).
  - No puede intervenir si acaba de responder (cooldown post-respuesta).
  - No puede intervenir si hay un intercambio activo en curso.
  - Respeta el estado conversacional antes de autorizar.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from caine.core.conversation_state import ConversationStateMachine

logger = logging.getLogger("caine.autonomy_governor")


@dataclass
class GovernorConfig:
    """Configuración del gobernador de autonomía."""
    # Tiempo mínimo entre intervenciones autónomas (segundos)
    min_interval_seconds: float = 480.0          # 8 minutos por defecto
    # Cooldown después de que CAINE respondió (evita respuesta → auto-charla)
    post_respond_cooldown_seconds: float = 120.0  # 2 minutos
    # Cooldown por tipo de evento (evita repetir el mismo evento)
    same_event_cooldown_seconds: float = 900.0    # 15 minutos
    # Máximo de intervenciones autónomas por hora
    max_per_hour: int = 6
    # Habilitar/deshabilitar autonomía completamente
    enabled: bool = True


@dataclass
class InterventionRecord:
    timestamp: float
    source: str
    approved: bool


class AutonomyGovernor:
    """Decide si CAINE puede hacer una intervención autónoma.

    Centraliza toda la lógica de cooldown que antes estaba dispersa en
    main.py, presence_loop.py y otros módulos.

    Uso:
        governor = AutonomyGovernor(config, conv_state)
        if governor.can_initiate("long_inactivity"):
            governor.record_intervention("long_inactivity")
            # → CAINE habla
    """

    def __init__(
        self,
        config: GovernorConfig | None = None,
        conv_state: ConversationStateMachine | None = None,
    ) -> None:
        self.config = config or GovernorConfig()
        self._conv = conv_state
        self._last_intervention_at: float = 0.0
        self._last_by_source: dict[str, float] = {}
        self._hourly_window: deque[float] = deque()
        self._history: list[InterventionRecord] = []

    def can_initiate(self, source: str = "unknown") -> bool:
        """Evalúa si CAINE puede iniciar una intervención autónoma ahora.

        Args:
            source: Nombre del evento/módulo que quiere intervenir.

        Returns:
            True si la intervención está autorizada.
        """
        if not self.config.enabled:
            logger.debug("Governor: autonomía deshabilitada globalmente.")
            return False

        now = time.monotonic()

        # 1. Verificar estado conversacional
        if self._conv is not None:
            from caine.core.conversation_state import ConvState
            state = self._conv.state
            if state not in {ConvState.IDLE, ConvState.WAIT_FOR_HUMAN, ConvState.SLEEP}:
                logger.debug(
                    "Governor: bloqueado — estado conversacional activo (%s).", state
                )
                return False

        # 2. Cooldown global entre intervenciones
        elapsed_since_last = now - self._last_intervention_at
        if elapsed_since_last < self.config.min_interval_seconds:
            remaining = self.config.min_interval_seconds - elapsed_since_last
            logger.debug(
                "Governor: bloqueado — cooldown global activo (%.0fs restantes).", remaining
            )
            return False

        # 3. Cooldown post-respuesta (CAINE no puede autocharlar)
        if self._conv is not None:
            elapsed_since_respond = self._conv.seconds_since_last_respond()
            if elapsed_since_respond < self.config.post_respond_cooldown_seconds:
                remaining = self.config.post_respond_cooldown_seconds - elapsed_since_respond
                logger.debug(
                    "Governor: bloqueado — post-respond cooldown (%.0fs restantes).", remaining
                )
                return False

        # 4. Cooldown por tipo de evento
        last_for_source = self._last_by_source.get(source, 0.0)
        if now - last_for_source < self.config.same_event_cooldown_seconds:
            remaining = self.config.same_event_cooldown_seconds - (now - last_for_source)
            logger.debug(
                "Governor: bloqueado — mismo evento '%s' muy reciente (%.0fs restantes).",
                source, remaining
            )
            return False

        # 5. Límite por hora
        self._purge_old_hourly(now)
        if len(self._hourly_window) >= self.config.max_per_hour:
            logger.debug(
                "Governor: bloqueado — límite horario alcanzado (%d/%d).",
                len(self._hourly_window), self.config.max_per_hour
            )
            return False

        logger.info("Governor: intervención autónoma AUTORIZADA para fuente '%s'.", source)
        return True

    def record_intervention(self, source: str) -> None:
        """Registra que una intervención autónoma fue ejecutada."""
        now = time.monotonic()
        self._last_intervention_at = now
        self._last_by_source[source] = now
        self._hourly_window.append(now)
        self._history.append(InterventionRecord(
            timestamp=now, source=source, approved=True
        ))
        logger.info("Governor: intervención registrada [%s].", source)

    def record_blocked(self, source: str, reason: str) -> None:
        """Registra un intento de intervención que fue bloqueado."""
        self._history.append(InterventionRecord(
            timestamp=time.monotonic(), source=source, approved=False
        ))
        logger.debug("Governor: bloqueado [%s] — %s", source, reason)

    def reset_cooldown(self) -> None:
        """Resetea cooldowns (útil en testing o reinicio de sesión)."""
        self._last_intervention_at = 0.0
        self._last_by_source.clear()
        self._hourly_window.clear()

    def status(self) -> dict:
        """Estado actual del gobernador para diagnóstico."""
        now = time.monotonic()
        self._purge_old_hourly(now)
        return {
            "enabled": self.config.enabled,
            "min_interval_seconds": self.config.min_interval_seconds,
            "seconds_since_last": now - self._last_intervention_at,
            "interventions_this_hour": len(self._hourly_window),
            "max_per_hour": self.config.max_per_hour,
        }

    def _purge_old_hourly(self, now: float) -> None:
        while self._hourly_window and now - self._hourly_window[0] > 3600:
            self._hourly_window.popleft()
