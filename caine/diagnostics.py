"""Autodiagnostico de CAINE al iniciar."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import json

from caine.screen_awareness import ScreenAwareness
from voice.voice_pipeline import VoicePipeline


@dataclass(slots=True)
class DiagnosticItem:
    name: str
    ok: bool
    detail: str


class DiagnosticsManager:
    """Ejecuta chequeos de salud y guarda un reporte local."""

    def __init__(self, report_file: Path) -> None:
        self.report_file = Path(report_file)
        self.report_file.parent.mkdir(parents=True, exist_ok=True)

    def run_startup_checks(self, brain_ok: tuple[bool, str], voice: VoicePipeline, awareness: ScreenAwareness) -> list[DiagnosticItem]:
        voice_checks = voice.prepare()
        screen_context = awareness.get_active_context(include_screenshot=False)

        items = [
            DiagnosticItem("ollama", brain_ok[0], brain_ok[1]),
            DiagnosticItem(
                "voz",
                all(result.ok for result in voice_checks),
                " | ".join(result.message for result in voice_checks),
            ),
            DiagnosticItem(
                "screen_awareness",
                bool(screen_context.app_name or screen_context.window_title),
                screen_context.summary() or "Sin ventana activa detectable por ahora.",
            ),
        ]
        self._save_report(items)
        return items

    def _save_report(self, items: list[DiagnosticItem]) -> None:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "items": [asdict(item) for item in items],
        }
        self.report_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
