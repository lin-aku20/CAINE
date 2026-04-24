"""Asistencia segura y no intrusiva para Minecraft."""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass(slots=True)
class MinecraftContext:
    detected: bool
    process_name: str = ""


class MinecraftAssistant:
    """Detecta Minecraft y ofrece solo asistencia contextual."""

    def detect(self) -> MinecraftContext:
        for process in psutil.process_iter(["name"]):
            name = (process.info.get("name") or "").lower()
            if "minecraft" in name or name == "javaw.exe":
                return MinecraftContext(detected=True, process_name=name)
        return MinecraftContext(detected=False)

    def describe_help(self) -> str:
        return (
            "Puedo ofrecer contexto y asistencia para Minecraft, pero no automatizare gameplay "
            "ni acciones dentro del juego sin confirmacion explicita."
        )
