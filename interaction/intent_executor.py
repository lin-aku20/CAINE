"""Enrutador de intenciones de IA hacia herramientas de bajo nivel."""

import json
import logging
from typing import Any

from interaction.app_launcher import AppLauncher
from interaction.window_controller import WindowController
from interaction.system_controller import SystemController
from interaction.keyboard_controller import KeyboardController
from interaction.mouse_controller import MouseController

class IntentExecutor:
    """Recibe la interpretacion JSON del LLM y ejecuta la accion."""

    def __init__(
        self, 
        launcher: AppLauncher, 
        windows: WindowController, 
        system: SystemController,
        keyboard: KeyboardController,
        mouse: MouseController
    ) -> None:
        self.launcher = launcher
        self.windows = windows
        self.system = system
        self.keyboard = keyboard
        self.mouse = mouse
        self.logger = logging.getLogger("caine.intent_executor")
        
    def execute_json(self, raw_json: str) -> str:
        try:
            data = json.loads(raw_json)
            action = data.get("action", "")
            target = data.get("target", "")
            
            if action == "open_app":
                res = self.launcher.launch(target)
                return res.message
            elif action == "open_website":
                res = self.launcher.open_website(target)
                return res.message
            elif action == "focus_window":
                success = self.windows.focus_window(target)
                return f"Ventana '{target}' enfocada con exito." if success else f"No se pudo enfocar '{target}'."
            elif action == "minimize_window":
                success = self.windows.minimize_window(target)
                return f"Ventana minimizada." if success else "No se pudo minimizar."
            elif action == "volume_up":
                return self.system.volume_up()
            elif action == "volume_down":
                return self.system.volume_down()
            elif action == "volume_mute":
                return self.system.volume_mute()
            elif action == "type_text":
                return self.keyboard.type_text(target)
                
            return f"Intencion '{action}' no soportada aun."
        except json.JSONDecodeError:
            self.logger.warning("El LLM no devolvio un JSON valido: %s", raw_json)
            return "El formato de intencion era invalido."
        except Exception as e:
            self.logger.error("Error ejecutando intencion: %s", e)
            return f"Fallo al ejecutar accion: {e}"
