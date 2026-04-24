"""Overlay y terminal visual de la entidad CAINE."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import tkinter as tk

from PIL import Image, ImageTk

from caine.state import CaineStatus, StateSnapshot


@dataclass(slots=True)
class OverlayEvent:
    kind: str
    text: str


class CaineAvatarOverlay:
    """Overlay ligero con avatar, subtitulos y terminal opcional."""

    def __init__(
        self,
        open_chat_terminal: bool = True,
        avatar_dir: Path | None = None,
        overlay_always_on_top: bool = False,
        terminal_always_on_top: bool = False,
        hide_when_idle: bool = True,
    ) -> None:
        self.open_chat_terminal = open_chat_terminal
        self.avatar_dir = Path(avatar_dir) if avatar_dir else None
        self.overlay_always_on_top = overlay_always_on_top
        self.terminal_always_on_top = terminal_always_on_top
        self.hide_when_idle = hide_when_idle
        self._events: queue.Queue[OverlayEvent | None] = queue.Queue()
        self._user_messages: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="CaineAvatarOverlay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._events.put(None)

    def set_status(self, text: str) -> None:
        self._events.put(OverlayEvent("status", text))

    def show_message(self, text: str) -> None:
        self._events.put(OverlayEvent("message", text))

    def add_chat_line(self, speaker: str, text: str) -> None:
        self._events.put(OverlayEvent("chat", f"{speaker}: {text}"))

    def set_avatar_state(self, state: str) -> None:
        self._events.put(OverlayEvent("avatar_state", state))

    def set_mic_state(self, listening: bool) -> None:
        self._events.put(OverlayEvent("mic", "listening" if listening else "idle"))

    def apply_snapshot(self, snapshot: StateSnapshot) -> None:
        self._events.put(OverlayEvent("snapshot", f"{snapshot.status.value}|{snapshot.subtitle}"))

    def get_user_message_nowait(self) -> str | None:
        try:
            return self._user_messages.get_nowait()
        except queue.Empty:
            return None

    def _run(self) -> None:
        root = tk.Tk()
        root.withdraw()

        # Configuración de Temas y Estética
        theme = {
            "bg": "#0a0b1e",          # Azul muy oscuro casi negro
            "surface": "#161b33",     # Superficie de tarjetas
            "surface_alt": "#0f1225", # Chat background
            "accent": "#4dffeb",      # Cyan neón
            "accent_dim": "#2d9d91",
            "accent2": "#ff007c",     # Rosa neón (teatral)
            "text": "#ffffff",
            "text_muted": "#a0a5cc",
            "border": "#2c3154",
            "shadow": "#050610",
            "success": "#00ff88",
            "warning": "#ffcc00",
        }

        terminal = tk.Toplevel(root)
        terminal.title("CAINE - Digital Circus Master Control")
        
        # Tamaño inicial y límites
        win_w, win_h = 960, 720
        terminal.geometry(f"{win_w}x{win_h}+100+100")
        terminal.minsize(800, 600)
        terminal.attributes("-topmost", self.terminal_always_on_top)
        terminal.configure(bg=theme["bg"])
        terminal.protocol("WM_DELETE_WINDOW", lambda: self.stop())

        # Marco principal (Contenedor con borde neón)
        main_container = tk.Frame(terminal, bg=theme["bg"], padx=2, pady=2)
        main_container.pack(fill="both", expand=True)
        
        outer_border = tk.Frame(main_container, bg=theme["border"], highlightthickness=1, highlightbackground=theme["accent"])
        outer_border.pack(fill="both", expand=True)

        inner_shell = tk.Frame(outer_border, bg=theme["bg"])
        inner_shell.pack(fill="both", expand=True, padx=4, pady=4)

        # --- SECCIÓN SUPERIOR: HEADER ---
        header_frame = tk.Frame(inner_shell, bg=theme["surface"], height=140)
        header_frame.pack(fill="x", side="top", padx=10, pady=10)
        header_frame.pack_propagate(False)

        avatar_container = tk.Frame(header_frame, bg=theme["surface"], width=120)
        avatar_container.pack(side="left", fill="y", padx=(15, 15))

        avatar_label = tk.Label(avatar_container, bg=theme["surface"])
        avatar_label.pack(expand=True)

        info_frame = tk.Frame(header_frame, bg=theme["surface"])
        info_frame.pack(side="left", fill="both", expand=True, pady=15)

        # Badge y Título
        badge_frame = tk.Frame(info_frame, bg=theme["surface"])
        badge_frame.pack(anchor="w")
        
        badge_label = tk.Label(badge_frame, text="ENTITY: CAINE", fg=theme["bg"], bg=theme["accent"], 
                              font=("Courier New", 9, "bold"), padx=8, pady=2)
        badge_label.pack(side="left")

        status_label = tk.Label(info_frame, text="SYSTEM INITIALIZING...", fg=theme["accent"], bg=theme["surface"], 
                                font=("Segoe UI Variable", 18, "bold"), anchor="w")
        status_label.pack(fill="x", pady=(5, 0))

        message_label = tk.Label(info_frame, text="Stand by for digital showmanship.", fg=theme["text_muted"], 
                                 bg=theme["surface"], font=("Segoe UI", 10, "italic"), anchor="w", wraplength=500)
        message_label.pack(fill="x")

        # --- SECCIÓN INFERIOR: CONTROLES (Empaquetar antes para reservar espacio) ---
        footer_frame = tk.Frame(inner_shell, bg=theme["bg"])
        footer_frame.pack(fill="x", side="bottom", padx=10, pady=(0, 10))

        # --- SECCIÓN MEDIA: CHAT (Expandible en el centro) ---
        chat_container = tk.Frame(inner_shell, bg=theme["surface_alt"], highlightthickness=1, highlightbackground=theme["border"])
        chat_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        transcript = tk.Text(chat_container, bg=theme["surface_alt"], fg=theme["text"], 
                             insertbackground=theme["accent"], wrap="word", relief="flat", 
                             borderwidth=0, padx=15, pady=15, font=("Cascadia Code", 11))
        
        scrollbar = tk.Scrollbar(chat_container, command=transcript.yview, bg=theme["surface_alt"])
        transcript.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        transcript.pack(fill="both", expand=True)
        
        transcript.insert("end", "[SYSTEM] Welcome to The Amazing Digital Circus Desktop Layer.\n")
        transcript.insert("end", "CAINE: Greetings! I am ready for the show.\n\n")
        transcript.config(state="disabled")

        # El footer_frame ya fue empaquetado arriba para reservar el fondo.

        # Input box con diseño moderno
        entry_container = tk.Frame(footer_frame, bg=theme["surface"], highlightthickness=1, highlightbackground=theme["border"])
        entry_container.pack(fill="x", pady=(0, 10))

        entry = tk.Entry(entry_container, bg=theme["surface"], fg=theme["text"], 
                         insertbackground=theme["accent"], relief="flat", borderwidth=0, 
                         font=("Segoe UI", 12), highlightthickness=0)
        entry.pack(side="left", fill="x", expand=True, padx=15, pady=12)

        def send_message(_: object | None = None) -> None:
            text = entry.get().strip()
            if text:
                entry.delete(0, "end")
                self._append_chat(transcript, f"LIN >> {text}\n")
                self._user_messages.put(text)

        entry.bind("<Return>", send_message)

        # Botonera
        btn_bar = tk.Frame(footer_frame, bg=theme["bg"])
        btn_bar.pack(fill="x")

        def create_btn(parent, text, cmd, color, fg="#ffffff"):
            return tk.Button(parent, text=text, command=cmd, bg=color, fg=fg, 
                            activebackground=theme["accent"], relief="flat", borderwidth=0,
                            font=("Segoe UI Variable", 10, "bold"), padx=20, pady=8, cursor="hand2")

        send_btn = create_btn(btn_bar, "ENVIAR ACTO", send_message, theme["accent"], theme["bg"])
        send_btn.pack(side="left", padx=(0, 10))

        mic_listening = {"active": False}
        def on_mic_click() -> None:
            if mic_listening["active"]: return
            mic_listening["active"] = True
            mic_btn.config(text="ESCUCHANDO...", state="disabled", bg=theme["success"])
            self._user_messages.put("__MIC__")

        mic_btn = create_btn(btn_bar, "HABLAR", on_mic_click, theme["accent2"])
        mic_btn.pack(side="left", padx=(0, 10))

        # Botones de estado (Derecha)
        tk.Frame(btn_bar, bg=theme["bg"]).pack(side="left", expand=True) # Spacer

        create_btn(btn_bar, "DORMIR", lambda: self._user_messages.put("__SLEEP__"), theme["surface"]).pack(side="right", padx=(5, 0))
        create_btn(btn_bar, "MUTE", lambda: self._user_messages.put("__MUTE__"), theme["surface"]).pack(side="right", padx=(5, 0))
        create_btn(btn_bar, "VISTAZO", lambda: self._user_messages.put("__OBSERVE__"), theme["surface"]).pack(side="right", padx=(5, 0))

        # --- LÓGICA DE ANIMACIÓN Y ACTUALIZACIÓN ---
        avatar_images = self._load_avatar_states((110, 110))
        current_avatar_state = {"value": "sleep"}
        pulse = {"value": 0}

        def set_avatar_image(state: str) -> None:
            current_avatar_state["value"] = state
            img = avatar_images.get(state) or avatar_images.get("idle")
            if img:
                avatar_label.configure(image=img)
                avatar_label.image = img

        set_avatar_image("sleep")

        def animate() -> None:
            pulse["value"] = (pulse["value"] + 1) % 20
            state = current_avatar_state["value"]
            border_color = theme["border"]
            
            if state == "listening": border_color = theme["success"] if pulse["value"] < 10 else theme["accent"]
            elif state == "thinking": border_color = theme["accent"] if pulse["value"] < 10 else theme["accent_dim"]
            elif state in ["speaking", "excited"]: border_color = theme["accent2"] if pulse["value"] < 10 else theme["warning"]
            elif state == "acting": border_color = theme["accent2"]
            elif state == "observing": border_color = theme["accent"]
            
            outer_border.configure(highlightbackground=border_color)
            terminal.after(150, animate)

        def pump() -> None:
            try:
                while True:
                    event = self._events.get_nowait()
                    if event is None: root.destroy(); return
                    
                    if event.kind == "status": status_label.config(text=event.text.upper())
                    elif event.kind == "message": message_label.config(text=event.text)
                    elif event.kind == "chat": self._append_chat(transcript, event.text + "\n")
                    elif event.kind == "avatar_state": set_avatar_image(event.text)
                    elif event.kind == "snapshot":
                        raw_state, subtitle = event.text.split("|", 1)
                        labels = {
                            CaineStatus.SLEEP.value: "SLEEPING IN WINGS",
                            CaineStatus.LISTENING.value: "AWAITING COMMAND",
                            CaineStatus.THINKING.value: "ORCHESTRATING...",
                            CaineStatus.SPEAKING.value: "PERFORMING VOICE",
                            CaineStatus.OBSERVING.value: "WATCHING THE SHOW",
                            CaineStatus.EXCITED.value: "EUPHORIC STATE",
                        }
                        status_label.config(text=labels.get(raw_state, "ACTING").upper())
                        message_label.config(text=subtitle)
                        set_avatar_image(raw_state)
                    elif event.kind == "mic":
                        listening = event.text == "listening"
                        if not listening: mic_listening["active"] = False
                        mic_btn.config(
                            text="ESCUCHANDO..." if listening else "HABLAR",
                            state="disabled" if listening else "normal",
                            bg=theme["success"] if listening else theme["accent2"]
                        )
                        if listening: set_avatar_image("listening")
            except queue.Empty: pass
            root.after(100, pump)

        animate()
        pump()
        root.mainloop()

    def _append_chat(self, transcript: tk.Text, text: str) -> None:
        transcript.config(state="normal")
        transcript.insert("end", text)
        transcript.see("end")
        transcript.config(state="disabled")

    def _load_avatar_states(self, size: tuple[int, int]) -> dict[str, ImageTk.PhotoImage]:
        if self.avatar_dir is None or not self.avatar_dir.exists(): return {}
        candidates = []
        for pat in ("*.png", "*.jpg", "*.jpeg"): candidates.extend(sorted(self.avatar_dir.glob(pat)))
        if not candidates: return {}
        
        state_map = {s: None for s in ["sleep", "idle", "listening", "thinking", "speaking", "acting", "observing", "excited"]}
        for cand in candidates:
            name = cand.stem.lower()
            for s in state_map:
                if state_map[s] is None and s in name:
                    state_map[s] = cand
                    break
        
        fallback = candidates[0]
        images: dict[str, ImageTk.PhotoImage] = {}
        for s, p in state_map.items():
            img = Image.open(p or fallback).convert("RGBA")
            img.thumbnail(size)
            images[s] = ImageTk.PhotoImage(img)
        return images
