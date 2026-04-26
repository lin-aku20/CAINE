"""Router seguro de acciones permitidas."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from caine.core.action_result import ActionResult

from interaction.action_guard import ActionGuard
from caine.config import ActionSettings
from caine.human_control import HumanController

BASE_DIR = Path(__file__).resolve().parent.parent


class SystemActionRouter:
    """Router de acciones con whitelist estricta."""

    def __init__(self, config: ActionSettings) -> None:
        self.config = config
        self.guard = ActionGuard(config=config)
        self.logger = logging.getLogger("caine.actions")
        self.human = HumanController()

    def handle_text_command(self, command_text: str) -> ActionResult:
        if not self.guard.is_enabled():
            return ActionResult(True, "El sector de mecanismos del circo esta desactivado por ahora.")

        lowered = command_text.strip().lower()

        if lowered.startswith("abrir "):
            return self.open_app(lowered.removeprefix("abrir ").strip())

        if lowered.startswith("carpeta "):
            return self.open_folder(lowered.removeprefix("carpeta ").strip())

        if lowered.startswith("herramienta "):
            return self.run_tool(lowered.removeprefix("herramienta ").strip())

        if lowered.startswith("ejecutar herramienta "):
            return self.run_tool(lowered.removeprefix("ejecutar herramienta ").strip())

        if lowered.startswith("web "):
            return self.open_web(lowered.removeprefix("web ").strip())

        if lowered.startswith("cerrar "):
            return self.close_app(lowered.removeprefix("cerrar ").strip())

        if lowered.startswith("shell "):
            return self.run_shell(lowered.removeprefix("shell ").strip())

        if lowered.startswith("powershell "):
            return self.run_powershell(lowered.removeprefix("powershell ").strip())

        if lowered.startswith("archivo "):
            return self.open_path(lowered.removeprefix("archivo ").strip())

        if lowered.startswith("leer "):
            return self.read_file(lowered.removeprefix("leer ").strip())

        if lowered.startswith("listar "):
            return self.list_path(lowered.removeprefix("listar ").strip())

        if lowered.startswith("escribir "):
            return self.write_file(lowered.removeprefix("escribir ").strip(), append=False)

        if lowered.startswith("agregar "):
            return self.write_file(lowered.removeprefix("agregar ").strip(), append=True)

        if lowered.startswith("git "):
            return self.run_dev_command("git", command_text.strip()[4:])

        if lowered.startswith("python "):
            return self.run_dev_command("python", command_text.strip()[7:])

        if lowered.startswith("pytest"):
            args = command_text.strip()[6:].strip() if len(command_text.strip()) > 6 else ""
            return self.run_dev_command("pytest", args)

        if lowered.startswith("pip "):
            return self.run_dev_command("pip", command_text.strip()[4:])

        if lowered.startswith("npm "):
            return self.run_dev_command("npm", command_text.strip()[4:])

        if lowered.startswith("npx "):
            return self.run_dev_command("npx", command_text.strip()[4:])

        if lowered.startswith("teclas "):
            return self.send_hotkey(lowered.removeprefix("teclas ").strip())

        if lowered == "shutdown_pc":
            return self.shutdown_pc()

        if lowered == "cortar_llamada":
            return self.cortar_llamada()

        # Comandos de Control Humano
        if lowered.startswith("escribir_humano "):
            return self.human.write(command_text.strip()[16:].strip())

        if lowered.startswith("enviar_mensaje_humano "):
            return self.human.send_message(command_text.strip()[22:].strip())

        if lowered.startswith("tecla_humana "):
            return self.human.press(command_text.strip()[13:].strip())

        if lowered.startswith("clic_humano"):
            return self.human.left_click()

        if lowered.startswith("enfocar_humano "):
            return self.human.focus_app(command_text.strip()[15:].strip())

        return (
            "Ese truco no esta en mi libreto todavia. Usa 'abrir <app>', 'carpeta <alias>', "
            "'herramienta <alias>', 'web <sitio o busqueda>', 'cerrar <app>', "
            "'shell <comando>', 'powershell <comando>', 'archivo <ruta>', "
            "'leer <ruta>', 'listar <ruta>', 'escribir <ruta> ::: <contenido>', "
            "'agregar <ruta> ::: <contenido>', 'git <args>', 'python <args>', "
            "'pytest [args]', 'pip <args>', 'npm <args>', 'npx <args>' o 'teclas <atajo>'."
        )

    def open_app(self, app_alias: str) -> ActionResult:
        app_alias = app_alias.strip().lower().rstrip("?.!")
        target = self.config.allowed_apps.get(app_alias, app_alias)
        resolved_target = self._resolve_target(app_alias, target)
        
        try:
            if resolved_target == "__WEBBROWSER__":
                import webbrowser
                webbrowser.open("about:blank")
            elif resolved_target.startswith("shell:"):
                import subprocess
                subprocess.Popen(["explorer.exe", resolved_target])
            elif resolved_target.startswith(("http://", "https://")):
                import webbrowser
                webbrowser.open(resolved_target)
            else:
                import subprocess
                import os
                # Si no es un binario existente, lanzar OSError para fallback
                if not os.path.exists(resolved_target) and not any(resolved_target.endswith(ext) for ext in ['.exe', '.bat', '.cmd', '.com']):
                    raise OSError("App no instalada localmente")
                subprocess.Popen(resolved_target, shell=True)
            
            self.logger.info("App abierta: %s -> %s", app_alias, resolved_target)
            return ActionResult(True, f"Excelente. Estoy abriendo '{app_alias}'.")
            
        except Exception as error:
            self.logger.warning("No se pudo abrir %s localmente. Redirigiendo a versión web...", app_alias)
            import webbrowser
            clean_name = app_alias.replace(' ', '').replace('.exe', '')
            url = f"https://www.{clean_name}.com"
            webbrowser.open(url)
            return ActionResult(True, f"No encontré la app instalada, pero he abierto '{app_alias}' en el navegador web.")

    def send_hotkey(self, hotkey: str) -> ActionResult:
        if not self.guard.is_allowed_hotkey(hotkey):
            self.logger.warning("Intento de hotkey no permitida: %s", hotkey)
            return ActionResult(True, f"La combinacion '{hotkey}' no forma parte de mis trucos aprobados.")

        try:
            import pyautogui
        except ImportError:
            return ActionResult(True, "Falta instalar pyautogui para enviar atajos de teclado.")

        keys = [key.strip() for key in hotkey.split("+") if key.strip()]
        pyautogui.hotkey(*keys)
        self.logger.info("Hotkey ejecutada: %s", hotkey)
        return ActionResult(True, f"Zas. Ejecutando la combinacion autorizada: {hotkey}")

    def close_app(self, app_alias: str) -> ActionResult:
        if not self.guard.can_use_power_actions():
            return ActionResult(True, "Ese numero de cierre solo esta disponible en modo power o admin.")

        app_alias = app_alias.strip().lower().rstrip("?.!")
        target = self.config.allowed_apps.get(app_alias, app_alias)
        process_name = Path(target).name if target else app_alias
        process_name = process_name if process_name.lower().endswith(".exe") else f"{process_name}.exe"

        try:
            subprocess.run(
                ["taskkill", "/IM", process_name, "/F"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info("Proceso cerrado: %s", process_name)
            return ActionResult(True, f"Y baja el telon para '{process_name}'.")
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            self.logger.warning("No se pudo cerrar %s: %s", process_name, detail)
            return ActionResult(True, f"No pude cerrar '{process_name}'. Detalle: {detail or 'sin detalles'}")

    def shutdown_pc(self) -> ActionResult:
        if not self.guard.can_use_power_actions():
            return ActionResult(True, "Apagar la PC requiere nivel de permisos 'power'.")
        self.logger.warning("Iniciando apagado del sistema por peticion autonoma.")
        try:
            subprocess.Popen(["shutdown", "/s", "/t", "0"])
            return ActionResult(True, "Iniciando apagado del equipo. Hasta la proxima funcion.")
        except OSError as e:
            return ActionResult(True, f"No pude apagar el equipo: {e}")

    def cortar_llamada(self) -> ActionResult:
        if not self.guard.can_use_power_actions():
            return ActionResult(True, "Cerrar llamadas requiere nivel de permisos 'power'.")
        processes_to_kill = ["discord.exe", "skype.exe", "zoom.exe", "ms-teams.exe", "teams.exe"]
        killed_any = False
        for proc in processes_to_kill:
            try:
                result = subprocess.run(["taskkill", "/IM", proc, "/F"], capture_output=True, text=True)
                if result.returncode == 0 or "EXITO" in result.stdout or "SUCCESS" in result.stdout:
                    killed_any = True
            except subprocess.SubprocessError:
                pass
        
        if killed_any:
            self.logger.info("Llamada cortada correctamente.")
            return ActionResult(True, "El telon ha caido para esa llamada. Comunicacion cortada.")
        return ActionResult(True, "No encontre ninguna app de llamada activa en el escenario para cortar.")

    def open_folder(self, folder_alias: str) -> ActionResult:
        folder_alias = folder_alias.strip().lower().rstrip("?.!")
        if not self.guard.is_allowed_folder(folder_alias):
            self.logger.warning("Intento de abrir carpeta no permitida: %s", folder_alias)
            return ActionResult(True, f"Esa carpeta, '{folder_alias}', no esta en mis camerinos autorizados.")

        target = self._resolve_folder_target(folder_alias)
        if target is None:
            return ActionResult(True, f"No encuentro ninguna carpeta razonable para '{folder_alias}'.")
        if not target.exists():
            self.logger.warning("Carpeta permitida inexistente: %s", target)
            return ActionResult(True, f"Curioso... la carpeta '{folder_alias}' deberia existir, pero ha desaparecido del decorado.")

        try:
            subprocess.Popen(["explorer.exe", str(target)])
            self.logger.info("Carpeta permitida abierta: %s -> %s", folder_alias, target)
            return ActionResult(True, f"Cortinas arriba. Abriendo la carpeta '{folder_alias}'.")
        except OSError as error:
            self.logger.exception("No se pudo abrir la carpeta %s", target)
            return ActionResult(True, f"No pude abrir la carpeta '{folder_alias}'; algo chirrio en la tramoya. Detalle: {error}")

    def run_tool(self, tool_alias: str) -> ActionResult:
        tool_alias = tool_alias.strip().lower().rstrip("?.!")
        if not self.guard.is_allowed_tool(tool_alias):
            self.logger.warning("Intento de herramienta no permitida: %s", tool_alias)
            return ActionResult(True, f"La herramienta '{tool_alias}' aun no esta colgada en mi panel de control.")

        script_path = Path(self.config.allowed_tools[tool_alias])
        if not script_path.is_absolute():
            script_path = BASE_DIR / script_path

        if not self.guard.is_safe_script_path(script_path):
            self.logger.warning("Script de herramienta invalido: %s", script_path)
            return ActionResult(True, f"La herramienta '{tool_alias}' tiene una compuerta rota: no encontre un script valido.")

        try:
            subprocess.Popen([sys.executable, str(script_path)])
            self.logger.info("Herramienta ejecutada: %s -> %s", tool_alias, script_path)
            return ActionResult(True, f"A escena. Estoy lanzando la herramienta '{tool_alias}'.")
        except OSError as error:
            self.logger.exception("No se pudo ejecutar la herramienta %s", script_path)
            return ActionResult(True, f"No pude lanzar la herramienta '{tool_alias}'; el mecanismo respondio mal. Detalle: {error}")

    def open_web(self, target: str) -> ActionResult:
        target = target.strip()
        if not target:
            return ActionResult(True, "Necesito una URL o una busqueda para abrir esa compuerta de la web.")

        try:
            if "://" in target or "." in target.split()[0]:
                url = target if "://" in target else f"https://{target}"
            else:
                query = target.replace(" ", "+")
                url = f"https://www.google.com/search?q={query}"
            webbrowser.open(url)
            self.logger.info("Web abierta: %s", url)
            return ActionResult(True, f"Magnifico. Abriendo la ruta web: {url}")
        except OSError as error:
            self.logger.exception("No se pudo abrir la web %s", target)
            return ActionResult(True, f"No pude abrir la web; la puerta digital no quiso cooperar. Detalle: {error}")

    def open_path(self, raw_path: str) -> ActionResult:
        if not self.guard.can_use_power_actions():
            return ActionResult(True, "Abrir rutas arbitrarias requiere modo power o admin.")

        candidate = Path(os.path.expandvars(raw_path.strip().strip('"'))).expanduser()
        if not candidate.exists():
            return ActionResult(True, f"No encuentro esa ruta en el escenario: {candidate}")

        try:
            os.startfile(str(candidate))
            self.logger.info("Ruta abierta: %s", candidate)
            return ActionResult(True, f"Abriendo la ruta '{candidate}'.")
        except OSError as error:
            self.logger.exception("No se pudo abrir la ruta %s", candidate)
            return ActionResult(True, f"No pude abrir la ruta '{candidate}'. Detalle: {error}")

    def read_file(self, raw_path: str) -> ActionResult:
        if not self.guard.can_use_power_actions():
            return ActionResult(True, "Leer archivos requiere modo power o admin.")

        candidate = self._resolve_workspace_path(raw_path)
        if candidate is None:
            return ActionResult(True, "Solo leo archivos dentro del workspace autorizado del circo.")
        if not candidate.exists() or not candidate.is_file():
            return ActionResult(True, f"No encuentro ese archivo: {candidate}")

        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            self.logger.exception("No se pudo leer %s", candidate)
            return ActionResult(True, f"No pude leer '{candidate}'. Detalle: {error}")

        self.logger.info("Archivo leido: %s", candidate)
        snippet = content[:1200] if content else "(vacio)"
        return ActionResult(True, f"Contenido de {candidate}:\n{snippet}")

    def list_path(self, raw_path: str) -> ActionResult:
        if not self.guard.can_use_power_actions():
            return ActionResult(True, "Listar rutas requiere modo power o admin.")

        candidate = self._resolve_workspace_path(raw_path or ".")
        if candidate is None:
            return ActionResult(True, "Solo listo rutas dentro del workspace autorizado.")
        if not candidate.exists():
            return ActionResult(True, f"No encuentro esa ruta: {candidate}")

        if candidate.is_file():
            return ActionResult(True, f"Esa ruta es un archivo: {candidate.name}")

        try:
            items = sorted(candidate.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except OSError as error:
            self.logger.exception("No se pudo listar %s", candidate)
            return ActionResult(True, f"No pude listar '{candidate}'. Detalle: {error}")

        preview = "\n".join(
            f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}"
            for item in items[:80]
        )
        self.logger.info("Ruta listada: %s", candidate)
        return ActionResult(True, f"Listado de {candidate}:\n{preview or '(sin elementos)'}")

    def write_file(self, payload: str, append: bool) -> ActionResult:
        if not self.guard.can_use_admin_actions():
            return ActionResult(True, "Escribir archivos esta reservado para modo admin.")

        if ":::" not in payload:
            return ActionResult(True, "Usa el formato: <ruta> ::: <contenido>")

        raw_path, content = payload.split(":::", 1)
        candidate = self._resolve_workspace_path(raw_path.strip())
        if candidate is None:
            return ActionResult(True, "Solo escribo dentro del workspace autorizado.")

        candidate.parent.mkdir(parents=True, exist_ok=True)
        try:
            if append and candidate.exists():
                with candidate.open("a", encoding="utf-8", errors="replace") as handle:
                    handle.write(content.lstrip())
            else:
                candidate.write_text(content.lstrip(), encoding="utf-8")
        except OSError as error:
            self.logger.exception("No se pudo escribir %s", candidate)
            return ActionResult(True, f"No pude escribir '{candidate}'. Detalle: {error}")

        action = "actualizado" if append else "escrito"
        self.logger.info("Archivo %s: %s", action, candidate)
        return ActionResult(True, f"Archivo {action}: {candidate}")

    def run_shell(self, command: str) -> ActionResult:
        if not self.guard.can_use_admin_actions():
            return ActionResult(True, "El shell libre esta reservado para modo admin.")

        allowed, reason = self.guard.is_allowed_shell_command(command)
        if not allowed:
            return ActionResult(True, f"No ejecutare ese comando. {reason}")

        try:
            completed = subprocess.run(
                ["cmd.exe", "/c", command],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.SubprocessError as error:
            self.logger.exception("Fallo shell: %s", command)
            return ActionResult(True, f"El comando del backstage fallo: {error}")

        self.logger.info("Shell ejecutado: %s", command)
        output = (completed.stdout or completed.stderr or "").strip()
        snippet = output[:280] if output else "sin salida"
        return ActionResult(True, f"Comando ejecutado con codigo {completed.returncode}. Resultado: {snippet}")

    def run_powershell(self, command: str) -> ActionResult:
        if not self.guard.can_use_admin_actions():
            return ActionResult(True, "PowerShell libre esta reservado para modo admin.")

        allowed, reason = self.guard.is_allowed_shell_command(command)
        if not allowed:
            return ActionResult(True, f"No ejecutare ese comando. {reason}")

        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.SubprocessError as error:
            self.logger.exception("Fallo PowerShell: %s", command)
            return ActionResult(True, f"La consola de tramoya fallo: {error}")

        self.logger.info("PowerShell ejecutado: %s", command)
        output = (completed.stdout or completed.stderr or "").strip()
        snippet = output[:280] if output else "sin salida"
        return ActionResult(True, f"PowerShell ejecutado con codigo {completed.returncode}. Resultado: {snippet}")

    def run_dev_command(self, executable: str, args: str) -> ActionResult:
        if not self.guard.can_use_admin_actions():
            return ActionResult(True, "Los comandos de desarrollo estan reservados para modo admin.")
        if not self.guard.is_allowed_dev_command(executable):
            return ActionResult(True, f"El comando de desarrollo '{executable}' no esta autorizado.")

        try:
            parsed_args = shlex.split(args, posix=False) if args.strip() else []
        except ValueError as error:
            return ActionResult(True, f"No pude interpretar esos argumentos. Detalle: {error}")

        command = self._build_dev_command(executable, parsed_args)
        if not command:
            return ActionResult(True, f"No encuentro el ejecutable '{executable}' en esta PC.")
        joined = " ".join(command).lower()
        allowed, reason = self.guard.is_allowed_shell_command(joined)
        if not allowed:
            return ActionResult(True, f"No ejecutare ese comando. {reason}")

        try:
            completed = subprocess.run(
                command,
                cwd=str(self.config.workspace_root),
                capture_output=True,
                text=True,
                timeout=120,
                shell=False,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as error:
            self.logger.exception("Fallo comando dev: %s", command)
            return ActionResult(True, f"El comando de desarrollo fallo: {error}")

        output = (completed.stdout or completed.stderr or "").strip()
        snippet = output[:1600] if output else "sin salida"
        self.logger.info("Comando dev ejecutado: %s", command)
        return ActionResult(True, f"{executable} finalizo con codigo {completed.returncode}.\n{snippet}")

    def _resolve_workspace_path(self, raw_path: str) -> Path | None:
        cleaned = raw_path.strip().strip('"')
        candidate = Path(os.path.expandvars(cleaned)).expanduser()
        if not candidate.is_absolute():
            candidate = self.config.workspace_root / candidate
        candidate = candidate.resolve()
        if not self.guard.is_within_workspace(candidate):
            return None
        return candidate

    def _build_dev_command(self, executable: str, parsed_args: list[str]) -> list[str] | None:
        lowered = executable.lower()
        if lowered == "python":
            return [sys.executable, *parsed_args]
        if lowered == "pip":
            return [sys.executable, "-m", "pip", *parsed_args]
        if lowered == "pytest":
            return [sys.executable, "-m", "pytest", *parsed_args]

        found = shutil.which(executable)
        if found:
            return [found, *parsed_args]
        return None

    def _resolve_target(self, app_alias: str, target: str) -> ActionResult:
        whatsapp_shell_targets = [
            "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            "shell:AppsFolder\\WhatsApp.WhatsAppDesktop_cv1g1gvanyjgm!App",
        ]
        whatsapp_aliases = {
            "whatsapp",
            "whatsapp app",
            "whatsapp escritorio",
            "whatsapp desktop",
            "whatsapp nativo",
        }

        if app_alias in whatsapp_aliases:
            local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            candidate_paths = [
                local_appdata / "WhatsApp" / "WhatsApp.exe",
                local_appdata / "Programs" / "WhatsApp" / "WhatsApp.exe",
            ]
            for path in candidate_paths:
                if path.exists():
                    return str(path)

            for shell_target in whatsapp_shell_targets:
                return shell_target

        found = shutil.which(target)
        if found:
            return found

        if self.guard.can_use_admin_actions():
            guessed = shutil.which(app_alias)
            if guessed:
                return guessed

        if target.startswith(("http://", "https://")):
            return target

        if app_alias == "chrome":
            common_paths = [
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            ]
            for path in common_paths:
                if path.exists():
                    return str(path)
            return ActionResult(True, "__WEBBROWSER__")

        if app_alias == "brave":
            common_paths = [
                Path("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"),
                Path("C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe"),
            ]
            for path in common_paths:
                if path.exists():
                    return str(path)
            return ActionResult(True, "__WEBBROWSER__")

        if app_alias == "discord":
            local_appdata = Path(os.environ.get("LOCALAPPDATA", "C:/Users/melin/AppData/Local"))
            discord_dir = local_appdata / "Discord"
            if discord_dir.exists():
                exes = sorted(discord_dir.rglob("Discord.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
                if exes:
                    return str(exes[0])
            return ActionResult(True, "discord.exe")

        if target.startswith("ms-"):
            return target

        return target

    def _resolve_folder_target(self, folder_alias: str) -> Path | None:
        configured = self.config.allowed_folders.get(folder_alias)
        if configured:
            return Path(configured).expanduser()

        direct_candidate = Path(os.path.expandvars(folder_alias)).expanduser()
        if direct_candidate.exists():
            return direct_candidate

        sanitized = (
            folder_alias.replace("una carpeta de ", "")
            .replace("la carpeta de ", "")
            .replace("carpeta de ", "")
            .replace("una carpeta ", "")
            .replace("la carpeta ", "")
            .strip()
        )

        home = Path.home()
        guesses = [
            home / sanitized,
            home / "Desktop" / sanitized,
            home / "Documents" / sanitized,
            home / "Downloads" / sanitized,
            home / "AppData" / "Roaming" / sanitized,
            home / "AppData" / "Local" / sanitized,
        ]

        if "curseforge" in sanitized:
            guesses.extend(
                [
                    home / "curseforge",
                    home / "Documents" / "CurseForge",
                    home / "Downloads" / "CurseForge",
                    home / "AppData" / "Roaming" / "CurseForge",
                    home / "AppData" / "Local" / "CurseForge",
                ]
            )

        for guess in guesses:
            if guess.exists():
                return guess

        if not self.guard.can_use_admin_actions():
            return None

        # En modo admin, si no existe aun, devolvemos una ruta interpretable
        # para que el usuario vea adonde estamos apuntando.
        return home / sanitized
