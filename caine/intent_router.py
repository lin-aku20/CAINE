"""Clasificacion local de intenciones antes de actuar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IntentResult:
    category: str
    command_text: str
    reason: str


class IntentRouter:
    """Clasificador ligero y estable basado en reglas."""

    @staticmethod
    def _normalize_open_target(raw_target: str) -> str:
        target = raw_target.strip(" ?!")

        for prefix in (
            "la app de ",
            "el app de ",
            "la aplicacion de ",
            "la aplicación de ",
            "aplicacion de ",
            "aplicación de ",
            "app de ",
        ):
            if target.startswith(prefix):
                target = target[len(prefix):]
                break

        if "whatsapp" in target:
            if any(
                marker in target
                for marker in (
                    "no en navegador",
                    "no navegador",
                    "app nativa",
                    "aplicacion nativa",
                    "aplicación nativa",
                    "escritorio",
                    "desktop",
                    "app",
                )
            ):
                return "whatsapp app"
            return "whatsapp"

        for noise in ("no en navegador", "no navegador", "por favor", "porfa"):
            target = target.replace(noise, "").strip()

        return " ".join(target.split())

    def classify(self, text: str, active_app: str = "") -> IntentResult:
        lowered = text.strip().lower()
        active = active_app.lower()

        for prefix in (
            "programa una web de ",
            "crea una web de ",
            "haz una web de ",
            "crea una pagina de ",
            "crea una página de ",
            "programa una pagina de ",
            "programa una página de ",
        ):
            if lowered.startswith(prefix):
                return IntentResult("desarrollo_web", lowered, "Peticion directa de crear una web.")

        if lowered in {"hazlo", "dale", "pos hazlo", "pues hazlo", "hacelo"}:
            return IntentResult("continuar_tarea", lowered, "Quiere ejecutar la ultima tarea pendiente.")

        for prefix in ("abre una carpeta de ", "abre la carpeta de ", "abre la carpeta ", "abre carpeta ", "abre mis ", "abre mi "):
            if lowered.startswith(prefix):
                normalized = "carpeta " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de abrir una carpeta.")

        for prefix in ("cierra ", "cerra ", "mata "):
            if lowered.startswith(prefix):
                normalized = "cerrar " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de cerrar una app.")

        for prefix in ("abre el archivo ", "abre archivo ", "abre la ruta ", "abre ruta "):
            if lowered.startswith(prefix):
                normalized = "archivo " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de abrir una ruta.")

        for prefix in ("lee el archivo ", "lee archivo ", "mostrar archivo ", "muestra archivo "):
            if lowered.startswith(prefix):
                normalized = "leer " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de leer un archivo.")

        for prefix in ("lista ", "muestra carpeta ", "muestra directorio "):
            if lowered.startswith(prefix):
                normalized = "listar " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de listar una ruta.")

        for prefix in ("ejecuta shell ", "corre shell "):
            if lowered.startswith(prefix):
                normalized = "shell " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de ejecutar shell.")

        for prefix in ("ejecuta powershell ", "corre powershell "):
            if lowered.startswith(prefix):
                normalized = "powershell " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de ejecutar powershell.")

        for prefix in ("ejecuta ", "lanza ", "corre "):
            if lowered.startswith(prefix):
                normalized = "herramienta " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de ejecutar una herramienta.")

        for prefix in ("apaga la pc", "apaga la computadora", "apagar equipo", "apaga el pc", "apagar pc", "apagar computadora"):
            if lowered.startswith(prefix):
                return IntentResult("accion_sistema", "shutdown_pc", "Peticion natural de apagar la computadora.")

        for prefix in ("corta la llamada", "colgar llamada", "cierra la llamada", "corta llamada", "corta la comunicacion"):
            if lowered.startswith(prefix):
                return IntentResult("accion_sistema", "cortar_llamada", "Peticion natural de cortar una llamada.")

        for prefix in ("busca en internet ", "busca en google ", "busca en la web ", "busca ", "busca en web ", "abre web ", "abre la web ", "googlea ", "busqueda de ", "buscar "):
            if lowered.startswith(prefix):
                normalized = "web " + lowered[len(prefix):].strip(" ?!")
                return IntentResult("accion_sistema", normalized, "Peticion natural de busqueda web.")

        if lowered.startswith(
            (
                "abrir ",
                "carpeta ",
                "herramienta ",
                "ejecutar herramienta ",
                "web ",
                "cerrar ",
                "shell ",
                "powershell ",
                "archivo ",
                "leer ",
                "listar ",
                "escribir ",
                "agregar ",
                "git ",
                "python ",
                "pytest",
                "pip ",
                "npm ",
                "npx ",
                "teclas ",
                "/accion ",
                "accion ",
                "open ",
            )
        ):
            return IntentResult("accion_sistema", lowered, "Coincide con comandos de sistema.")

        OPEN_PREFIXES = (
            "puedes abrir ", "puedes abrirme ", "podrias abrir ",
            "abre ", "abreme ", "abrime ",
            "abre el ", "abre la ", "abre los ", "abre las ",
            "inicia ", "inicia el ", "inicia la ",
            "lanza ", "lanza el ", "lanza la ",
            "arranca ", "ejecuta ",
            "ponme ", "pon ", "quiero usar ", "quiero abrir ",
        )
        for prefix in OPEN_PREFIXES:
            if lowered.startswith(prefix):
                normalized = "abrir " + self._normalize_open_target(lowered[len(prefix):])
                return IntentResult("accion_sistema", normalized, "Peticion natural de abrir una app.")

        if lowered.startswith("/"):
            return IntentResult("comando_interno", lowered, "Comienza con slash.")

        if any(token in lowered for token in ("recuerda", "acuerdate", "mi nombre es", "prefiero", "me gusta")):
            return IntentResult("memoria", lowered, "Parece una preferencia o recuerdo.")

        if "minecraft" in lowered or "javaw.exe" in active or "minecraft" in active:
            return IntentResult("minecraft", lowered, "El contexto apunta a Minecraft.")

        if lowered.endswith("?") or lowered.startswith(
            ("que ", "como ", "cuando ", "donde ", "por que ", "quien ", "cuanto ")
        ):
            return IntentResult("pregunta", lowered, "Tiene forma de pregunta.")

        return IntentResult("conversacion", lowered, "No coincide con un flujo especial.")
