import logging
import time
import pygetwindow as gw
from typing import Optional

from caine.core.action_result import ActionResult
from caine.human_control import HumanController
from caine.perception.desktop_vision import DesktopVisionAgent
import re

try:
    import pytesseract
except ImportError:
    pytesseract = None

class UniversalMessagingAgent:
    """Maneja el envío de mensajes universal para múltiples aplicaciones."""
    
    def __init__(self, human: HumanController):
        self.logger = logging.getLogger("caine.universal_messaging")
        self.human = human
        self.vision = DesktopVisionAgent()

    def _open_and_focus_app(self, app_name: str) -> bool:
        """Abre o enfoca la aplicación deseada."""
        self.logger.info("[UNIVERSAL_MSG] Abriendo/enfocando %s", app_name)
        # Intentar enfocar primero si ya está abierta
        windows = gw.getWindowsWithTitle(app_name.capitalize())
        if not windows:
            # Si no está abierta, usamos el human controller para abrirla via teclado
            self.human.press_hotkey('win')
            time.sleep(0.5)
            self.human.type_text(app_name)
            time.sleep(0.5)
            self.human.press_hotkey('enter')
            time.sleep(3.0) # Esperar a que abra
        else:
            win = windows[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning("[UNIVERSAL_MSG] Error activando ventana: %s", e)
                return False
        return True

    def open_chat(self, app: str, target: str) -> ActionResult:
        """Abre el chat con el usuario destino usando los atajos específicos de cada app."""
        if not self._open_and_focus_app(app):
            return ActionResult(False, f"No pude abrir o enfocar {app}.")
        
        app_lower = app.lower()
        self.logger.info("[UNIVERSAL_MSG] Buscando contacto '%s' en %s", target, app_lower)
        
        if app_lower == "discord":
            self.human.press_hotkey('ctrl', 'k')
            time.sleep(0.5)
        elif app_lower == "whatsapp":
            self.human.press_hotkey('ctrl', 'f')
            time.sleep(0.5)
        elif app_lower == "telegram":
            self.human.press_hotkey('ctrl', 'f')
            time.sleep(0.5)
        elif app_lower == "messenger":
            self.human.press_hotkey('ctrl', 'k')
            time.sleep(0.5)
        elif app_lower == "signal":
            self.human.press_hotkey('ctrl', 'n')
            time.sleep(0.5)
        else:
            # Fallback genérico: intentar CTRL+F
            self.human.press_hotkey('ctrl', 'f')
            time.sleep(0.5)

        self.human.type_text(target)
        time.sleep(1.0) # Esperar a que la app filtre los contactos
        self.human.press_hotkey('enter')
        time.sleep(0.8) # Esperar a que se abra el chat
        
        return ActionResult(True, f"Chat abierto con {target} en {app}")

    def send_message(self, app: str, target: str, content: str, phone: Optional[str] = None) -> ActionResult:
        """Flujo completo: open_chat -> verify (si aplica) -> type -> press_enter."""
        chat_result = self.open_chat(app, target)
        if not chat_result.success:
            return chat_result

        # Validación estricta de teléfono para WhatsApp
        if app.lower() == "whatsapp" and phone and pytesseract:
            self.logger.info("[UNIVERSAL_MSG] Validando teléfono en WhatsApp: %s", phone)
            
            try:
                # Normalizar el número esperado (solo dígitos y +)
                expected_phone = re.sub(r'[^\d+]', '', phone)
                
                time.sleep(1.0) # Esperar a que la UI se estabilice
                screen = self.vision.capture_screen(grayscale=True)
                text = pytesseract.image_to_string(screen).replace(" ", "").replace("-", "")
                
                if expected_phone not in text:
                    self.logger.info("[UNIVERSAL_MSG] Teléfono no encontrado a simple vista. Abriendo panel de perfil...")
                    # Hacer click en la cabecera del chat (centro-arriba) para abrir el perfil
                    import pyautogui
                    sw, sh = pyautogui.size()
                    pyautogui.click(int(sw * 0.5), int(sh * 0.1))
                    time.sleep(1.5)
                    
                    screen = self.vision.capture_screen(grayscale=True)
                    text = pytesseract.image_to_string(screen).replace(" ", "").replace("-", "")
                    
                    if expected_phone not in text:
                        self.logger.error("[UNIVERSAL_MSG] ALERTA DE SEGURIDAD: El contacto abierto no coincide con el teléfono %s.", expected_phone)
                        return ActionResult(False, f"Abortado por seguridad: El número de teléfono de {target} no coincide.")
                        
                self.logger.info("[UNIVERSAL_MSG] ✅ Teléfono %s verificado correctamente.", expected_phone)
            except Exception as e:
                self.logger.warning("[UNIVERSAL_MSG] ⚠️ Validación de teléfono omitida. OCR/Tesseract falló o no está instalado: %s", e)

        # Esperar a que el chat termine de cargar completamente
        time.sleep(2.5)

        if app.lower() == "whatsapp":
            self.logger.info("[UNIVERSAL_MSG] Buscando visualmente la caja de texto de WhatsApp...")
            
            # 1. Intentar reconocimiento visual con la nueva plantilla
            element = self.vision.find_icon("whatsapp_input", threshold=0.55, retries=3)
            
            if element:
                self.logger.info("[UNIVERSAL_MSG] Caja de texto encontrada visualmente (confianza: %.2f)", element.confidence)
                # Extraer coordenadas del bounding box y calcular el centro
                x, y, w, h = element.bounding_box
                center_x = x + w // 2
                center_y = y + h // 2
                
                # Hacer click un poco a la derecha del centro del icono para asegurar que entramos al campo de texto
                target_x = center_x + 50
                target_y = center_y
                self.human.move_mouse(target_x, target_y, duration=0.2)
                self.human.click(target_x, target_y)
                time.sleep(0.3)
            else:
                self.logger.warning("[UNIVERSAL_MSG] No se encontró la caja de texto visualmente. Usando fallback de navegación y click relativo.")
                # Fallback: Forzar el foco con navegación por teclado y click en 0.5, 0.92
                self.human.press_key("tab")
                time.sleep(0.2)
                self.human.press_key("tab")
                time.sleep(0.2)
                self.human.press_key("tab")
                time.sleep(0.2)
                self.human.click_relative(0.50, 0.92)
                time.sleep(0.3)

        self.logger.info("[UNIVERSAL_MSG] Escribiendo mensaje: '%s'", content)
        self.human.type_text(content)
        time.sleep(0.4)
        self.human.press_key('enter')
        
        return ActionResult(True, f"Mensaje enviado a {target} por {app}.")

    def make_call(self, app: str, target: str, content: str = "", phone: Optional[str] = None) -> ActionResult:
        """Inicia una llamada universal. Flujo: open_chat -> find_call_button -> click -> verify."""
        self.logger.info("[INTENT] hacer_llamada detectada")
        self.logger.info("[CALL] Abriendo %s", app.capitalize())
        
        chat_result = self.open_chat(app, target)
        if not chat_result.success:
            return chat_result

        self.logger.info("[CALL] Buscando contacto %s", target)
        
        time.sleep(2.5) # Esperar interfaz
        self.logger.info("[CALL] Chat confirmado")
        
        if app.lower() == "whatsapp":
            # --- FASE 1: DETECCIÓN DE CONTEXTO (CALL_OPTIONS_BUTTON) ---
            self.logger.info("[CALL] FASE 1 - Buscando CALL_OPTIONS_BUTTON (Apertura de menú)")
            call_options_btn = self.vision.find_icon("whatsapp_call_panel", threshold=0.6, retries=2)
            
            if call_options_btn:
                self.logger.info("[CALL] CALL_OPTIONS_BUTTON encontrado. Haciendo click...")
                x, y, w, h = call_options_btn.bounding_box
                cx, cy = x + w//2, y + h//2
                self.human.move_mouse(cx, cy, duration=0.2)
                self.human.click(cx, cy)
            else:
                self.logger.warning("[CALL] CALL_OPTIONS_BUTTON no detectado visualmente. Usando fallback superior derecho.")
                import pyautogui
                sw, sh = pyautogui.size()
                target_x = int(sw * 0.90)
                target_y = int(sh * 0.10)
                self.human.move_mouse(target_x, target_y, duration=0.3)
                self.human.click(target_x, target_y)

            # --- FASE 2: CONFIRMACIÓN VISUAL (ESTADO = CALL_MENU_OPEN) ---
            time.sleep(2.0)
            self.logger.info("[CALL] FASE 2 - Esperando aparición de panel flotante (ESTADO = CALL_MENU_OPEN)")

            # --- FASE 3/4: IDENTIFICACIÓN Y EJECUCIÓN (CALL_EXECUTION_BUTTON) ---
            self.logger.info("[CALL] FASE 3 - Buscando CALL_EXECUTION_BUTTON (Botón grande verde de Voz)")
            execution_btn = self.vision.find_icon("whatsapp_call_voice", threshold=0.65, retries=3)
            
            if execution_btn:
                self.logger.info("[CALL] FASE 4 - CALL_EXECUTION_BUTTON encontrado. Ejecutando llamada...")
                vx, vy, vw, vh = execution_btn.bounding_box
                vcx, vcy = vx + vw//2, vy + vh//2
                self.human.move_mouse(vcx, vcy, duration=0.2)
                self.human.click(vcx, vcy)
            else:
                self.logger.error("[CALL] REGLA ANTI-ERROR: CALL_EXECUTION_BUTTON no encontrado. El menú no era de llamada o la UI cambió.")
                return ActionResult(False, "No se pudo detectar el botón final de inicio de llamada (CALL_EXECUTION_BUTTON).")
        else:
            # Flujo genérico para otras apps (Discord, Signal)
            self.logger.info("[CALL] Buscando botón de llamada genérico...")
            call_btn = self.vision.find_icon("call_icon", threshold=0.55, retries=2)
            if not call_btn:
                call_btn = self.vision.find_icon("discord_call_icon", threshold=0.55, retries=2)
                
            if call_btn:
                self.logger.info("[CALL] Botón llamada encontrado (estrategia visual)")
                x, y, w, h = call_btn.bounding_box
                cx, cy = x + w//2, y + h//2
                self.human.move_mouse(cx, cy, duration=0.2)
                self.human.click(cx, cy)
            else:
                self.logger.warning("[CALL] Botón no detectado visualmente. Usando fallback inteligente.")
                if app.lower() == "discord":
                    self.human.press_hotkey('ctrl', 'shift', 'c')
                else:
                    import pyautogui
                    sw, sh = pyautogui.size()
                    target_x = int(sw * 0.90)
                    target_y = int(sh * 0.10)
                    self.human.move_mouse(target_x, target_y, duration=0.3)
                    self.human.click(target_x, target_y)
            time.sleep(2.0)

        self.logger.info("[CALL] Iniciando llamada")
        # Enviar mensaje opcional
        if content:
            self.logger.info("[CALL] Enviando mensaje adjunto: %s", content)
            self.human.type_text(content)
            time.sleep(0.3)
            self.human.press_key("enter")

        return ActionResult(True, f"Llamada iniciada con {target} en {app}.")
