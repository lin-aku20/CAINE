"""Lanzamiento seguro de apps y sitios para CAINE usando shell de Windows."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import time
import webbrowser

from interaction.action_guard import ActionGuard
from interaction.system_actions import SystemActionRouter
from memory.long_term_memory import LongTermMemoryStore


@dataclass(slots=True)
class LaunchResult:
    success: bool
    action: str
    target: str
    path: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "action": self.action,
            "target": self.target,
            "path": self.path,
            "message": self.message,
        }


class AppLauncher:
    """Abre apps por alias de Windows y evita ejecuciones peligrosas o repetidas."""

    APP_ALIASES: dict[str, str] = {
        "discord": "Discord",
        "chrome": "Chrome",
        "steam": "Steam",
        "spotify": "Spotify",
        "minecraft": "Minecraft",
        "firefox": "Firefox",
        "edge": "Edge",
        "notepad": "Notepad",
        "calculator": "Calculator",
        "calculadora": "Calculator",
    }

    WEBSITE_TARGETS: dict[str, str] = {
        "youtube": "https://www.youtube.com",
        "instagram": "https://www.instagram.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "tiktok": "https://www.tiktok.com",
        "reddit": "https://www.reddit.com",
        "facebook": "https://www.facebook.com",
        "github": "https://github.com",
        "twitch": "https://www.twitch.tv",
    }

    VERB_PREFIXES = (
        "open ",
        "launch ",
        "start ",
        "run ",
        "abre ",
        "abreme ",
        "abrime ",
        "inicia ",
        "iniciar ",
        "ejecuta ",
        "ejecutar ",
        "abre la app de ",
        "open the app ",
    )

    NOISE_PREFIXES = (
        "the app ",
        "app ",
        "application ",
        "program ",
        "programa ",
        "juego ",
        "game ",
        "website ",
        "site ",
        "social media ",
        "social ",
    )

    START_MENU_DIRS = (
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    )

    COOLDOWN_SECONDS = 15.0
    HELPER_NAMES = {"update.exe", "updater.exe", "squirrel.exe", "setup.exe", "installer.exe"}

    def __init__(
        self,
        router: SystemActionRouter,
        memory_store: LongTermMemoryStore | None = None,
    ) -> None:
        self.router = router
        self.guard: ActionGuard = router.guard
        self.memory_store = memory_store
        self.logger = logging.getLogger("caine.interaction.app_launcher")
        self._last_launch_times: dict[str, float] = {}

    def open_application(self, app_alias: str) -> dict[str, object]:
        return self.launch(app_alias).as_dict()

    def open_website(self, target: str) -> dict[str, object]:
        return self._launch_website(target).as_dict()

    def open_folder(self, folder_alias: str) -> dict[str, object]:
        message = self.router.open_folder(folder_alias)
        return LaunchResult(
            success="abriendo" in message.lower() or "cortinas arriba" in message.lower(),
            action="open_folder",
            target=folder_alias.strip(),
            path=folder_alias.strip(),
            message=message,
        ).as_dict()

    def launch_from_text(self, command_text: str) -> dict[str, object]:
        target = self._normalize_text(command_text)
        if not target:
            return LaunchResult(False, "open_app", "", "", "No encontre un objetivo claro para abrir.").as_dict()

        website = self._website_for_target(target)
        if website:
            return self._launch_website(target, website).as_dict()

        return self.launch(target).as_dict()

    def launch(self, target: str) -> LaunchResult:
        normalized = self._normalize_text(target)
        if not normalized:
            return LaunchResult(False, "open_app", "", "", "No hay nada claro para abrir.")

        website = self._website_for_target(normalized)
        if website:
            return self._launch_website(normalized, website)

        if not self.guard.is_allowed_app(normalized):
            self.logger.warning("ActionGuard bloqueo app %s", normalized)
            return LaunchResult(False, "open_app", normalized, "", f"ActionGuard no permitio abrir '{normalized}'.")

        if not self._can_launch(normalized):
            return LaunchResult(
                False,
                "open_app",
                normalized,
                "",
                f"'{normalized}' esta en cooldown. Espera unos segundos antes de repetir el truco.",
            )

        shell_target = self._resolve_shell_target(normalized)
        if shell_target is None:
            self.logger.warning("No encontre acceso seguro para %s", normalized)
            return LaunchResult(False, "open_app", normalized, "", f"No encontre un acceso seguro para '{normalized}'.")

        self.logger.info("Launching app target=%s path=%s", normalized, shell_target)
        try:
            os.startfile(shell_target)
        except Exception as error:
            self.logger.error("Launch failed for %s: %s", shell_target, error)
            return LaunchResult(False, "open_app", normalized, str(shell_target), f"Launch failed: {error}")

        self._last_launch_times[normalized] = time.monotonic()
        self._remember_launch(normalized, shell_target)
        return LaunchResult(True, "open_app", normalized, shell_target, f"Aplicacion abierta: {normalized}")

    def _launch_website(self, target: str, url: str | None = None) -> LaunchResult:
        normalized = self._normalize_text(target)
        final_url = url or self._website_for_target(normalized)
        if not final_url:
            return LaunchResult(False, "open_app", normalized, "", f"No tengo una web configurada para '{normalized}'.")

        self.logger.info("Launching website target=%s url=%s", normalized, final_url)
        try:
            webbrowser.open(final_url)
        except Exception as error:
            self.logger.error("Fallo al abrir web %s: %s", final_url, error)
            return LaunchResult(False, "open_app", normalized, final_url, f"No pude abrir '{final_url}': {error}")

        self._last_launch_times[normalized] = time.monotonic()
        self._remember_launch(normalized, final_url)
        return LaunchResult(True, "open_app", normalized, final_url, f"Sitio abierto: {final_url}")

    def _remember_launch(self, normalized: str, path: str) -> None:
        if self.memory_store is None:
            return

        source = f"Lanzamiento correcto desde interaction layer: {normalized} -> {path}"
        self.memory_store.store_preference("recent_apps", normalized, source)
        self.memory_store.store_preference("favorite_apps", normalized, source)
        self.memory_store.record_command_usage(f"launch:{normalized}")

    def _can_launch(self, normalized: str) -> bool:
        last_launch = self._last_launch_times.get(normalized, 0.0)
        return (time.monotonic() - last_launch) >= self.COOLDOWN_SECONDS

    def _resolve_shell_target(self, normalized: str) -> str | None:
        # Primero intentar usar el diccionario de config (ej: notepad -> notepad.exe)
        config_target = self.guard.config.allowed_apps.get(normalized.lower())
        if config_target:
            return config_target

        display_name = self.APP_ALIASES.get(normalized, normalized.title())

        # Buscar accesos directos en el menu inicio
        shortcut = self._search_start_menu_shortcut(display_name, normalized)
        if shortcut is not None:
            return str(shortcut)

        # Como ultimo intento, dejar que Windows intente ejecutar el alias si es global
        if display_name and not display_name.lower().endswith(".exe"):
            return display_name

        return None

    def _search_start_menu_shortcut(self, display_name: str, normalized: str) -> Path | None:
        wanted = display_name.lower()
        alias = normalized.lower()
        for base_dir in self.START_MENU_DIRS:
            if not base_dir.exists():
                continue
            for shortcut in base_dir.rglob("*.lnk"):
                name = shortcut.stem.lower()
                if wanted not in name and alias not in name:
                    continue
                return shortcut
        return None

    def _normalize_text(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        normalized = normalized.strip("¿?¡!.,:;\"'()[]{}")

        for prefix in self.VERB_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break

        for prefix in self.NOISE_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()

        replacements = {
            "discord app": "discord",
            "discord desktop": "discord",
            "google chrome": "chrome",
            "mozilla firefox": "firefox",
            "microsoft edge": "edge",
            "spotify app": "spotify",
            "minecraft launcher": "minecraft",
            "steam app": "steam",
            "bloc de notas": "notepad",
            "calculator": "calculator",
            "calculadora": "calculator",
        }
        return replacements.get(normalized, normalized)

    def _website_for_target(self, normalized: str) -> str | None:
        if normalized in self.WEBSITE_TARGETS:
            return self.WEBSITE_TARGETS[normalized]
        if normalized.startswith(("http://", "https://")):
            return normalized
        return None
