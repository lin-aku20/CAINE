"""
Carga del prompt de personalidad desde archivo.
"""

from __future__ import annotations

from pathlib import Path


class PersonalityLoader:
    """Lee y entrega la personalidad del asistente."""

    def __init__(self, personality_file: Path) -> None:
        self.personality_file = Path(personality_file)

    def load_text(self) -> str:
        """Carga el contenido del archivo de personalidad."""
        if not self.personality_file.exists():
            raise FileNotFoundError(
                f"No se encontro el archivo de personalidad: {self.personality_file}"
            )

        return self.personality_file.read_text(encoding="utf-8").strip()

