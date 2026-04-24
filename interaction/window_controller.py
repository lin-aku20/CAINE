"""Controlador de ventanas seguro para CAINE."""

try:
    import pygetwindow as gw
except ImportError:
    gw = None

class WindowController:
    """Busca, enfoca y minimiza ventanas del escritorio."""

    def focus_window(self, title_query: str) -> bool:
        if not gw: return False
        for win in gw.getAllWindows():
            if title_query.lower() in win.title.lower():
                try:
                    win.activate()
                    return True
                except Exception:
                    pass
        return False

    def minimize_window(self, title_query: str) -> bool:
        if not gw: return False
        for win in gw.getAllWindows():
            if title_query.lower() in win.title.lower():
                try:
                    win.minimize()
                    return True
                except Exception:
                    pass
        return False
