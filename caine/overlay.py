"""Overlay visual ligero para estados y subtitulos."""

from __future__ import annotations

import queue
import threading
import tkinter as tk

from caine.state import StateSnapshot


class CaineOverlay:
    """Ventana flotante simple y siempre visible."""

    def __init__(self, title: str, geometry: str, always_on_top: bool = True) -> None:
        self.title = title
        self.geometry = geometry
        self.always_on_top = always_on_top
        self._queue: queue.Queue[StateSnapshot | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, name="CaineOverlay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)

    def update(self, snapshot: StateSnapshot) -> None:
        self._queue.put(snapshot)

    def _run(self) -> None:
        root = tk.Tk()
        root.title(self.title)
        root.geometry(self.geometry)
        root.attributes("-topmost", self.always_on_top)
        root.configure(bg="#0d0d14")
        root.overrideredirect(False)

        status_label = tk.Label(root, text="SLEEP", fg="#ffe680", bg="#0d0d14", font=("Segoe UI", 18, "bold"))
        status_label.pack(anchor="w", padx=12, pady=(10, 0))
        subtitle_label = tk.Label(
            root,
            text="En espera",
            fg="#f3f3f3",
            bg="#0d0d14",
            wraplength=390,
            justify="left",
            font=("Segoe UI", 11),
        )
        subtitle_label.pack(anchor="w", padx=12, pady=(6, 12))

        def pump() -> None:
            try:
                while True:
                    item = self._queue.get_nowait()
                    if item is None:
                        root.destroy()
                        return
                    status_label.config(text=item.status.upper())
                    subtitle_label.config(text=item.subtitle)
            except queue.Empty:
                pass
            root.after(120, pump)

        pump()
        root.mainloop()
