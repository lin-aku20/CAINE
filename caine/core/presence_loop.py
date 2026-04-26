"""Bucle asíncrono de presencia continua para CAINE.

Las intervenciones autónomas se consultan primero con AutonomyGovernor.
Tick de 60 segundos para no saturar CPU en idle.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from events.event_bus import EventBus
from caine.core.motivation import MotivationEngine

if TYPE_CHECKING:
    from caine.core.autonomy_governor import AutonomyGovernor

logger = logging.getLogger("caine.presence_loop")


class PresenceLoop:
    """Supervisa la motivación y emite eventos autónomos con control de frecuencia."""

    def __init__(
        self,
        event_bus: EventBus,
        motivation: MotivationEngine,
        governor: "AutonomyGovernor | None" = None,
    ) -> None:
        self.event_bus = event_bus
        self.motivation = motivation
        self.governor = governor

    async def run(self, stop_signal: asyncio.Event) -> None:
        """Se ejecuta en baja frecuencia (tick de 60 segundos)."""
        logger.info("Presence loop iniciado. La entidad es autónoma.")

        while not stop_signal.is_set():
            # Dormir en tramos pequeños para reaccionar rápido a stop_signal
            for _ in range(60):
                if stop_signal.is_set():
                    return
                await asyncio.sleep(1.0)

            state = self.motivation.snapshot()

            if state.boredom > 0.85:
                source = "extreme_boredom"
                if self._can_emit(source):
                    logger.info("CAINE se siente aburrido. Emitiendo autonomous_thought.")
                    await self.event_bus.emit("autonomous_thought", {
                        "reason": source,
                        "context": "El sistema ha estado inactivo o sin cambios mucho tiempo.",
                    })
                    self.motivation.state.boredom *= 0.5
                    if self.governor:
                        self.governor.record_intervention(source)

            elif state.curiosity > 0.85:
                source = "high_curiosity"
                if self._can_emit(source):
                    logger.info("CAINE siente curiosidad. Emitiendo autonomous_thought.")
                    await self.event_bus.emit("autonomous_thought", {
                        "reason": source,
                        "context": "El usuario pasó mucho tiempo enfocado en una app interesante.",
                    })
                    self.motivation.state.curiosity *= 0.5
                    if self.governor:
                        self.governor.record_intervention(source)

    def _can_emit(self, source: str) -> bool:
        """Verifica con el governor si se puede emitir el evento."""
        if self.governor is None:
            return True
        can = self.governor.can_initiate(source)
        if not can:
            self.governor.record_blocked(source, "presence_loop governor check")
        return can
