import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from pathlib import Path

import cv2
import mss
import mss.tools
import numpy as np
import pyautogui

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import pygetwindow as gw
    _HAS_GW = True
except ImportError:
    _HAS_GW = False

logger = logging.getLogger("caine.desktop_vision")


@dataclass
class UIElement:
    label: str
    type: str  # 'button', 'text_input', 'icon', 'text'
    bounding_box: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    clickable: bool

    @property
    def center(self) -> Tuple[int, int]:
        x, y, w, h = self.bounding_box
        return (x + w // 2, y + h // 2)


@dataclass
class DesktopSnapshot:
    """Estado visual completo del escritorio en un instante."""
    active_app: str = ""
    window_title: str = ""
    # Mapa espacial dividido en zonas
    zones: dict = field(default_factory=dict)
    # Elementos detectados
    ui_elements: List[UIElement] = field(default_factory=list)
    # Diff visual respecto al snapshot anterior
    change_ratio: float = 0.0
    ui_changed: bool = False
    # Imagen cruda (numpy array)
    screen: Optional[object] = None
    timestamp: float = field(default_factory=time.monotonic)

    def summary(self) -> str:
        parts = [f"app={self.active_app or 'escritorio'}"]
        if self.ui_changed:
            parts.append(f"cambio_visual={self.change_ratio:.1%}")
        if self.ui_elements:
            labels = [e.label for e in self.ui_elements[:5]]
            parts.append(f"elementos={labels}")
        return " | ".join(parts)


class DesktopVisionAgent:
    """Visión activa del escritorio: captura, análisis de región, template matching y diff visual."""

    # Definición de zonas espaciales normalizadas (x_pct, y_pct, w_pct, h_pct)
    ZONE_MAP = {
        "top_bar":          (0.00, 0.00, 1.00, 0.08),
        "chat_header":      (0.25, 0.00, 0.50, 0.15),  # barra superior del chat (NO perfil derecho)
        "discord_call_btn": (0.60, 0.00, 0.20, 0.10),  # zona íconos llamada Discord
        "sidebar_left":     (0.00, 0.00, 0.20, 1.00),
        "main_area":        (0.20, 0.10, 0.60, 0.80),
        "profile_panel":    (0.80, 0.00, 0.20, 1.00),  # zona PROHIBIDA para búsqueda de llamada
        "taskbar":          (0.00, 0.92, 1.00, 0.08),
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger("caine.desktop_vision")
        self.last_screen: Optional[np.ndarray] = None
        self.last_snapshot: Optional[DesktopSnapshot] = None
        self.ui_map: List[UIElement] = []

    # ------------------------------------------------------------------
    # Captura de pantalla
    # ------------------------------------------------------------------

    def capture_screen(self, grayscale: bool = True) -> np.ndarray:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            screen_np = np.array(sct_img)
            if grayscale:
                return cv2.cvtColor(screen_np, cv2.COLOR_BGRA2GRAY)
            return cv2.cvtColor(screen_np, cv2.COLOR_BGRA2BGR)

    def capture_region(self, region: Tuple[int, int, int, int], grayscale: bool = True) -> Tuple[np.ndarray, int, int]:
        """Captura solo una región (x, y, w, h). Devuelve (imagen, offset_x, offset_y)."""
        screen = self.capture_screen(grayscale=grayscale)
        x, y, w, h = region
        return screen[y:y+h, x:x+w], x, y

    def zone_to_pixels(self, zone_name: str) -> Optional[Tuple[int, int, int, int]]:
        """Convierte una zona nombrada a píxeles absolutos."""
        if zone_name not in self.ZONE_MAP:
            return None
        sw, sh = pyautogui.size()
        xp, yp, wp, hp = self.ZONE_MAP[zone_name]
        return (int(sw * xp), int(sh * yp), int(sw * wp), int(sh * hp))

    # ------------------------------------------------------------------
    # Detección de ventana activa
    # ------------------------------------------------------------------

    def get_active_window(self) -> Tuple[str, str]:
        """Devuelve (título, nombre_proceso) de la ventana activa."""
        if _HAS_GW:
            try:
                active = gw.getActiveWindow()
                if active:
                    return active.title or "", ""
            except Exception:
                pass
        return "", ""

    def get_discord_window(self):
        """Devuelve la ventana de Discord si está abierta, o None."""
        if not _HAS_GW:
            return None
        wins = gw.getWindowsWithTitle("Discord")
        return wins[0] if wins else None

    # ------------------------------------------------------------------
    # Diff visual (detección de cambios)
    # ------------------------------------------------------------------

    def compute_visual_diff(self, screen: np.ndarray) -> float:
        """Compara la pantalla actual con la anterior. Devuelve ratio de cambio (0.0-1.0)."""
        if self.last_screen is None:
            self.last_screen = screen
            return 0.0
        diff = cv2.absdiff(self.last_screen, screen)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        changed = cv2.countNonZero(thresh)
        total = screen.shape[0] * screen.shape[1]
        return changed / total

    # ------------------------------------------------------------------
    # Snapshot completo del escritorio
    # ------------------------------------------------------------------

    def take_snapshot(self) -> DesktopSnapshot:
        """Captura y analiza el estado completo del escritorio."""
        screen = self.capture_screen(grayscale=True)
        change_ratio = self.compute_visual_diff(screen)
        self.last_screen = screen

        title, process = self.get_active_window()

        snapshot = DesktopSnapshot(
            active_app=title.split(" - ")[-1] if " - " in title else title,
            window_title=title,
            zones={name: self.zone_to_pixels(name) for name in self.ZONE_MAP},
            ui_elements=list(self.ui_map),
            change_ratio=change_ratio,
            ui_changed=change_ratio > 0.02,
            screen=screen,
        )
        self.last_snapshot = snapshot
        return snapshot

    # ------------------------------------------------------------------
    # Escaneo OCR de texto
    # ------------------------------------------------------------------

    def scan_ui_elements(self) -> None:
        """Actualiza el UIObjectMap escaneando la pantalla actual via OCR."""
        if pytesseract is None:
            self.logger.error("pytesseract no está instalado.")
            return

        screen = self.capture_screen(grayscale=True)
        self.last_screen = screen
        self.ui_map.clear()

        try:
            data = pytesseract.image_to_data(screen, output_type=pytesseract.Output.DICT)
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                conf = int(data['conf'][i])
                if text and conf > 50:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    element_type = 'text'
                    if len(text) < 15 and text.lower() in ['llamar', 'enviar', 'call', 'send', 'buscar']:
                        element_type = 'button'
                    self.ui_map.append(UIElement(
                        label=text.lower(),
                        type=element_type,
                        bounding_box=(x, y, w, h),
                        confidence=conf / 100.0,
                        clickable=True
                    ))
            self.logger.debug("[VISION] %d text elements found.", len(self.ui_map))
        except Exception as e:
            self.logger.warning("[VISION] OCR falló, ignorando búsqueda de texto: %s", e)

    # ------------------------------------------------------------------
    # Template matching con región
    # ------------------------------------------------------------------

    def find_icon(self, icon_path: str, threshold: float = 0.75, retries: int = 3, min_confidence: float = None, region=None, **kwargs) -> Optional[UIElement]:
        """Busca un ícono específico usando Template Matching multiescala y priorizando memoria aprendida, con retries automáticos."""
        # Compatibilidad con min_confidence heredado
        if min_confidence is not None:
            threshold = min_confidence

        original_path = Path(icon_path)
        icon_name = original_path.stem
        
        # 1. Prioridad: Buscar en memoria aprendida
        learned_dir = original_path.parent / "learned"
        index_file = learned_dir / "index.json"
        
        actual_path = str(original_path)
        if index_file.exists():
            try:
                import json
                index = json.loads(index_file.read_text(encoding="utf-8"))
                if icon_name in index:
                    learned_path = learned_dir / index[icon_name]
                    if learned_path.exists():
                        actual_path = str(learned_path)
                        self.logger.info("[VISION] 🧠 Usando plantilla aprendida dinámicamente: %s", learned_path.name)
            except Exception as e:
                self.logger.warning("[VISION] Error leyendo learned/index.json: %s", e)

        if not os.path.exists(actual_path):
            self.logger.error("[VISION] Icon path not found: %s", actual_path)
            return None

        template = cv2.imread(actual_path, 0)
        if template is None:
            return None

        for intento in range(retries):
            screen = self.capture_screen(grayscale=True)
            offset_x, offset_y = 0, 0
            if region:
                x, y, w, h = region
                screen = screen[y:y+h, x:x+w]
                offset_x, offset_y = x, y

            best_match = None
            best_val = 0.0
            best_scale = 1.0

            for scale in np.linspace(0.5, 1.5, 20):
                resized = cv2.resize(template, None, fx=scale, fy=scale)
                if resized.shape[0] > screen.shape[0] or resized.shape[1] > screen.shape[1]:
                    continue
                result = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val > best_val:
                    best_val = max_val
                    best_match = max_loc
                    best_scale = scale

            if best_val >= threshold and best_match is not None:
                rh, rw = int(template.shape[0] * best_scale), int(template.shape[1] * best_scale)
                element = UIElement(
                    label=Path(icon_path).stem,
                    type='icon',
                    bounding_box=(best_match[0] + offset_x, best_match[1] + offset_y, rw, rh),
                    confidence=best_val,
                    clickable=True
                )
                return element
                
            self.logger.debug("[VISION] find_icon falló intento %d/%d (conf: %.2f). Reintentando...", intento + 1, retries, best_val)
            import time
            time.sleep(0.3)

        return None

    def find_icon_edges(self, icon_path: str, min_confidence: float = 0.40, region=None) -> Optional[UIElement]:
        """Busca un ícono usando Canny Edge Detection (agnóstico a modo oscuro/claro)."""
        if not os.path.exists(icon_path):
            self.logger.error("[VISION] Icon path not found: %s", icon_path)
            return None

        template = cv2.imread(icon_path, 0)
        if template is None:
            return None

        template_edges = cv2.Canny(template, 50, 200)

        screen = self.capture_screen(grayscale=True)
        offset_x, offset_y = 0, 0
        if region:
            x, y, w, h = region
            screen = screen[y:y+h, x:x+w]
            offset_x, offset_y = x, y

        screen_edges = cv2.Canny(screen, 50, 200)

        best_match = None
        best_val = 0.0
        best_scale = 1.0

        for scale in np.linspace(0.5, 1.5, 20):
            resized = cv2.resize(template_edges, None, fx=scale, fy=scale)
            if resized.shape[0] > screen_edges.shape[0] or resized.shape[1] > screen_edges.shape[1]:
                continue
            result = cv2.matchTemplate(screen_edges, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_match = max_loc
                best_scale = scale

        if best_val >= min_confidence and best_match is not None:
            rh, rw = int(template.shape[0] * best_scale), int(template.shape[1] * best_scale)
            element = UIElement(
                label=Path(icon_path).stem,
                type='icon',
                bounding_box=(best_match[0] + offset_x, best_match[1] + offset_y, rw, rh),
                confidence=best_val,
                clickable=True
            )
            self.logger.debug("[VISION] Found %s (edges) at %s conf=%.2f", element.label, element.bounding_box, best_val)
            return element
        return None

    def find_element(self, query: str) -> Optional[UIElement]:
        """Busca un elemento en el UI Map por texto OCR."""
        self.scan_ui_elements()
        query = query.lower()
        for element in self.ui_map:
            if query in element.label:
                return element
        return None

    def wait_for_visual_change(self, timeout: float = 5.0, threshold: float = 0.02) -> bool:
        """Espera un cambio visual significativo en la pantalla."""
        if self.last_screen is None:
            self.last_screen = self.capture_screen(grayscale=True)
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_screen = self.capture_screen(grayscale=True)
            ratio = self.compute_visual_diff(current_screen)
            if ratio > threshold:
                self.last_screen = current_screen
                return True
            time.sleep(0.3)
        return False

    def scan_for_hover_buttons(
        self,
        region: Tuple[int, int, int, int],
        step_px: int = 20,
        hover_threshold: float = 0.001,
    ) -> Optional[Tuple[int, int]]:
        """Escanea una región moviendo el mouse y detectando cambios de hover.

        Mueve el cursor pixel a pixel por la región. Si al posicionar el mouse
        en un punto se detecta un cambio visual localizado (highlight/hover),
        ese punto contiene un elemento interactivo.

        Args:
            region: (x, y, w, h) zona de escaneo en píxeles absolutos.
            step_px: distancia entre cada punto de sondeo.
            hover_threshold: ratio mínimo de cambio en la zona local para
                             considerar que hay hover (0.001 = 0.1% de píxeles).

        Returns:
            (x, y) del primer elemento interactivo detectado, o None.
        """
        rx, ry, rw, rh = region
        self.logger.debug("[VISION] Hover scan: region=(%d,%d,%d,%d) step=%d", rx, ry, rw, rh, step_px)

        # Captura base antes de mover el mouse
        base_crop = self._capture_crop(rx, ry, rw, rh)

        for y_offset in range(0, rh, step_px):
            for x_offset in range(0, rw, step_px):
                px = rx + x_offset
                py = ry + y_offset

                # Mover mouse
                pyautogui.moveTo(px, py, duration=0.05)
                time.sleep(0.08)  # esperar renderizado del hover

                # Captura post-hover
                hover_crop = self._capture_crop(rx, ry, rw, rh)

                # Comparar solo la zona local alrededor del cursor (±30px)
                local_x1 = max(0, x_offset - 30)
                local_y1 = max(0, y_offset - 30)
                local_x2 = min(rw, x_offset + 30)
                local_y2 = min(rh, y_offset + 30)

                base_local = base_crop[local_y1:local_y2, local_x1:local_x2]
                hover_local = hover_crop[local_y1:local_y2, local_x1:local_x2]

                if base_local.size == 0 or hover_local.size == 0:
                    continue

                diff = cv2.absdiff(base_local, hover_local)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                changed = cv2.countNonZero(thresh)
                total = base_local.shape[0] * base_local.shape[1]
                ratio = changed / total if total > 0 else 0

                if ratio > hover_threshold:
                    self.logger.info(
                        "[VISION] Hover detected at (%d, %d) ratio=%.3f",
                        px, py, ratio,
                    )
                    # Actualizar base para la siguiente comparación
                    base_crop = hover_crop
                    return (px, py)

                # Actualizar base para evitar drift acumulado
                base_crop = hover_crop

        return None

    def _capture_crop(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Captura una región específica de la pantalla en escala de grises."""
        screen = self.capture_screen(grayscale=True)
        return screen[y:y+h, x:x+w]

    def detect_horizontal_cluster(
        self,
        region: Tuple[int, int, int, int],
        min_icon_size: int = 12,
        max_icon_size: int = 40,
        min_count: int = 2,
        max_gap_px: int = 60,
    ) -> Optional[Tuple[List[Tuple[int, int]], Tuple[int, int, int, int]]]:
        """Detecta el cluster horizontal de iconos más compacto en la región.

        Busca el grupo donde los iconos están:
          - alineados horizontalmente (misma Y ± tolerancia)
          - del mismo tamaño aproximado
          - separados por ≤ max_gap_px entre sí
          - sin texto debajo (barra de controles, no navegación)

        Returns:
            Tuple (icon_centers, cluster_bbox) donde:
              - icon_centers: list de (x, y) centros ordenados izquierda→derecha
              - cluster_bbox: (x, y, w, h) bounding box del cluster completo
            None si no se encuentra ningún cluster válido.
        """
        rx, ry, rw, rh = region
        crop = self._capture_crop(rx, ry, rw, rh)

        # Umbralizar de forma adaptativa: en Discord los iconos pueden ser
        # gris claro, no necesariamente blanco puro. El umbral fijo en 160
        # perdia iconos como el telefono de la captura real.
        percentile_995 = float(np.percentile(crop, 99.5))
        bright_threshold = int(max(85, min(170, percentile_995 - 6)))
        _, bright = cv2.threshold(crop, bright_threshold, 255, cv2.THRESH_BINARY)

        # Fallback extra para temas oscuros donde los iconos quedan aun mas bajos.
        if cv2.countNonZero(bright) < 20:
            _, bright = cv2.threshold(crop, 95, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        bright = cv2.dilate(bright, kernel, iterations=1)

        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos por tamaño de icono
        icons = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if min_icon_size <= w <= max_icon_size and min_icon_size <= h <= max_icon_size:
                aspect = w / max(h, 1)
                if 0.35 <= aspect <= 2.8:
                    cx = rx + x + w // 2
                    cy = ry + y + h // 2
                    icons.append((cx, cy, w, h))

        if len(icons) < min_count:
            return None

        # Ordenar por x
        icons.sort(key=lambda i: i[0])

        # Buscar el grupo horizontal más denso usando ventana deslizante
        best_group = []
        for start_idx in range(len(icons)):
            group = [icons[start_idx]]
            ref_y = icons[start_idx][1]
            ref_h = icons[start_idx][3]

            for i in range(start_idx + 1, len(icons)):
                cx, cy, w, h = icons[i]
                prev_cx = group[-1][0]
                # Gap horizontal
                if cx - prev_cx > max_gap_px:
                    break
                # Alineación vertical (mismo row ±40% de altura)
                if abs(cy - ref_y) > ref_h * 0.6:
                    break
                group.append(icons[i])

            if len(group) >= min_count and len(group) > len(best_group):
                best_group = group

        if len(best_group) < min_count:
            return None

        centers = [(g[0], g[1]) for g in best_group]
        xs = [g[0] for g in best_group]
        ys = [g[1] for g in best_group]
        ws = [g[2] for g in best_group]
        hs = [g[3] for g in best_group]
        bbox_x = min(xs) - max(ws)
        bbox_y = min(ys) - max(hs)
        bbox_w = (max(xs) + max(ws)) - bbox_x
        bbox_h = max(hs) * 2

        self.logger.debug(
            "[VISION] Horizontal cluster: %d icons, bbox=(%d,%d,%d,%d)",
            len(centers), bbox_x, bbox_y, bbox_w, bbox_h,
        )
        return centers, (bbox_x, bbox_y, bbox_w, bbox_h)





    def verify_tooltip(
        self,
        x: int,
        y: int,
        hover_ms: int = 350,
        tooltip_threshold: float = 0.008,
    ) -> bool:
        """Verifica si al hacer hover en (x, y) aparece un tooltip.

        Mueve el mouse a la posición, espera hover_ms ms y compara
        la pantalla completa. Si aparece una región rectangular nueva
        (tooltip = fondo sólido + bordes definidos), retorna True.

        No requiere OCR — detecta el tooltip por su forma visual.

        Args:
            x, y: posición del elemento a verificar.
            hover_ms: milisegundos de espera para renderizar tooltip.
            tooltip_threshold: ratio mínimo de cambio para confirmar.

        Returns:
            True si se detectó tooltip o cambio de hover, False si nada.
        """
        import time

        # Captura base (antes de mover el mouse a ese punto)
        base = self.capture_screen(grayscale=True)

        pyautogui.moveTo(x, y, duration=0.15)
        time.sleep(hover_ms / 1000.0)

        after = self.capture_screen(grayscale=True)

        diff = cv2.absdiff(base, after)
        _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
        changed = cv2.countNonZero(thresh)
        total = base.shape[0] * base.shape[1]
        ratio = changed / total

        if ratio > tooltip_threshold:
            # Extra: verificar que el cambio tiene forma rectangular (tooltip)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                # Tooltip típico: ancho > alto, tamaño moderado
                if bw > 30 and bh > 10 and bw < 400 and bh < 60:
                    self.logger.debug("[VISION] Tooltip confirmed at (%d,%d) bw=%d bh=%d", x, y, bw, bh)
                    return True
            # Aunque no tenga forma perfecta de tooltip, el hover produjo cambio visible
            self.logger.debug("[VISION] Hover change at (%d,%d) ratio=%.4f (no tooltip shape)", x, y, ratio)
            return True

        return False

