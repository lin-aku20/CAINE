"""Guardas de seguridad para acciones del sistema."""

from __future__ import annotations

from pathlib import Path

from caine.config import ActionSettings


class ActionGuard:
    """Valida si una accion textual esta permitida."""

    def __init__(self, config: ActionSettings) -> None:
        self.config = config

    def is_enabled(self) -> bool:
        return self.config.enabled

    def is_allowed_app(self, alias: str) -> bool:
        if self.can_use_admin_actions():
            return True
        return alias.lower() in self.config.allowed_apps

    def is_allowed_hotkey(self, combo: str) -> bool:
        normalized = combo.replace(" ", "").lower()
        return normalized in {item.replace(" ", "").lower() for item in self.config.allowed_hotkeys}

    def permission_mode(self) -> str:
        return self.config.permission_mode.strip().lower()

    def can_use_power_actions(self) -> bool:
        return self.permission_mode() in {"power", "admin"}

    def can_use_admin_actions(self) -> bool:
        return self.permission_mode() == "admin"

    def is_allowed_folder(self, alias: str) -> bool:
        if self.can_use_admin_actions():
            return True
        return alias.lower() in self.config.allowed_folders

    def is_allowed_tool(self, alias: str) -> bool:
        return alias.lower() in self.config.allowed_tools

    def is_safe_script_path(self, script_path: Path) -> bool:
        return script_path.exists() and script_path.is_file()

    def is_within_workspace(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.config.workspace_root.resolve())
            return True
        except ValueError:
            return False

    def is_allowed_dev_command(self, executable: str) -> bool:
        return executable.lower() in {item.lower() for item in self.config.allowed_dev_commands}

    def is_allowed_shell_command(self, command: str) -> tuple[bool, str]:
        normalized = command.strip().lower()
        if not normalized:
            return False, "El comando esta vacio."
        for pattern in self.config.blocked_shell_patterns:
            if pattern.lower() in normalized:
                return False, f"El patron '{pattern}' esta bloqueado."
        return True, "ok"
