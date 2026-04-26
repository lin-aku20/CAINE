"""Estados internos de CAINE y notificacion de cambios."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import threading
from typing import Callable


class CaineStatus(StrEnum):
    # Ciclo de vida del sistema
    BOOT = "boot"                    # Inicializando subsistemas
    IDLE = "idle"                    # En espera pasiva (sin wake word aún)
    SLEEP = "sleep"                  # Dormido por inactividad o comando
    # Ciclo conversacional
    INITIATE = "initiate"            # CAINE inicia contacto (autónomo)
    WAIT_FOR_HUMAN = "wait_for_human"  # Esperando input humano real
    PROCESS_INPUT = "process_input"  # Procesando el input recibido
    RESPOND = "respond"              # Generando y emitiendo respuesta
    # Estados operativos
    LISTENING = "listening"          # Escuchando micrófono activamente
    THINKING = "thinking"            # Consultando modelo/memoria
    SPEAKING = "speaking"            # TTS en curso
    ACTING = "acting"                # Ejecutando acción del sistema
    OBSERVING = "observing"          # Observando pantalla/contexto
    EXCITED = "excited"              # Estado de alta activación
    # Deprecated alias (backward compat)
    WAITING_FOR_USER = "wait_for_human"


@dataclass(slots=True)
class StateSnapshot:
    status: CaineStatus
    subtitle: str


class StateController:
    """Controla el estado operativo y avisa a observadores."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = StateSnapshot(status=CaineStatus.SLEEP, subtitle="En espera")
        self._listeners: list[Callable[[StateSnapshot], None]] = []

    def subscribe(self, callback: Callable[[StateSnapshot], None]) -> None:
        self._listeners.append(callback)
        callback(self.snapshot())

    def set(self, status: CaineStatus, subtitle: str) -> None:
        with self._lock:
            self._snapshot = StateSnapshot(status=status, subtitle=subtitle)
            snapshot = self._snapshot

        for callback in self._listeners:
            try:
                callback(snapshot)
            except Exception:
                continue

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return StateSnapshot(
                status=self._snapshot.status,
                subtitle=self._snapshot.subtitle,
            )
