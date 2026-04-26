import pyautogui
import cv2
import numpy as np
import logging
import os

logger = logging.getLogger("caine.vision_click")

def click_image(image_path: str, confidence: float = 0.8) -> bool:
    """Busca una imagen en la pantalla y hace clic en ella si la encuentra."""
    if not os.path.exists(image_path):
        logger.error("No se encontró la imagen: %s", image_path)
        return False

    screenshot = pyautogui.screenshot()
    screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    template = cv2.imread(image_path)
    if template is None:
        logger.error("No se pudo cargar la imagen: %s", image_path)
        return False

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        h, w = template.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2

        pyautogui.moveTo(center_x, center_y, duration=0.2)
        pyautogui.click()
        return True

    return False
