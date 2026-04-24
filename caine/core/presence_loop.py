"""Bucle asincrono de presencia continua para CAINE."""

import asyncio
import logging
from events.event_bus import EventBus
from caine.core.motivation import MotivationEngine

class PresenceLoop:
    """Supervisa la motivacion y emite pensamientos autonomos o decisiones espontaneas."""
    
    def __init__(self, event_bus: EventBus, motivation: MotivationEngine) -> None:
        self.event_bus = event_bus
        self.motivation = motivation
        self.logger = logging.getLogger("caine.presence_loop")
        
    async def run(self, stop_signal: asyncio.Event) -> None:
        """Se ejecuta en baja frecuencia para no saturar CPU (tick de 60 segundos)."""
        self.logger.info("Presence loop iniciado. La entidad es autonoma.")
        
        while not stop_signal.is_set():
            # Dormir de a tramos pequeños para reaccionar rapido a stop_signal
            for _ in range(60):
                if stop_signal.is_set():
                    return
                await asyncio.sleep(1.0)
                
            state = self.motivation.snapshot()
            
            if state.boredom > 0.85:
                self.logger.info("CAINE se siente aburrido. Emitiendo autonomous_thought.")
                await self.event_bus.emit("autonomous_thought", {
                    "reason": "extreme_boredom", 
                    "context": "El sistema ha estado inactivo o sin cambios mucho tiempo."
                })
                self.motivation.state.boredom *= 0.5
                
            elif state.curiosity > 0.85:
                self.logger.info("CAINE siente curiosidad. Emitiendo autonomous_thought.")
                await self.event_bus.emit("autonomous_thought", {
                    "reason": "high_curiosity",
                    "context": "El usuario paso mucho tiempo enfocado en un app interesante."
                })
                self.motivation.state.curiosity *= 0.5
