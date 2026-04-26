"""
Carga y validacion de la configuracion central de CAINE.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class OllamaSettings:
    base_url: str = "http://localhost:11434/v1"
    primary_model: str = "llama3:latest"
    fallback_model: str = "llama3:latest"
    api_key: str = "ollama"
    timeout_seconds: int = 120


@dataclass(slots=True)
class MemorySettings:
    conversation_limit: int = 12
    long_term_file: Path = BASE_DIR / "memory" / "caine_memory.db"
    legacy_json_file: Path = BASE_DIR / "memory" / "long_term_memory.json"
    max_context_items: int = 5


@dataclass(slots=True)
class VoiceSettings:
    enabled: bool = False
    wake_word: str = "hey caine"
    stt_provider: str = "vosk"
    tts_provider: str = "pyttsx3"
    vosk_model_path: Path = BASE_DIR / "models" / "vosk"
    wakeword_model_path: Path = BASE_DIR / "models" / "wakeword"
    sample_rate: int = 16000
    tts_rate: int = 185
    wake_chunk_seconds: float = 1.8
    command_capture_seconds: float = 6.0
    post_speech_cooldown_seconds: float = 1.2
    wake_variants: list[str] = field(
        default_factory=lambda: ["hey caine", "hey kane", "ok caine", "caine", "despierta", "caine despierta"]
    )


@dataclass(slots=True)
class ActionSettings:
    enabled: bool = True
    permission_mode: str = "power"
    workspace_root: Path = BASE_DIR
    allowed_apps: dict[str, str] = field(
        default_factory=lambda: {
            "notepad": "notepad.exe",
            "bloc de notas": "notepad.exe",
            "calculator": "calc.exe",
            "calculadora": "calc.exe",
            "explorer": "explorer.exe",
            "explorador": "explorer.exe",
            "paint": "mspaint.exe",
            "terminal": "wt.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "taskmgr": "taskmgr.exe",
            "administrador de tareas": "taskmgr.exe",
            "snippingtool": "SnippingTool.exe",
            "recortes": "SnippingTool.exe",
            "settings": "ms-settings:",
            "configuracion": "ms-settings:",
            "whatsapp": "https://web.whatsapp.com",
            "whatsapp web": "https://web.whatsapp.com",
            "discord": "discord.exe",
            "steam": "steam.exe",
        }
    )
    allowed_folders: dict[str, str] = field(
        default_factory=lambda: {
            "desktop": str(Path.home() / "Desktop"),
            "escritorio": str(Path.home() / "Desktop"),
            "documents": str(Path.home() / "Documents"),
            "documentos": str(Path.home() / "Documents"),
            "downloads": str(Path.home() / "Downloads"),
            "descargas": str(Path.home() / "Downloads"),
            "pictures": str(Path.home() / "Pictures"),
            "imagenes": str(Path.home() / "Pictures"),
            "music": str(Path.home() / "Music"),
            "musica": str(Path.home() / "Music"),
            "videos": str(Path.home() / "Videos"),
            "videos personales": str(Path.home() / "Videos"),
        }
    )
    allowed_tools: dict[str, str] = field(
        default_factory=lambda: {
            "diagnostico": "verify_environment.py",
            "diagnóstico": "verify_environment.py",
            "verificar entorno": "verify_environment.py",
            "verificar ollama": "verify_ollama.py",
            "ollama": "verify_ollama.py",
            "caine": "main.py",
        }
    )
    allowed_hotkeys: list[str] = field(
        default_factory=lambda: ["ctrl+shift+esc", "win+d", "alt+tab"]
    )
    blocked_shell_patterns: list[str] = field(
        default_factory=lambda: [
            "format ",
            "del /f",
            "rd /s",
            "shutdown /s",
            "shutdown /r",
            "reg delete",
            "bcdedit",
            "diskpart",
            "cipher /w",
        ]
    )
    allowed_dev_commands: list[str] = field(
        default_factory=lambda: ["git", "python", "pytest", "pip", "npm", "npx"]
    )
    log_file: Path = BASE_DIR / "logs" / "actions.log"


@dataclass(slots=True)
class LoggingSettings:
    log_file: Path = BASE_DIR / "logs" / "caine.log"
    level: str = "INFO"


@dataclass(slots=True)
class OverlaySettings:
    enabled: bool = True
    title: str = "CAINE"
    geometry: str = "420x120+20+20"
    always_on_top: bool = True


@dataclass(slots=True)
class AwarenessSettings:
    enabled: bool = True
    capture_screenshots: bool = True
    screenshots_dir: Path = BASE_DIR / "logs" / "screens"


@dataclass(slots=True)
class WorldSettings:
    enabled: bool = True
    scan_interval_seconds: float = 2.0
    snapshot_interval_seconds: float = 30.0
    ocr_interval_seconds: float = 45.0
    inactivity_seconds: int = 600
    repeated_behavior_seconds: int = 900
    remember_app_usage: bool = True
    detect_running_apps: bool = True


@dataclass(slots=True)
class AutonomySettings:
    second_mouse: bool = False
    enabled: bool = True
    commentary_cooldown_seconds: float = 90.0
    same_event_cooldown_seconds: float = 240.0
    minimum_idle_check_seconds: float = 600.0
    max_commentary_per_hour: int = 10


@dataclass(slots=True)
class InteractionSettings:
    enabled: bool = True
    mouse_duration_seconds: float = 0.15
    safe_screen_margin: int = 8
    typing_interval_seconds: float = 0.01


@dataclass(slots=True)
class DiagnosticsSettings:
    report_file: Path = BASE_DIR / "logs" / "startup_report.json"
    errors_file: Path = BASE_DIR / "logs" / "errors.log"


@dataclass(slots=True)
class ServiceSettings:
    service_name: str = "CAINE"
    display_name: str = "CAINE Local AI Assistant"
    description: str = "Servicio persistente de CAINE para supervision y reinicio automatico."
    auto_start: bool = True
    restart_delay_seconds: int = 5


@dataclass(slots=True)
class MinecraftSettings:
    enabled: bool = True
    confirm_before_actions: bool = True


@dataclass(slots=True)
class DesktopSettings:
    enabled: bool = True
    scan_interval_seconds: float = 3.0
    ocr_every_n_scans: int = 3
    diff_threshold: float = 0.025
    auto_talk_screen_events: bool = True
    microphone_enabled: bool = True
    open_chat_terminal: bool = True
    overlay_always_on_top: bool = False
    terminal_always_on_top: bool = False
    tesseract_cmd: str = ""
    avatar_dir: Path = BASE_DIR / "assets" / "caine"
    microphone_phrase_seconds: float = 5.0
    voice_name_hint: str = "Sabina"
    voice_rate: int = 205
    sapi_rate: int = 2
    sapi_pitch: int = -2
    use_piper_voice: bool = True
    piper_model_path: Path = BASE_DIR / "assets" / "voices" / "piper" / "es_ES-davefx-medium.onnx"
    piper_config_path: Path = BASE_DIR / "assets" / "voices" / "piper" / "es_ES-davefx-medium.onnx.json"
    always_listen_microphone: bool = False
    presence_interval_seconds: float = 120.0
    game_keywords: list[str] = field(
        default_factory=lambda: [
            "minecraft",
            "roblox",
            "genshin",
            "vrchat",
            "steam",
            "curseforge",
            "javaw",
        ]
    )


@dataclass(slots=True)
class CaineConfig:
    personality_file: Path = BASE_DIR / "personality" / "caine.txt"
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    actions: ActionSettings = field(default_factory=ActionSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    awareness: AwarenessSettings = field(default_factory=AwarenessSettings)
    world: WorldSettings = field(default_factory=WorldSettings)
    autonomy: AutonomySettings = field(default_factory=AutonomySettings)
    interaction: InteractionSettings = field(default_factory=InteractionSettings)
    diagnostics: DiagnosticsSettings = field(default_factory=DiagnosticsSettings)
    service: ServiceSettings = field(default_factory=ServiceSettings)
    minecraft: MinecraftSettings = field(default_factory=MinecraftSettings)
    desktop: DesktopSettings = field(default_factory=DesktopSettings)

    @classmethod
    def from_yaml(cls, config_path: Path | None = None) -> "CaineConfig":
        config = cls()
        path = config_path or BASE_DIR / "config" / "config.yaml"
        if not path.exists():
            return config

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        config.personality_file = BASE_DIR / raw.get("personality_file", "personality/caine.txt")
        config.ollama = OllamaSettings(**_merge_dataclass_dict(config.ollama, raw.get("ollama", {})))

        memory_values = _merge_dataclass_dict(config.memory, raw.get("memory", {}))
        memory_values["long_term_file"] = BASE_DIR / memory_values["long_term_file"]
        memory_values["legacy_json_file"] = BASE_DIR / memory_values["legacy_json_file"]
        config.memory = MemorySettings(**memory_values)

        voice_values = _merge_dataclass_dict(config.voice, raw.get("voice", {}))
        voice_values["vosk_model_path"] = BASE_DIR / voice_values["vosk_model_path"]
        voice_values["wakeword_model_path"] = BASE_DIR / voice_values["wakeword_model_path"]
        config.voice = VoiceSettings(**voice_values)

        action_values = _merge_dataclass_dict(config.actions, raw.get("actions", {}))
        action_values["workspace_root"] = BASE_DIR / action_values["workspace_root"]
        action_values["log_file"] = BASE_DIR / action_values["log_file"]
        config.actions = ActionSettings(**action_values)

        logging_values = _merge_dataclass_dict(config.logging, raw.get("logging", {}))
        logging_values["log_file"] = BASE_DIR / logging_values["log_file"]
        config.logging = LoggingSettings(**logging_values)

        overlay_values = _merge_dataclass_dict(config.overlay, raw.get("overlay", {}))
        config.overlay = OverlaySettings(**overlay_values)

        awareness_values = _merge_dataclass_dict(config.awareness, raw.get("awareness", {}))
        awareness_values["screenshots_dir"] = BASE_DIR / awareness_values["screenshots_dir"]
        config.awareness = AwarenessSettings(**awareness_values)

        world_values = _merge_dataclass_dict(config.world, raw.get("world", {}))
        config.world = WorldSettings(**world_values)

        autonomy_values = _merge_dataclass_dict(config.autonomy, raw.get("autonomy", {}))
        config.autonomy = AutonomySettings(**autonomy_values)

        interaction_values = _merge_dataclass_dict(config.interaction, raw.get("interaction", {}))
        config.interaction = InteractionSettings(**interaction_values)

        diagnostics_values = _merge_dataclass_dict(config.diagnostics, raw.get("diagnostics", {}))
        diagnostics_values["report_file"] = BASE_DIR / diagnostics_values["report_file"]
        diagnostics_values["errors_file"] = BASE_DIR / diagnostics_values["errors_file"]
        config.diagnostics = DiagnosticsSettings(**diagnostics_values)

        service_values = _merge_dataclass_dict(config.service, raw.get("service", {}))
        config.service = ServiceSettings(**service_values)

        minecraft_values = _merge_dataclass_dict(config.minecraft, raw.get("minecraft", {}))
        config.minecraft = MinecraftSettings(**minecraft_values)

        desktop_values = _merge_dataclass_dict(config.desktop, raw.get("desktop", {}))
        desktop_values["avatar_dir"] = BASE_DIR / desktop_values["avatar_dir"]
        desktop_values["piper_model_path"] = BASE_DIR / desktop_values["piper_model_path"]
        desktop_values["piper_config_path"] = BASE_DIR / desktop_values["piper_config_path"]
        config.desktop = DesktopSettings(**desktop_values)
        return config


def _merge_dataclass_dict(instance: Any, override: dict[str, Any]) -> dict[str, Any]:
    values = {item.name: getattr(instance, item.name) for item in fields(instance)}
    values.update(override or {})
    return values
