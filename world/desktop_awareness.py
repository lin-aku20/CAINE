"""Motor de conciencia de escritorio para CAINE (Desktop Awareness)."""

import time
import ctypes
import ctypes.wintypes
from dataclasses import dataclass, field

import psutil
import pyautogui

try:
    import pygetwindow as gw
except ImportError:
    gw = None


@dataclass(slots=True)
class DesktopContext:
    active_window_title: str
    active_app_exe: str
    idle_time_seconds: float
    running_apps_count: int


class DesktopAwareness:
    """Supervisa la inactividad, ventanas enfocadas y procesos corriendo usando APIs del SO (Bajo CPU)."""

    def __init__(self) -> None:
        self._last_mouse_pos = pyautogui.position()
        self._last_activity_time = time.monotonic()
        self._user32 = ctypes.windll.user32

    def get_context(self) -> DesktopContext:
        """Retorna el estado instantaneo del escritorio."""
        self._update_idle_time()

        title = self._get_active_window_title()
        exe = self._get_active_window_exe()
        
        # Aproximar carga contando procesos de usuario
        # (Esto se podria cachead, pero es rapido)
        count = 0
        try:
            count = len(list(psutil.process_iter(['name'])))
        except Exception:
            pass

        return DesktopContext(
            active_window_title=title,
            active_app_exe=exe,
            idle_time_seconds=time.monotonic() - self._last_activity_time,
            running_apps_count=count,
        )

    def _update_idle_time(self) -> None:
        try:
            current_pos = pyautogui.position()
            if current_pos != self._last_mouse_pos:
                self._last_activity_time = time.monotonic()
                self._last_mouse_pos = current_pos
        except Exception:
            pass

    def _get_active_window_title(self) -> str:
        if gw:
            try:
                win = gw.getActiveWindow()
                if win:
                    return win.title
            except Exception:
                pass
        return ""

    def _get_active_window_exe(self) -> str:
        """Usa Win32 API para sacar el ejecutable de la ventana actual."""
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return ""
        
        pid = ctypes.wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        try:
            process = psutil.Process(pid.value)
            return process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "unknown.exe"
