"""Estados internos de CAINE y notificacion de cambios."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import threading
from typing import Callable


class CaineStatus(StrEnum):
    SLEEP = "sleep"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ACTING = "acting"
    OBSERVING = "observing"
    EXCITED = "excited"
    WAITING_FOR_USER = "waiting_for_user"


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
