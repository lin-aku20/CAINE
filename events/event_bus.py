"""Bus de eventos asincrono para la vida interna de CAINE."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable


EventHandler = Callable[["CaineEvent"], Any | Awaitable[Any]]


@dataclass(slots=True)
class CaineEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class EventBus:
    """Despacha eventos del mundo a subsistemas desacoplados."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[CaineEvent | None] = asyncio.Queue()
        self._logger = logging.getLogger("caine.event_bus")

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)

    async def emit(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        await self._queue.put(CaineEvent(name=event_name, payload=payload or {}))

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if event is None:
                return

            handlers = [*self._subscribers.get(event.name, []), *self._subscribers.get("*", [])]
            for handler in handlers:
                try:
                    result = handler(event)
                    if inspect.isawaitable(result):
                        await result
                except Exception as error:
                    self._logger.exception("Fallo manejando evento %s: %s", event.name, error)

    async def shutdown(self) -> None:
        await self._queue.put(None)
