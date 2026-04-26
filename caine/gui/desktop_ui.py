import os
import sys

# Asegurar que el directorio raíz del proyecto está en sys.path
# para que 'from caine...' funcione correctamente.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import math
import time
import threading
import ctypes

try:
    # Forzar que Windows renderice la GUI a resolución nativa (arregla el "mitad de pantalla")
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import customtkinter as ctk

# Forzar tema oscuro y color rojo (aunque personalizaremos los colores)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class CaineDesktopUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de ventana: Segundo Escritorio (debajo de todas las apps)
        self.title("CAINE - Central AI and Network Engine")
        self.attributes("-fullscreen", True)
        # NO usar -topmost: queremos ser el desktop, las apps abren ENCIMA de nosotros
        
        # Anclar la ventana al fondo de la pila Z (como el wallpaper de Windows)
        # Esto se hace después de que Tk asigne el handle de ventana
        self.after(200, self._pin_as_desktop_layer)
        
        # Paleta de colores (Roja y Negra, diseño técnico y minimalista)
        self.configure(fg_color="#050505")
        self._mini_mode = False  # Comienza en modo escritorio completo
        
        # --- LIENZO GLOBAL (AURORAS Y ORBE) ---
        # El canvas de fondo ocupa el 100% de la ventana
        self.bg_canvas = ctk.CTkCanvas(
            self, 
            bg="#050505", 
            highlightthickness=0
        )
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Guardar dimensiones actuales para dibujar
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()
        
        # Parámetros del orbe
        self.center_x = self.screen_w // 2
        self.center_y = self.screen_h // 2
        self.base_radius = 80
        self.current_radius = self.base_radius
        self.target_radius = self.base_radius
        
        # Elementos dinámicos del lienzo (Auroras y Orbe)
        self.aurora_lines = []
        # Aurora system: 18 bandas multicapa para profundidad y movimiento real
        # Cada banda tiene su propia fase, velocidad y paleta de color
        self.aurora_config = [
            # (fase_x, vel_x, fase_t, vel_t, y_base_ratio, amplitud, color_idx)
            # Capa inferior — rojos muy oscuros
            (0.0,   0.0010, 0.0,  0.18, 0.82, 80,  0),
            (1.2,   0.0015, 0.7,  0.22, 0.78, 100, 1),
            (2.4,   0.0008, 1.4,  0.15, 0.75, 120, 0),
            # Capa media — carmesíes y burdeos
            (0.5,   0.0018, 2.1,  0.28, 0.68, 140, 2),
            (1.7,   0.0012, 0.3,  0.20, 0.65, 130, 3),
            (3.0,   0.0020, 1.0,  0.32, 0.62, 150, 2),
            (0.9,   0.0014, 1.8,  0.25, 0.58, 120, 1),
            # Capa alta — más brillantes, magenta oscuro
            (2.1,   0.0022, 0.5,  0.35, 0.52, 160, 4),
            (0.3,   0.0016, 2.5,  0.28, 0.48, 140, 3),
            (1.5,   0.0019, 1.2,  0.40, 0.44, 180, 4),
            (2.8,   0.0011, 0.8,  0.22, 0.40, 150, 5),
            # Filamentos altos — delgados y brillantes
            (0.7,   0.0025, 3.0,  0.45, 0.35, 80,  5),
            (1.9,   0.0017, 1.6,  0.38, 0.30, 70,  4),
            (3.2,   0.0021, 0.2,  0.50, 0.26, 60,  5),
            # Resplandor de corona — muy difuso
            (0.1,   0.0009, 2.8,  0.12, 0.20, 200, 6),
            (1.3,   0.0013, 1.1,  0.18, 0.16, 180, 6),
            (2.6,   0.0007, 0.6,  0.14, 0.12, 160, 7),
            (0.8,   0.0011, 2.2,  0.16, 0.08, 140, 7),
        ]
        # Paleta de colores aurora: rojo sangre → carmesí → magenta oscuro → burdeos → corona violácea
        self.aurora_palette = [
            "#1A0000",  # 0 rojo muy oscuro
            "#2D0005",  # 1 rojo burdeos
            "#3D0010",  # 2 carmesí oscuro
            "#4A0020",  # 3 carmesí
            "#3A0030",  # 4 magenta oscuro
            "#2A0040",  # 5 violeta profundo
            "#1A0025",  # 6 corona, muy difuso
            "#0F0015",  # 7 negro violáceo
        ]
        self.aurora_lines = []
        for _ in self.aurora_config:
            line = self.bg_canvas.create_polygon(0, 0, 0, 0, fill="#110000", outline="", smooth=True)
            self.aurora_lines.append(line)
            
        self.core_circle = self.bg_canvas.create_oval(
            self.center_x - 30, self.center_y - 30,
            self.center_x + 30, self.center_y + 30,
            fill="#AA0000", outline=""
        )
        self.ring1 = self.bg_canvas.create_oval(
            self.center_x - self.base_radius, self.center_y - self.base_radius,
            self.center_x + self.base_radius, self.center_y + self.base_radius,
            outline="#FF2A2A", width=2
        )
        self.ring2 = self.bg_canvas.create_oval(
            self.center_x - self.base_radius - 15, self.center_y - self.base_radius - 15,
            self.center_x + self.base_radius + 15, self.center_y + self.base_radius + 15,
            outline="#550000", width=1, dash=(4, 4)
        )
        
        # --- CAPAS SUPERIORES (UI FLOTANTE) ---
        # Cabecera
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", height=60)
        self.header_frame.place(relx=0.5, y=30, anchor="n", relwidth=0.9)
        
        self.lbl_system = ctk.CTkLabel(
            self.header_frame, 
            text="SYSTEM: CAINE // OS.OVERRIDE_ACTIVE", 
            font=("Courier New", 16, "bold"),
            text_color="#FF2A2A"
        )
        self.lbl_system.pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(
            self.header_frame, 
            text="STATUS: ONLINE", 
            font=("Courier New", 16, "bold"),
            text_color="#FF2A2A"
        )
        self.lbl_status.pack(side="right")

        # Terminal de Logs / Status
        self.terminal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.terminal_frame.place(relx=0.5, rely=0.85, anchor="s", relwidth=0.8)
        
        self.log_text = ctk.CTkTextbox(
            self.terminal_frame, 
            height=120, 
            fg_color="#0A0A0A", 
            text_color="#FF4444",
            font=("Consolas", 14),
            border_color="#330000",
            border_width=1
        )
        self.log_text.pack(fill="x")
        self.log_text.insert("0.0", "> Secuencia de arranque completada.\n> Enlazando con protocolos C.A.I.N.E...\n")
        self.log_text.configure(state="disabled")

        # Se eliminó el botón de salida manual para respetar la inmersión del Segundo Escritorio.

        # Entrada de texto (Input manual)
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.place(relx=0.5, rely=0.95, anchor="s", relwidth=0.8)
        
        self.entry_cmd = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Ingresar comando manual...", 
            font=("Consolas", 14), 
            fg_color="#050505", 
            border_color="#330000",
            text_color="#FF2A2A"
        )
        self.entry_cmd.pack(side="left", fill="x", expand=True)
        self.entry_cmd.bind("<Return>", self.on_user_input)

        # Estado de la IA
        self.is_speaking = False
        
        # Conectar Voz
        try:
            from caine.core.voice_authority import VoiceAuthority
            self.voice = VoiceAuthority(ui_controller=self)
        except Exception as e:
            self.log(f"> Error cargando VoiceAuthority: {e}")
            self.voice = None

        # Cargar KERNEL de CAINE OS
        try:
            from caine.core.caine_os_kernel import CaineOSKernel
            self.kernel = CaineOSKernel(ui_controller=self)
            self.kernel.start()
        except Exception as e:
            self.log(f"> Error Crítico Cargando Kernel: {e}")
            self.kernel = None

        # Iniciar loop de animación
        self.animate_orb()
        
        # Simular el arranque dando la bienvenida
        self.after(1000, self.boot_sequence)
        
        # Iniciar Escucha de Micrófono
        self._start_mic_listener()

    def _start_mic_listener(self):
        """Inicia el hilo de escucha continua del micrófono."""
        self.mic_thread = threading.Thread(target=self._mic_listener_loop, daemon=True)
        self.mic_thread.start()

    def _mic_listener_loop(self):
        import speech_recognition as sr
        import sounddevice as sd
        import numpy as np
        
        recognizer = sr.Recognizer()
        samplerate = 16000
        duration = 5  # Grabar en bloques de 5 segundos
        
        self.log("> [MIC] Escucha activa iniciada (SoundDevice engine).")
        
        while True:
            try:
                if self.is_speaking:
                    time.sleep(1)
                    continue
                
                # Grabar audio bloqueando el hilo de escucha (pero no la GUI)
                audio_data = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1, dtype='int16')
                sd.wait()
                
                # Verificar si el volumen es suficientemente alto para ser habla
                rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
                if rms < 50:  # Umbral de silencio
                    continue
                    
                # Convertir a formato de SpeechRecognition
                audio_bytes = audio_data.tobytes()
                sr_audio = sr.AudioData(audio_bytes, samplerate, 2)
                
                # Transcribir
                text = recognizer.recognize_google(sr_audio, language="es-ES")
                if text:
                    self.log(f"[VOZ DETECTADA]: {text}")
                    if self.kernel:
                        self.kernel.process_input(text)
            except sr.UnknownValueError:
                # No se entendió nada, ignorar
                pass
            except Exception as e:
                time.sleep(2)

    def on_user_input(self, event):
        text = self.entry_cmd.get().strip()
        if text and self.kernel:
            self.entry_cmd.delete(0, "end")
            # Enviar al kernel de forma asíncrona para no bloquear GUI
            import threading
            threading.Thread(target=self.kernel.process_input, args=(text,), daemon=True).start()


    def _pin_as_desktop_layer(self):
        """Ancla CAINE al fondo de la pila Z (como el escritorio de Windows)."""
        try:
            import ctypes
            HWND_BOTTOM = 1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            hwnd = self.winfo_id()
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
        except Exception as e:
            self.log(f"> [UI] No se pudo anclar al fondo: {e}")

    # ─────────────────────────────────────────────────────────────────
    # MODO ADAPTATIVO: Desktop ↔ Mini Widget
    # ─────────────────────────────────────────────────────────────────

    def step_back_for_app(self, delay_ms: int = 2500):
        """
        Lanzada cuando el kernel va a abrir una app.
        Espera `delay_ms` ms para que la app arranque,
        luego detecta si está en fullscreen y adapta CAINE.
        """
        # Darle tiempo a la app para que cargue y tome el foco
        self.after(delay_ms, self._detect_and_adapt)

    def _is_any_window_fullscreen(self) -> bool:
        """Detecta si alguna ventana externa cubre toda la pantalla."""
        try:
            import ctypes
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)   # ancho real de pantalla
            sh = user32.GetSystemMetrics(1)   # alto real de pantalla
            my_hwnd = self.winfo_id()

            # Recorrer ventanas visibles con EnumWindows
            found_fs = [False]
            RECT = ctypes.wintypes.RECT

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            def _cb(hwnd, _):
                if hwnd == my_hwnd:
                    return True  # ignorar nuestra propia ventana
                if not user32.IsWindowVisible(hwnd):
                    return True
                r = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                w = r.right - r.left
                h = r.bottom - r.top
                # Consideramos "fullscreen" si cubre >=95% de la pantalla
                if w >= sw * 0.95 and h >= sh * 0.95:
                    found_fs[0] = True
                    return False  # dejar de iterar
                return True

            user32.EnumWindows(_cb, 0)
            return found_fs[0]
        except Exception:
            return False

    def _detect_and_adapt(self):
        """Decide si ir a mini-mode o quedarse como escritorio."""
        if self._is_any_window_fullscreen():
            self._enter_mini_mode()
        # Si no hay fullscreen, CAINE ya está de fondo — no hace falta nada

    def _enter_mini_mode(self):
        """CAINE se convierte en un widget flotante pequeño en la esquina superior izquierda."""
        self._mini_mode = True
        try:
            self.attributes("-fullscreen", False)
            # Tamaño mini: 320 x 180, esquina superior izquierda
            self.geometry("320x180+0+0")
            self.attributes("-topmost", True)      # visible sobre la app fullscreen
            self.attributes("-alpha", 0.90)         # ligera transparencia para no molestar
            # Ocultar paneles grandes
            self.terminal_frame.place_forget()
            self.input_frame.place_forget()
            self.header_frame.place_forget()
            # Reposicionar el orbe pequeño centrado
            self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.log(f"> [MINI] Modo compacto activo")
        except Exception as e:
            self.log(f"> [MINI] Error: {e}")
        # Iniciar monitor de salida del fullscreen
        self._start_fullscreen_monitor()

    def _start_fullscreen_monitor(self):
        """Hilo que vigila cuándo el fullscreen desaparece para restaurar CAINE."""
        def _monitor():
            import time as _time
            _time.sleep(2)  # esperar que la app se establezca
            while getattr(self, '_mini_mode', False):
                _time.sleep(2)
                try:
                    if not self._is_any_window_fullscreen():
                        # Ya no hay fullscreen — restaurar en el hilo de Tk
                        self.after(0, self._restore_desktop_mode)
                        break
                except Exception:
                    break
        import threading
        threading.Thread(target=_monitor, daemon=True).start()

    def _restore_desktop_mode(self):
        """Vuelve a modo escritorio completo."""
        self._mini_mode = False
        try:
            self.attributes("-topmost", False)
            self.attributes("-alpha", 1.0)
            self.attributes("-fullscreen", True)
            # Restaurar paneles
            self.header_frame.place(relx=0.5, y=30, anchor="n", relwidth=0.9)
            self.terminal_frame.place(relx=0.5, rely=0.85, anchor="s", relwidth=0.8)
            self.input_frame.place(relx=0.5, rely=0.95, anchor="s", relwidth=0.8)
            self.after(300, self._pin_as_desktop_layer)
            self.log("> [DESKTOP] Modo escritorio restaurado.")
        except Exception as e:
            self.log(f"> [DESKTOP] Error restaurando: {e}")

    def _restore_desktop_layer(self):
        """Alias de compatibilidad — redirige a _restore_desktop_mode."""
        self._restore_desktop_mode()

    def boot_sequence(self):
        # Emitir mensaje inicial a través de la voz instanciada
        msg = "Sistema Caine cargado. Operativo en el segundo escritorio. Esperando instrucciones de control."
        if self.voice:
            self.voice.speak_async(msg)
        else:
            self.log(f"> {msg}")

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def set_speaking(self, state: bool):
        """Activa o desactiva la ondulación del orbe."""
        self.is_speaking = state

    def animate_orb(self):
        """Anima el orbe de sonido iterativamente y las auroras de fondo."""
        t = time.time()
        
        # --- ANIMAR AURORAS BOREALES ---
        if hasattr(self, 'screen_w') and hasattr(self, 'screen_h'):
            w, h = self.screen_w, self.screen_h
            SEGMENTS = 28  # más segmentos = curvas más suaves

            for idx, (cfg, line) in enumerate(zip(self.aurora_config, self.aurora_lines)):
                px, vx, pt, vt, y_base_r, amp, color_idx = cfg

                # Base Y de esta banda (repartida en la mitad superior de la pantalla)
                y_base = h * y_base_r

                # Puntos del polígono: abajo-izquierda → arco superior → abajo-derecha
                pts = [0, h]  # esquina inferior izquierda

                for s in range(SEGMENTS + 1):
                    x = w * s / SEGMENTS
                    # Onda compuesta de 4 armónicos para movimiento orgánico complejo
                    a1 = math.sin(x * vx + t * vt + pt) * amp
                    a2 = math.cos(x * vx * 0.6 - t * vt * 0.7 + pt * 1.3) * amp * 0.5
                    a3 = math.sin(x * vx * 1.8 + t * vt * 1.4 - pt * 0.8) * amp * 0.25
                    a4 = math.cos(x * vx * 0.3 + t * vt * 0.4 + pt * 2.1) * amp * 0.15
                    # Respiración vertical: toda la banda sube/baja lentamente
                    breathe = math.sin(t * 0.11 + idx * 0.4) * 30
                    y = y_base + a1 + a2 + a3 + a4 + breathe
                    pts.extend([x, y])

                pts.extend([w, h])  # esquina inferior derecha

                color = self.aurora_palette[color_idx % len(self.aurora_palette)]
                self.bg_canvas.itemconfig(line, fill=color)
                self.bg_canvas.coords(line, *pts)

        # --- ANIMAR ORBE ---
        if self.is_speaking:
            import random
            noise = random.randint(-20, 40)
            self.target_radius = self.base_radius + 20 + noise
            core_size = 30 + random.randint(0, 15)
        else:
            self.target_radius = self.base_radius + math.sin(t * 2) * 5
            core_size = 30

        self.current_radius += (self.target_radius - self.current_radius) * 0.2
        r = self.current_radius
        
        # Actualizar anillo principal
        self.bg_canvas.coords(
            self.ring1,
            self.center_x - r, self.center_y - r,
            self.center_x + r, self.center_y + r
        )
        
        # Actualizar anillo secundario
        r2 = r + 15 + math.cos(t * 3) * 10
        self.bg_canvas.coords(
            self.ring2,
            self.center_x - r2, self.center_y - r2,
            self.center_x + r2, self.center_y + r2
        )
        
        # Actualizar núcleo
        if not hasattr(self, '_core_size'):
            self._core_size = 30
        self._core_size += (core_size - self._core_size) * 0.3
        c = self._core_size
        self.bg_canvas.coords(
            self.core_circle,
            self.center_x - c, self.center_y - c,
            self.center_x + c, self.center_y + c
        )

        self.after(33, self.animate_orb)

if __name__ == "__main__":
    app = CaineDesktopUI()
    app.mainloop()
