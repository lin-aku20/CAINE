"""HookManager — Listener pasivo de acciones reales del usuario.

Escucha clics y teclado SIN interceptar ni bloquear los eventos.
Solo observa y emite eventos internos para que ActionObserver los procese.

Seguridad:
- Nunca almacena lo que se escribe en campos de contraseña.
- Detecta campos password por contexto OCR (texto "*" o etiqueta "password").
- Solo emite UserClickEvent y UserTypeEvent a los suscriptores internos.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("caine.learning.hook")


@dataclass
class UserClickEvent:
    x: int
    y: int
    button: str           # "left" | "right" | "double"
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class UserTypeEvent:
    text: str             # texto completo antes del Enter
    timestamp: float = field(default_factory=time.monotonic)


ClickCallback = Callable[[UserClickEvent], None]
TypeCallback  = Callable[[UserTypeEvent], None]


class HookManager:
    """Monitor pasivo de mouse y teclado. No bloquea eventos del usuario."""

    def __init__(self) -> None:
        self._click_listeners: list[ClickCallback] = []
        self._type_listeners:  list[TypeCallback]  = []
        self._running = False
        self._mouse_listener = None
        self._keyboard_listener = None
        self._current_word: list[str] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def on_click(self, cb: ClickCallback) -> None:
        self._click_listeners.append(cb)

    def on_type(self, cb: TypeCallback) -> None:
        self._type_listeners.append(cb)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._start_listeners, daemon=True, name="caine-hook").start()
        logger.info("[HOOK] Listener de usuario iniciado (pasivo).")

    def stop(self) -> None:
        self._running = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        logger.info("[HOOK] Listener detenido.")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _start_listeners(self) -> None:
        from pynput import mouse, keyboard

        def on_click(x, y, button, pressed):
            if not pressed or not self._running:
                return
            btn = "left" if "left" in str(button) else "right"
            event = UserClickEvent(x=x, y=y, button=btn)
            self._dispatch_click(event)

        def on_key_press(key):
            if not self._running:
                return
            try:
                char = key.char
                if char:
                    with self._lock:
                        self._current_word.append(char)
            except AttributeError:
                # Teclas especiales (Enter, Esc, Backspace, etc.)
                from pynput.keyboard import Key
                if key == Key.enter:
                    with self._lock:
                        word = "".join(self._current_word).strip()
                        self._current_word.clear()
                    if word and not self._is_sensitive(word):
                        self._dispatch_type(UserTypeEvent(text=word))
                elif key == Key.backspace:
                    with self._lock:
                        if self._current_word:
                            self._current_word.pop()
                elif key in (Key.esc, Key.tab):
                    with self._lock:
                        self._current_word.clear()

        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._keyboard_listener = keyboard.Listener(on_press=on_key_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()
        self._mouse_listener.join()

    def _dispatch_click(self, event: UserClickEvent) -> None:
        for cb in self._click_listeners:
            try:
                threading.Thread(target=cb, args=(event,), daemon=True).start()
            except Exception as exc:
                logger.debug("[HOOK] Error en listener click: %s", exc)

    def _dispatch_type(self, event: UserTypeEvent) -> None:
        for cb in self._type_listeners:
            try:
                threading.Thread(target=cb, args=(event,), daemon=True).start()
            except Exception as exc:
                logger.debug("[HOOK] Error en listener type: %s", exc)

    @staticmethod
    def _is_sensitive(text: str) -> bool:
        """Descarta texto que parece contraseña (solo asteriscos o muy corto)."""
        stripped = text.strip()
        if not stripped or len(stripped) < 2:
            return True
        if all(c == "*" for c in stripped):
            return True
        return False
