"""Bucle de percepción continua del escritorio.

CAINE observa activamente el escritorio cada N ms y actualiza su
DesktopSnapshot. Cualquier cambio visual > umbral activa un evento.
Corre en un hilo de background, no bloquea el event loop principal.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("caine.perception.loop")


class DesktopPerceptionLoop:
    """Hilo de percepción continua.

    Captura el escritorio cada `interval_ms` milisegundos y mantiene el
    snapshot más reciente. Notifica a suscriptores cuando detecta cambios.
    """

    def __init__(
        self,
        interval_ms: float = 500,
        on_change: Optional[Callable] = None,
    ) -> None:
        self._interval = interval_ms / 1000.0
        self._on_change = on_change
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._snapshot = None
        self._lock = threading.Lock()

        # Import lazy para no bloquear si mss no está instalado
        from caine.perception.desktop_vision import DesktopVisionAgent
        self._vision = DesktopVisionAgent()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Inicia el bucle en background."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="caine-perception")
        self._thread.start()
        logger.info("[PERCEPCIÓN] Bucle de visión continua iniciado (intervalo %.0f ms)", self._interval * 1000)

    def stop(self) -> None:
        """Detiene el bucle."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("[PERCEPCIÓN] Bucle detenido.")

    @property
    def snapshot(self):
        """Último DesktopSnapshot disponible (thread-safe)."""
        with self._lock:
            return self._snapshot

    @property
    def active_app(self) -> str:
        snap = self.snapshot
        return snap.active_app if snap else ""

    @property
    def ui_changed(self) -> bool:
        snap = self.snapshot
        return snap.ui_changed if snap else False

    def get_vision(self):
        """Expone el DesktopVisionAgent subyacente para template matching puntual."""
        return self._vision

    # ------------------------------------------------------------------
    # Bucle interno
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                snap = self._vision.take_snapshot()
                with self._lock:
                    self._snapshot = snap

                # Notificar cambios a suscriptores
                if snap.ui_changed and self._on_change:
                    try:
                        self._on_change(snap)
                    except Exception as exc:
                        logger.warning("[PERCEPCIÓN] Error en callback on_change: %s", exc)

            except Exception as exc:
                logger.warning("[PERCEPCIÓN] Error en snapshot: %s", exc)

            time.sleep(self._interval)
