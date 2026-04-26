"""
CAINE OS Kernel — Núcleo unificado de inteligencia.

Conecta todas las capacidades del CAINE original al Segundo Escritorio:
- IntentParser (Tool Calling rápido)
- ActionRouter (Acciones físicas del sistema)
- SystemActionRouter (Control del OS: apps, shell, volumen, etc.)
- HumanController (Mouse, teclado, ventanas)
- CaineBrain (LLM con streaming y tool calling)
- ConversationMemory + LongTermMemoryStore
- ScreenAwareness (contexto de pantalla activa)
- IntentRouter (clasificación de categorías)
"""
import threading
import time
import logging

logging.basicConfig(level=logging.WARNING)


class CaineOSKernel:
    """
    Núcleo unificado de CAINE OS.
    Inicializa robustamente todos los subsistemas del CAINE 1 original
    y los hace accesibles desde la nueva interfaz visual.
    """

    def __init__(self, ui_controller):
        self.ui = ui_controller
        self.logger = logging.getLogger("CAINE.Kernel")
        self._is_running = False

        # Inicialización defensiva — cada módulo falla solo (no bloquea el resto)
        self.config = None
        self.intent_parser = None
        self.intent_router = None
        self.action_router = None
        self.system_actions = None
        self.human = None
        self.brain = None
        self.memory_store = None
        self.awareness = None

        self.ui.log("> [KERNEL] Iniciando protocolos CAINE OS...")

        self._init_config()
        self._init_human()
        self._init_system_actions()
        self._init_memory()
        self._init_intent_parser()
        self._init_intent_router()
        self._init_action_router()
        self._init_awareness()
        self._init_brain()

    # ─────────────────────────────────────────────
    # SUBSISTEMAS
    # ─────────────────────────────────────────────

    def _init_config(self):
        try:
            from caine.config import CaineConfig
            self.config = CaineConfig.from_yaml()
            self.ui.log("> [KERNEL] Configuración central cargada.")
        except Exception as e:
            self.ui.log(f"> [KERNEL] Config no disponible, usando defaults ({e}).")
            # Crear configuración mínima funcional
            try:
                from caine.config import ActionSettings
                self.config = type('MinimalConfig', (), {
                    'actions': ActionSettings(),
                    'memory': type('M', (), {'max_context_items': 5, 'long_term_file': None, 'legacy_json_file': None, 'conversation_limit': 12})(),
                    'awareness': type('A', (), {'screenshots_dir': 'screenshots', 'capture_screenshots': False})(),
                })()
            except Exception:
                self.config = None

    def _init_human(self):
        try:
            from caine.human_control import HumanController
            self.human = HumanController()
            self.ui.log("> [KERNEL] Control físico (Mouse/Teclado) en línea.")
        except Exception as e:
            self.ui.log(f"> [KERNEL] HumanController no disponible ({e}).")

    def _init_system_actions(self):
        try:
            from interaction.system_actions import SystemActionRouter
            action_config = self.config.actions if self.config else None
            if action_config is None:
                from caine.config import ActionSettings
                action_config = ActionSettings()
            self.system_actions = SystemActionRouter(action_config)
            self.ui.log("> [KERNEL] Router de Sistema (Apps/Shell/OS) en línea.")
        except Exception as e:
            self.ui.log(f"> [KERNEL] SystemActionRouter no disponible ({e}).")

    def _init_memory(self):
        try:
            from memory.long_term_memory import LongTermMemoryStore
            self.memory_store = LongTermMemoryStore()
            self.ui.log("> [KERNEL] Memoria a largo plazo conectada.")
        except Exception as e:
            self.ui.log(f"> [KERNEL] Memoria no disponible ({e}).")

    def _init_intent_parser(self):
        try:
            from caine.intent_parser import IntentParser
            self.intent_parser = IntentParser()
            self.ui.log("> [KERNEL] Parser de Intenciones (Tool Calling) en línea.")
        except Exception as e:
            self.intent_parser = None
            self.ui.log(f"> [KERNEL] IntentParser no disponible ({e}).")

    def _init_intent_router(self):
        try:
            from caine.intent_router import IntentRouter
            self.intent_router = IntentRouter()
            self.ui.log("> [KERNEL] Router de Categorías en línea.")
        except Exception as e:
            self.intent_router = None
            self.ui.log(f"> [KERNEL] IntentRouter no disponible ({e}).")

    def _init_action_router(self):
        try:
            from caine.action_router import ActionRouter
            if self.system_actions and self.human:
                self.action_router = ActionRouter(self.system_actions, self.human)
            elif self.system_actions:
                from caine.human_control import HumanController
                self.action_router = ActionRouter(self.system_actions, HumanController())
            else:
                raise RuntimeError("No hay SystemActionRouter para el ActionRouter.")
            self.ui.log("> [KERNEL] Enrutador de Acciones completo en línea.")
        except Exception as e:
            self.action_router = None
            self.ui.log(f"> [KERNEL] ActionRouter en modo degradado ({e}).")

    def _init_awareness(self):
        try:
            from caine.screen_awareness import ScreenAwareness
            screenshots_dir = getattr(getattr(self.config, 'awareness', None), 'screenshots_dir', 'screenshots')
            capture = getattr(getattr(self.config, 'awareness', None), 'capture_screenshots', False)
            self.awareness = ScreenAwareness(screenshots_dir=screenshots_dir, capture_screenshots=capture)
            self.ui.log("> [KERNEL] Conciencia de Pantalla activa.")
        except Exception as e:
            self.awareness = None
            self.ui.log(f"> [KERNEL] ScreenAwareness no disponible ({e}).")

    def _init_brain(self):
        try:
            from brain.caine_brain import CaineBrain
            from memory.conversation_memory import ConversationMemory
            from personality.loader import PersonalityLoader

            memory = ConversationMemory()
            personality = PersonalityLoader()

            # Leer configuración de Ollama desde config si está disponible
            ollama = getattr(self.config, 'ollama', None)
            base_url = getattr(ollama, 'base_url', 'http://localhost:11434/v1')
            api_key = getattr(ollama, 'api_key', 'ollama')
            timeout = getattr(ollama, 'timeout_seconds', 60)

            # Detectar automáticamente el mejor modelo disponible en Ollama
            primary_model = self._detect_best_model(base_url)

            self.brain = CaineBrain(
                base_url=base_url,
                primary_model=primary_model,
                fallback_model=primary_model,
                api_key=api_key,
                timeout_seconds=timeout,
                personality_loader=personality,
                conversation_memory=memory,
                tool_executor=self._execute_tool_call
            )
            self.ui.log(f"> [KERNEL] LLM conectado → modelo: {primary_model}")
        except Exception as e:
            self.brain = None
            self.ui.log(f"> [KERNEL] LLM no conectado: {e}")

    def _detect_best_model(self, base_url: str) -> str:
        """Auto-detecta el mejor modelo disponible en Ollama."""
        try:
            import requests
            # La API de tags está en el root, no en /v1
            tags_url = base_url.replace("/v1", "") + "/api/tags"
            r = requests.get(tags_url, timeout=3)
            if r.status_code == 200:
                models = [m['name'] for m in r.json().get('models', [])]
                # Preferencia: caine > llama3 > qwen > cualquiera
                for preferred in ['caine:latest', 'llama3:latest', 'qwen2.5:7b', 'qwen3.5:latest']:
                    if preferred in models:
                        return preferred
                if models:
                    return models[0]
        except Exception:
            pass
        return 'caine:latest'

    # ─────────────────────────────────────────────
    # CICLO DE VIDA
    # ─────────────────────────────────────────────

    def start(self):
        """Inicia el ciclo de procesamiento en un hilo separado."""
        self._is_running = True
        self.thread = threading.Thread(target=self._kernel_loop, daemon=True)
        self.thread.start()
        self.ui.log("> [KERNEL] ━━━ CAINE OS COMPLETAMENTE OPERATIVO ━━━")

    def stop(self):
        self._is_running = False

    def _kernel_loop(self):
        """Mantiene los sistemas de fondo vivos."""
        while self._is_running:
            time.sleep(1)

    # ─────────────────────────────────────────────
    # TOOL EXECUTOR (Bridge LLM → ActionRouter)
    # ─────────────────────────────────────────────

    def _execute_tool_call(self, accion: str, destino: str) -> str:
        """Callback invocado por CaineBrain cuando el modelo decide usar una herramienta nativa."""
        self.ui.log(f"> [TOOL CALL] {accion} → {destino}")

        action_map = {
            "llamar": "start_call",
            "hacer_llamada": "hacer_llamada",
            "terminar_llamada": "end_call",
            "enviar_mensaje": "send_message",
            "abrir_app": "open_app",
            "reproducir": "media_play",
            "pausar": "media_pause",
            "volumen_subir": "volume_up",
            "volumen_bajar": "volume_down",
            "volumen_silenciar": "volume_mute",
            "buscar_youtube": "youtube_search",
        }

        mapped_action = action_map.get(accion, accion)
        intent = {
            "action": mapped_action,
            "target": destino,
            "app": "discord" if accion in ["llamar", "terminar_llamada", "enviar_mensaje"] else "",
            "content": "",
            "tool_call": "control_sistema"
        }

        try:
            if self.action_router:
                result = self.action_router.handle(intent)
                msg = getattr(result, "message", str(result))
                self.ui.log(f"> [TOOL RESULT] {msg}")
                return msg
            else:
                return "ActionRouter no disponible."
        except Exception as e:
            self.ui.log(f"> [TOOL ERROR] {e}")
            return f"Error ejecutando la acción: {e}"

    # ─────────────────────────────────────────────
    # PROCESAMIENTO DE INPUT (Voz / Teclado)
    # ─────────────────────────────────────────────

    def process_input(self, user_text: str):
        """Punto de entrada unificado para todos los comandos."""
        self.ui.log(f"[USUARIO]: {user_text}")

        # 1. IntentParser — Tool Calling rápido (llamadas, mensajes, apps, volumen, etc.)
        if self.intent_parser:
            parsed = self.intent_parser.parse_intent(user_text)
            if parsed and parsed.get("action") != "unknown":
                action = parsed.get("action")
                self.ui.log(f"> Ejecutando protocolo: {action}...")
                
                # Si va a abrir una app, bajar CAINE para que la app sea visible
                if action in ("open_app", "youtube_search") and hasattr(self.ui, "step_back_for_app"):
                    self.ui.after(0, lambda: self.ui.step_back_for_app(delay_ms=3000))
                
                try:
                    result = self.action_router.handle(parsed) if self.action_router else "Sin ActionRouter."
                    msg = getattr(result, "message", str(result))
                    # Guardar en memoria si está disponible
                    if self.memory_store:
                        try:
                            self.memory_store.maybe_store_fact(
                                user_text=user_text, assistant_text=msg, intent=action
                            )
                        except Exception:
                            pass
                    if self.ui.voice:
                        self.ui.voice.speak_async(msg)
                    else:
                        self.ui.log(f"> CAINE: {msg}")
                    return
                except Exception as e:
                    self.ui.log(f"> Fallo en protocolo {action}: {e}")
                    if self.ui.voice:
                        self.ui.voice.speak_async("Encontré un fallo ejecutando esa orden.")
                    return

        # 2. IntentRouter — Clasificación por categoría (como el CAINE 1 clásico)
        if self.intent_router and self.awareness:
            try:
                screen_ctx = self.awareness.get_active_context(include_screenshot=False)
                intent = self.intent_router.classify(user_text, active_app=screen_ctx.process_name)

                if intent.category == "accion_sistema" and self.system_actions:
                    cmd = (intent.command_text or "").removeprefix("/accion ").strip()
                    result = self.system_actions.handle_text_command(cmd)
                    msg = getattr(result, "message", str(result))
                    if self.ui.voice:
                        self.ui.voice.speak_async(msg)
                    else:
                        self.ui.log(f"> CAINE: {msg}")
                    return

                if intent.category == "desarrollo_web":
                    reply = "Puedo montar una web simple dentro del proyecto. Si quieres que la ejecute ahora mismo, dime 'hazlo'."
                    if self.ui.voice:
                        self.ui.voice.speak_async(reply)
                    return
            except Exception as e:
                self.ui.log(f"> IntentRouter falló: {e}")

        # 3. Respuesta Conversacional con LLM
        if self.brain:
            self.ui.log("> Procesando con LLM...")
            try:
                # Construir contexto de pantalla si está disponible
                extra_ctx = ""
                if self.awareness:
                    try:
                        ctx = self.awareness.get_active_context(include_screenshot=False)
                        if ctx.summary():
                            extra_ctx = f"Contexto de pantalla: {ctx.summary()}"
                    except Exception:
                        pass

                if self.memory_store:
                    try:
                        mem = self.memory_store.get_context_summary(query=user_text, limit=5)
                        if mem:
                            extra_ctx += f"\nMemoria relevante: {mem}"
                    except Exception:
                        pass

                reply = self.brain.send_message(user_text, extra_context=extra_ctx if extra_ctx else None)

                # Manejar tanto strings como generadores (streaming)
                if hasattr(reply, '__iter__') and not isinstance(reply, str):
                    full_reply = ""
                    for token in reply:
                        full_reply += token
                    reply = full_reply

                if self.memory_store:
                    try:
                        self.memory_store.maybe_store_fact(
                            user_text=user_text, assistant_text=reply, intent="conversacion"
                        )
                    except Exception:
                        pass

                if self.ui.voice:
                    self.ui.voice.speak_async(reply)
                else:
                    self.ui.log(f"> CAINE: {reply}")

            except Exception as e:
                self.ui.log(f"> Error LLM: {e}")
                if self.ui.voice:
                    self.ui.voice.speak_async("La red neuronal no responde en este momento.")
        else:
            fallback = "Sistema operativo activo. LLM no conectado."
            if self.ui.voice:
                self.ui.voice.speak_async(fallback)
            else:
                self.ui.log(f"> CAINE: {fallback}")
