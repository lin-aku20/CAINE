import pyautogui
import cv2
import numpy as np
import time
import logging
import os
from pathlib import Path

logger = logging.getLogger("caine.vision")

def find_and_click(image_path: str, tries: int = 5) -> bool:
    if not os.path.exists(image_path):
        logger.error("[VISION] image path not found: %s", image_path)
        return False
        
    template = cv2.imread(image_path, 0)
    if template is None:
        logger.error("[VISION] could not load image: %s", image_path)
        return False

    base_dir = Path(__file__).resolve().parent.parent.parent
    debug_path = base_dir / "debug_last_scan.png"

    for _ in range(tries):
        screenshot = pyautogui.screenshot()
        screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        
        cv2.imwrite(str(debug_path), screen)

        for scale in np.linspace(0.5, 1.5, 20):
            resized = cv2.resize(template, None, fx=scale, fy=scale)
            
            # Avoid matching if template is larger than screen
            if resized.shape[0] > screen.shape[0] or resized.shape[1] > screen.shape[1]:
                continue

            result = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > 0.65:
                rh, rw = resized.shape[:2]
                x = max_loc[0] + rw // 2
                y = max_loc[1] + rh // 2

                logger.info("[VISION] button found at %s,%s conf=%.2f", x, y, max_val)
                logger.info("[HUMAN_ACTION] moving mouse")
                pyautogui.moveTo(x, y, duration=0.2)
                
                logger.info("[HUMAN_ACTION] click")
                pyautogui.click()

                return True

        time.sleep(1)

    logger.warning("[VISION] button NOT found")
    return False
