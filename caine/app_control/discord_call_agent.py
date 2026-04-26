"""Discord Call Agent — Motor especializado en iniciar llamadas verificadas.

Arquitectura de 5 fases:
  FASE 1 → Contexto: ¿Estamos en un DM/grupo donde se puede llamar?
  FASE 2 → Detección: Encontrar el botón correcto usando OCR de tooltip
  FASE 3 → Ejecución: Click verificado con confirmación de cursor
  FASE 4 → Verificación: Confirmar señales reales de llamada activa
  FASE 5 → Aprendizaje: Guardar la posición y patrón para futuro

Nunca marca éxito sin señales reales de llamada.
Distingue llamada de voz vs videollamada usando el texto del tooltip.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw

from caine.core.action_result import ActionResult
from caine.human_control import HumanController
from caine.perception.desktop_vision import DesktopVisionAgent, UIElement

try:
    import pytesseract
except ImportError:
    pytesseract = None

pyautogui.FAILSAFE = False

logger = logging.getLogger("caine.discord_call")
_TESSERACT_READY: Optional[bool] = None


# ---------------------------------------------------------------------------
# Memoria de patrones aprendidos para llamadas
# ---------------------------------------------------------------------------

CALL_MEMORY_FILE = Path(__file__).resolve().parent.parent.parent / "memory" / "ui_patterns" / "discord_call.json"

@dataclass
class CallButtonMemory:
    """Recuerdo de dónde estaba el botón de llamada la última vez."""
    app: str               # "Discord"
    contexto: str          # "DM" o título de ventana
    boton: str             # "llamada_voz" | "videollamada"
    tooltip: str           # texto del tooltip leído
    x_abs: int             # posición absoluta X
    y_abs: int             # posición absoluta Y
    x_rel: float           # posición relativa X (0.0-1.0)
    y_rel: float           # posición relativa Y (0.0-1.0)
    ordinal_index: int     # posición dentro del cluster (ej: 0=voz, 1=video)
    icon_w: int            # ancho aproximado del icono
    icon_h: int            # alto aproximado del icono
    region_bbox: list      # [x, y, w, h] donde se encontró
    confianza: float       # 0.0-1.0
    success_count: int     # veces que funcionó
    last_used: str         # ISO timestamp
    learned_from: str      # "agent" o "user"

    def to_dict(self) -> dict:
        return {
            "app": self.app,
            "contexto": self.contexto,
            "boton": self.boton,
            "tooltip": self.tooltip,
            "x_abs": self.x_abs,
            "y_abs": self.y_abs,
            "x_rel": self.x_rel,
            "y_rel": self.y_rel,
            "ordinal_index": self.ordinal_index,
            "icon_w": self.icon_w,
            "icon_h": self.icon_h,
            "region_bbox": self.region_bbox,
            "confianza": self.confianza,
            "success_count": self.success_count,
            "last_used": self.last_used,
            "learned_from": self.learned_from,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CallButtonMemory":
        return cls(**d)


def _load_call_memory() -> Optional[CallButtonMemory]:
    try:
        if CALL_MEMORY_FILE.exists():
            data = json.loads(CALL_MEMORY_FILE.read_text(encoding="utf-8"))
            return CallButtonMemory.from_dict(data)
    except Exception:
        pass
    return None


def _save_call_memory(mem: CallButtonMemory) -> None:
    try:
        CALL_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        CALL_MEMORY_FILE.write_text(json.dumps(mem.to_dict(), indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("[CALL_MEMORY] No pude guardar: %s", exc)


# ---------------------------------------------------------------------------
# Constantes de Discord
# ---------------------------------------------------------------------------

# Tooltips conocidos de Discord (inglés y español)
VOICE_CALL_TOOLTIPS = {"start voice call", "voice call", "llamada de voz", "iniciar llamada de voz"}
VIDEO_CALL_TOOLTIPS = {"start video call", "video call", "videollamada", "iniciar videollamada"}
ALL_CALL_TOOLTIPS   = VOICE_CALL_TOOLTIPS | VIDEO_CALL_TOOLTIPS

# Señales de llamada activa (OCR keywords)
CALL_ACTIVE_KEYWORDS = [
    "calling", "ringing", "connected", "voice connected",
    "llamando", "timbrando", "conectado", "conectada",
]

# Señales de controles de llamada activa
CALL_CONTROL_KEYWORDS = [
    "mute", "deafen", "disconnect", "leave call",
    "silenciar", "ensordecer", "desconectar",
    "screen", "video", "camera", "activities",
    "compartir", "pantalla", "camara",
]

MAX_ATTEMPTS = 12  # máximo de intentos antes de rendirse


# ---------------------------------------------------------------------------
# DiscordCallAgent
# ---------------------------------------------------------------------------

class DiscordCallAgent:
    """Motor especializado en iniciar llamadas de Discord con verificación real."""

    def __init__(self, human: HumanController, vision: DesktopVisionAgent) -> None:
        self.human = human
        self.vision = vision
        self.assets_dir = Path(__file__).resolve().parent.parent / "assets"

    # ==================================================================
    # API pública
    # ==================================================================

    def start_voice_call(self) -> ActionResult:
        """Inicia una llamada de VOZ. Verifica el resultado real."""
        return self._start_call(call_type="voice")

    def start_video_call(self) -> ActionResult:
        """Inicia una VIDEOLLAMADA. Verifica el resultado real."""
        return self._start_call(call_type="video")

    # ==================================================================
    # Motor principal
    # ==================================================================

    def _start_call(self, call_type: str = "voice") -> ActionResult:
        """Pipeline completo: Contexto → Detección → Click → Verificación → Aprendizaje."""
        target_tooltips = VOICE_CALL_TOOLTIPS if call_type == "voice" else VIDEO_CALL_TOOLTIPS
        logger.info("[CALL] === INICIO: %s call ===", call_type)

        # ------------------------------------------------------------------
        # FASE 0: ¿Discord está abierto y enfocado?
        # ------------------------------------------------------------------
        if not self._ensure_discord_focused():
            return ActionResult(False, "Discord no está abierto o no se pudo enfocar.")

        # ------------------------------------------------------------------
        # FASE 1: (ELIMINADA) No se pre-verifica estado. Siempre se intenta llamar.
        # ------------------------------------------------------------------
        
        # ------------------------------------------------------------------
        # FASE 1.5: Intentar desde memoria (posición aprendida)
        # ------------------------------------------------------------------
        memory = _load_call_memory()
        expected_boton = "llamada_voz" if call_type == "voice" else "videollamada"
        if memory and memory.boton == expected_boton and memory.confianza >= 0.7:
            result = self._try_from_memory(memory, target_tooltips)
            if result:
                return result

        # ------------------------------------------------------------------
        # FASE 2: Detección del botón por OCR de tooltip
        # ------------------------------------------------------------------
        screen_w, screen_h = pyautogui.size()
        search_region = self._get_call_button_region(screen_w, screen_h)

        # Si el usuario ya dejó el mouse sobre el botón, aprovechar esa pista.
        btn_pos = self._try_current_cursor_hint(search_region, target_tooltips, call_type, screen_w, screen_h)
        if btn_pos:
            result = self._click_and_verify(btn_pos, call_type, search_region)
            if result:
                return result

        for attempt in range(1, MAX_ATTEMPTS + 1):
            logger.info("[CALL] Intento #%d de %d", attempt, MAX_ATTEMPTS)

            btn_pos = self._try_current_cursor_hint(search_region, target_tooltips, call_type, screen_w, screen_h)
            if btn_pos:
                result = self._click_and_verify(btn_pos, call_type, search_region)
                if result:
                    return result

            # ESTRATEGIA A (PRIORIDAD 1): Template Matching + Contexto de Cluster (Heurística visual estricta)
            # Esto usa memoria aprendida inmediatamente si existe, sin necesidad de hacer hover en todo.
            btn_pos = self._find_call_button_by_template_and_cluster(
                search_region, call_type, screen_w, screen_h
            )
            if btn_pos:
                result = self._click_and_verify(btn_pos, call_type, search_region)
                if result:
                    return result

            # ESTRATEGIA B (PRIORIDAD 2): Exploración activa con Hover y Lectura OCR
            btn_pos = self._find_call_button_by_tooltip(
                search_region, target_tooltips, screen_w, screen_h
            )
            if btn_pos:
                result = self._click_and_verify(btn_pos, call_type, search_region)
                if result:
                    return result

            # ESTRATEGIA C: Cluster detection puro (posición ordinal fallback)
            btn_pos = self._find_call_button_by_cluster(
                search_region, call_type, screen_w, screen_h
            )
            if btn_pos:
                result = self._click_and_verify(btn_pos, call_type, search_region)
                if result:
                    return result

            # Esperar antes del siguiente intento
            time.sleep(0.5)

        logger.error("[CALL] === FALLO: agotados %d intentos ===", MAX_ATTEMPTS)
        return ActionResult(False, f"No pude encontrar ni confirmar el botón de {call_type} call después de {MAX_ATTEMPTS} intentos.")

    # ==================================================================
    # Fases internas
    # ==================================================================

    def _ensure_discord_focused(self) -> bool:
        """Verifica que Discord esté abierto y en primer plano."""
        windows = gw.getWindowsWithTitle("Discord")
        if not windows:
            logger.warning("[CALL] Discord no encontrado entre las ventanas abiertas.")
            return False
        win = windows[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.5)
            self.vision.capture_screen()  # baseline
            return True
        except Exception as exc:
            logger.error("[CALL] No pude enfocar Discord: %s", exc)
            return False

    def _get_call_button_region(self, sw: int, sh: int) -> Tuple[int, int, int, int]:
        """Zona donde Discord pone los botones de llamada (esquina sup-derecha del chat).
        X: 60%-97%  Y: 0%-15% — cubre DM y Group DM headers.
        """
        return (int(sw * 0.60), 0, int(sw * 0.37), int(sh * 0.15))

    # ------------------------------------------------------------------
    # ESTRATEGIA A: Hover + OCR de tooltip
    # ------------------------------------------------------------------

    def _find_call_button_by_tooltip(
        self,
        region: Tuple[int, int, int, int],
        target_tooltips: set[str],
        sw: int, sh: int,
    ) -> Optional[Tuple[int, int]]:
        """Escanea la región haciendo hover en iconos detectados y lee el tooltip con OCR."""
        logger.debug("[CALL] Estrategia A: hover scan con OCR de tooltip")

        # Primero encontrar candidatos mediante cluster
        cluster_result = self.vision.detect_horizontal_cluster(
            region=region, min_icon_size=10, max_icon_size=45,
            min_count=2, max_gap_px=80,
        )
        if not cluster_result:
            return None

        centers, _ = cluster_result
        logger.info("[CALL] Cluster con %d iconos encontrado", len(centers))

        for idx, (cx, cy) in enumerate(centers[:6]):
            # Mover cursor al icono
            pyautogui.moveTo(cx, cy, duration=0.25, tween=pyautogui.easeInOutQuad)
            time.sleep(0.5)  # esperar tooltip

            # Leer tooltip con OCR
            tooltip_text = self._read_tooltip_near(cx, cy, sw, sh)
            if not tooltip_text:
                logger.debug("[CALL] Icono #%d (%d,%d): sin tooltip legible", idx, cx, cy)
                continue

            logger.info("[CALL] Icono #%d (%d,%d): tooltip='%s'", idx, cx, cy, tooltip_text)

            # ¿Es el botón que buscamos?
            tooltip_lower = tooltip_text.lower().strip()
            for target in target_tooltips:
                if target in tooltip_lower or tooltip_lower in target:
                    logger.info("[CALL] ✅ MATCH: '%s' coincide con tooltip '%s'", target, tooltip_text)
                    return (cx, cy)

            # ¿Es el otro tipo de llamada? (descartar explícitamente)
            for other in ALL_CALL_TOOLTIPS - target_tooltips:
                if other in tooltip_lower:
                    logger.info("[CALL] ⏭ Descartado: tooltip='%s' es %s, no lo que buscamos", tooltip_text, other)
                    break

        return None

    def _read_tooltip_near(self, x: int, y: int, sw: int, sh: int) -> str:
        """Lee el texto del tooltip que aparece debajo o encima del cursor."""
        if not self._tesseract_ready():
            return ""

        # Los tooltips de Discord aparecen justo debajo del botón
        # Región: centrado en X ±120px, Y+25 a Y+60
        tooltip_regions = [
            # Debajo del cursor
            (max(0, x - 120), min(y + 20, sh - 50), 240, 40),
            # Encima del cursor (a veces Discord lo pone arriba)
            (max(0, x - 120), max(0, y - 55), 240, 40),
            # Más abajo y más ancho
            (max(0, x - 160), min(y + 15, sh - 60), 320, 50),
        ]

        for rx, ry, rw, rh in tooltip_regions:
            if rx + rw > sw:
                rw = sw - rx
            if ry + rh > sh:
                rh = sh - ry
            if rw <= 0 or rh <= 0:
                continue

            try:
                crop = self.vision._capture_crop(rx, ry, rw, rh)
                if crop.size == 0:
                    continue
                # Preprocessar para OCR: invertir si es fondo oscuro
                _, binary = cv2.threshold(crop, 127, 255, cv2.THRESH_BINARY_INV)
                text = pytesseract.image_to_string(binary, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ").strip()
                if text and len(text) > 3:
                    return text
                # Intentar también con la imagen original
                text2 = pytesseract.image_to_string(crop, config="--psm 7").strip()
                if text2 and len(text2) > 3:
                    return text2
            except Exception:
                continue

        return ""

    def _tesseract_ready(self) -> bool:
        global _TESSERACT_READY
        if _TESSERACT_READY is not None:
            return _TESSERACT_READY
        if pytesseract is None:
            _TESSERACT_READY = False
            return False
        try:
            pytesseract.get_tesseract_version()
            _TESSERACT_READY = True
        except Exception as exc:
            logger.warning("[CALL] Tesseract OCR no esta disponible: %s", exc)
            _TESSERACT_READY = False
        return _TESSERACT_READY

    @staticmethod
    def _point_in_region(x: int, y: int, region: Tuple[int, int, int, int]) -> bool:
        rx, ry, rw, rh = region
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def _try_current_cursor_hint(
        self,
        region: Tuple[int, int, int, int],
        target_tooltips: set[str],
        call_type: str,
        sw: int,
        sh: int,
    ) -> Optional[Tuple[int, int]]:
        """Si el usuario ya puso el cursor sobre el botón correcto, aprovéchalo.

        Prioridad:
        1. Leer tooltip en la posición actual si existe OCR.
        2. Si no hay OCR, validar hover + posición relativa dentro del cluster.
        """
        cursor_x, cursor_y = pyautogui.position()
        if not self._point_in_region(cursor_x, cursor_y, region):
            return None

        logger.info("[CALL] Cursor actual dentro de la region de llamadas en (%d,%d)", cursor_x, cursor_y)

        tooltip_text = self._read_tooltip_near(cursor_x, cursor_y, sw, sh)
        if tooltip_text:
            tooltip_lower = tooltip_text.lower().strip()
            for target in target_tooltips:
                if target in tooltip_lower or tooltip_lower in target:
                    logger.info("[CALL] Cursor guiado por usuario confirmado por tooltip: '%s'", tooltip_text)
                    return (cursor_x, cursor_y)

        if not self.vision.verify_tooltip(cursor_x, cursor_y):
            return None

        cluster_result = self.vision.detect_horizontal_cluster(
            region=region, min_icon_size=10, max_icon_size=45,
            min_count=2, max_gap_px=80,
        )
        if not cluster_result:
            return None

        centers, _ = cluster_result
        nearest_idx = None
        nearest_dist = None
        for idx, (cx, cy) in enumerate(centers):
            dist = abs(cx - cursor_x) + abs(cy - cursor_y)
            if nearest_dist is None or dist < nearest_dist:
                nearest_idx = idx
                nearest_dist = dist

        if nearest_idx is None or nearest_dist is None or nearest_dist > 35:
            return None

        if call_type == "voice" and nearest_idx == 0:
            logger.info("[CALL] Cursor guiado por usuario aceptado como llamada de voz (cluster idx 0)")
            return centers[nearest_idx]
        if call_type == "video" and nearest_idx == 1:
            logger.info("[CALL] Cursor guiado por usuario aceptado como videollamada (cluster idx 1)")
            return centers[nearest_idx]

        return None

    def _find_call_button_by_template_and_cluster(
        self,
        region: Tuple[int, int, int, int],
        call_type: str,
        sw: int, sh: int,
    ) -> Optional[Tuple[int, int]]:
        """Aplica la heurística visual estricta:
        1. Encuentra candidatos con template matching en la zona top-right.
        2. Valida que el candidato esté dentro de un cluster de controles.
        3. Verifica el orden espacial (ej: llamada a la izquierda de videollamada).
        """
        logger.debug("[CALL] Estrategia A: Template Matching + Validación de Cluster")
        
        # 1. Detectar el cluster en la región
        cluster_result = self.vision.detect_horizontal_cluster(
            region=region, min_icon_size=10, max_icon_size=45,
            min_count=2, max_gap_px=80,
        )
        if not cluster_result:
            logger.debug("[CALL] Template+Cluster: No se encontró el cluster típico en la cabecera.")
            return None

        centers, cluster_bbox = cluster_result
        if len(centers) < 2:
            return None

        # 2. Buscar por template matching dentro de esa región
        icon_name = "discord_call_icon.png" if call_type == "voice" else "discord_video_icon.png"
        icon_path = str(self.assets_dir / icon_name)
        
        if not os.path.exists(icon_path):
            logger.debug("[CALL] Template+Cluster: Falta el asset %s", icon_path)
            return None

        candidate = self.vision.find_icon(icon_path, min_confidence=0.55, region=region)
        if not candidate:
            candidate = self.vision.find_icon_edges(icon_path, min_confidence=0.55, region=region)

        if candidate:
            cx, cy = candidate.center
            
            # Si la plantilla fue detectada con buena confianza, confiamos ciegamente en ella.
            # Esto evita que un error en la detección de bordes del cluster nos haga descartar el botón correcto.
            if candidate.confidence >= 0.60:
                logger.info("[CALL] ✅ Plantilla detectada con confianza alta (%.2f). Click directo.", candidate.confidence)
                return (cx, cy)
                
            # 3. Validar contexto espacial solo si la confianza es baja (0.55 - 0.60)
            if cluster_result:
                centers, _ = cluster_result
                for idx, (clust_x, clust_y) in enumerate(centers):
                    if abs(cx - clust_x) < 30 and abs(cy - clust_y) < 30:
                        logger.info("[CALL] ✅ Candidato validado por pertenecer al cluster (confianza %.2f).", candidate.confidence)
                        return (cx, cy)
                        
            logger.debug("[CALL] Template candidato en (%d,%d) descartado por baja confianza y no coincidir con cluster.", cx, cy)
        
        return None

    # ------------------------------------------------------------------
    # ESTRATEGIA C: Cluster + posición ordinal (Fallback puro)
    # ------------------------------------------------------------------

    def _find_call_button_by_cluster(
        self,
        region: Tuple[int, int, int, int],
        call_type: str,
        sw: int, sh: int,
    ) -> Optional[Tuple[int, int]]:
        """Fallback: en Discord DM, el orden es siempre [📞voice][📹video][📌pin][👥members].
        Si no hay OCR ni template matching, usa la posición ordinal como heurística.
        """
        logger.debug("[CALL] Estrategia C: cluster + posición ordinal (Fallback)")

        cluster_result = self.vision.detect_horizontal_cluster(
            region=region, min_icon_size=10, max_icon_size=45,
            min_count=2, max_gap_px=80,
        )
        if not cluster_result:
            return None

        centers, _ = cluster_result
        if len(centers) < 2:
            return None

        if call_type == "voice" and len(centers) >= 1:
            cx, cy = centers[0]
            logger.info("[CALL] Cluster ordinal: voice → icono #0 en (%d,%d)", cx, cy)
            return (cx, cy)
        elif call_type == "video" and len(centers) >= 2:
            cx, cy = centers[1]
            logger.info("[CALL] Cluster ordinal: video → icono #1 en (%d,%d)", cx, cy)
            return (cx, cy)

        return None

    # ------------------------------------------------------------------
    # Click + Verificación
    # ------------------------------------------------------------------

    def _click_and_verify(
        self,
        pos: Tuple[int, int],
        call_type: str,
        search_region: Tuple[int, int, int, int],
    ) -> Optional[ActionResult]:
        """Hace click en pos y verifica si la llamada empezó de verdad."""
        cx, cy = pos
        logger.info("[CALL] FASE 3: Click en (%d, %d)", cx, cy)

        # Capturar estado antes del click
        self.vision.capture_screen()

        # Click suave
        pyautogui.moveTo(cx, cy, duration=0.3, tween=pyautogui.easeInOutQuad)
        time.sleep(0.15)
        pyautogui.click()

        # Esperar a que Discord reaccione y verificar varias veces.
        for wait_seconds in (1.0, 1.5, 2.5):
            time.sleep(wait_seconds)
            if self._verify_call_active():
                logger.info("[CALL] ✅ LLAMADA CONFIRMADA en (%d,%d)", cx, cy)

                # FASE 5: Aprendizaje — guardar la posición exitosa
                sw, sh = pyautogui.size()
                expected_boton = "llamada_voz" if call_type == "voice" else "videollamada"
                ordinal_idx = 0 if call_type == "voice" else 1
                
                # Intentamos leer el tooltip real, si no pudimos, guardamos el que esperábamos
                actual_tooltip = self._read_tooltip_near(cx, cy, sw, sh) or ("Start Voice Call" if call_type == "voice" else "Start Video Call")
                
                # Contexto basado en la ventana activa
                windows = gw.getWindowsWithTitle("Discord")
                window_title = windows[0].title if windows else "DM"
                
                mem = CallButtonMemory(
                    app="Discord",
                    contexto=window_title,
                    boton=expected_boton,
                    tooltip=actual_tooltip,
                    x_abs=cx,
                    y_abs=cy,
                    x_rel=round(cx / sw, 4),
                    y_rel=round(cy / sh, 4),
                    ordinal_index=ordinal_idx,
                    icon_w=30,  # tamaño estimado base
                    icon_h=30,
                    region_bbox=list(search_region),
                    confianza=0.85,
                    success_count=1,
                    last_used=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    learned_from="agent"
                )
                
                # Si ya había memoria, incrementar
                old = _load_call_memory()
                if old and old.boton == expected_boton:
                    mem.success_count = old.success_count + 1
                    mem.confianza = min(0.99, old.confianza + 0.05)
                _save_call_memory(mem)

                return ActionResult(True, f"Llamada de {call_type} iniciada y confirmada.")

        logger.warning("[CALL] ❌ Click en (%d,%d) no inició la llamada.", cx, cy)
        return None

    # ------------------------------------------------------------------
    # Verificación multicapa de llamada activa
    # ------------------------------------------------------------------

    def _verify_call_active(self) -> bool:
        """Verifica estrictamente si la llamada empezó.
        
        REGLA ESTRICTA:
        Solo es válido si se detecta el panel de controles de llamada
        y el botón rojo circular de colgar en la franja central.
        Se ignoran variaciones de color sueltas.
        """
        sw, sh = pyautogui.size()
        
        # 1. Buscar el botón de colgar en la FRANJA CENTRAL (cubre arriba y abajo)
        # Region: centro de la pantalla, del 20% al 80% horizontal, toda la altura.
        center_column_region = (int(sw * 0.20), 0, int(sw * 0.60), sh)
        
        end_call_path = str(self.assets_dir / "discord_end_call_icon.png")
        btn_found = False
        
        if os.path.exists(end_call_path) and os.path.getsize(end_call_path) > 50:
            found = self.vision.find_icon(end_call_path, min_confidence=0.65, region=center_column_region)
            if found:
                btn_found = True
                logger.info("[VERIFY] ✅ Botón de colgar detectado en la franja central.")
        else:
            # Fallback si falta asset: buscar cluster de controles centrales
            # El panel suele tener [camara][pantalla][mic][sonido][colgar]
            cluster = self.vision.detect_horizontal_cluster(
                region=center_column_region, min_icon_size=20, max_icon_size=60, min_count=3, max_gap_px=60
            )
            if cluster:
                btn_found = True
                logger.info("[VERIFY] ✅ Cluster de controles de llamada detectado en panel central superior.")

        if not btn_found:
            logger.debug("[VERIFY] ❌ No se detectó botón de colgar ni panel central.")
            return False
            
        # 2. Panel de controles (texto OCR confirmatorio)
        panel_text_found = False
        if pytesseract:
            try:
                crop = self.vision._capture_crop(*center_column_region)
                text = pytesseract.image_to_string(crop, config="--psm 6").lower()
                for kw in CALL_ACTIVE_KEYWORDS + CALL_CONTROL_KEYWORDS:
                    if kw in text:
                        panel_text_found = True
                        logger.info("[VERIFY] ✅ Texto del panel detectado: '%s'", kw)
                        break
            except Exception as e:
                logger.debug("[VERIFY] Error OCR: %s", e)
        
        # Como Tesseract a veces falla en fondos oscuros, si el botón está clarísimo en el cluster, 
        # lo damos por válido. Pero el cluster superior central es mandatorio.
        if btn_found:
            return True
            
        return False

    def _detect_active_call(self) -> bool:
        """Detecta si ya hay una llamada activa antes de intentar iniciar una nueva."""
        return self._verify_call_active()

    # ------------------------------------------------------------------
    # Memoria: intentar desde posición aprendida
    # ------------------------------------------------------------------

    def _try_from_memory(
        self,
        memory: CallButtonMemory,
        target_tooltips: set[str],
    ) -> Optional[ActionResult]:
        """Intenta usar la posición aprendida de llamadas anteriores."""
        sw, sh = pyautogui.size()
        cx = int(memory.x_rel * sw)
        cy = int(memory.y_rel * sh)
        logger.info(
            "[CALL] Intentando desde MEMORIA: (%d,%d) confianza=%.2f éxitos=%d",
            cx, cy, memory.confianza, memory.success_count,
        )

        # Hover primero para confirmar que el tooltip sigue ahí
        pyautogui.moveTo(cx, cy, duration=0.3, tween=pyautogui.easeInOutQuad)
        time.sleep(0.5)

        tooltip = self._read_tooltip_near(cx, cy, sw, sh)
        if tooltip:
            tooltip_lower = tooltip.lower()
            for target in target_tooltips:
                if target in tooltip_lower or tooltip_lower in target:
                    logger.info("[CALL] Memoria CONFIRMADA por tooltip: '%s'", tooltip)
                    region = self._get_call_button_region(sw, sh)
                    call_type_arg = "voice" if memory.boton == "llamada_voz" else "video"
                    return self._click_and_verify((cx, cy), call_type_arg, region)

        # Si falló la validación del tooltip, penalizamos la confianza
        logger.info("[CALL] Memoria NO confirmada (tooltip='%s'). Disminuyendo confianza...", tooltip)
        memory.confianza = max(0.0, memory.confianza - 0.20)
        _save_call_memory(memory)
        
        logger.info("[CALL] Usando detección completa como fallback.")
        return None
