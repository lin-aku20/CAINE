"""Capa de percepción unificada de CAINE.

Consolida ContextEngine, ScreenWatcher y DesktopAwareness en una
sola API que produce PerceptionSnapshot — la vista del mundo en
un momento dado.

Uso:
    layer = PerceptionLayer(config)
    snapshot = await layer.get_snapshot()
    print(snapshot.context_type)   # "gaming" | "work" | "social" | "idle"
    print(snapshot.suggested_mood) # "stay_quiet" | "comment" | "offer_help"
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from caine.config import CaineConfig

logger = logging.getLogger("caine.perception")


# ---------------------------------------------------------------------------
# Tipos de contexto y humor sugerido
# ---------------------------------------------------------------------------

class ContextType(StrEnum):
    GAMING     = "gaming"
    WORK       = "work"        # IDE, terminal, documentos
    SOCIAL     = "social"      # Discord, WhatsApp, redes
    MEDIA      = "media"       # YouTube, Spotify, video
    BROWSING   = "browsing"    # Navegador genérico
    CREATIVE   = "creative"    # Figma, Photoshop, DAW
    IDLE       = "idle"        # Sin actividad del usuario
    UNKNOWN    = "unknown"


class UserEnergy(StrEnum):
    FOCUSED     = "focused"    # Lleva tiempo en la misma app
    ACTIVE      = "active"     # Cambiando entre apps
    DISTRACTED  = "distracted" # Muchos cambios rápidos
    IDLE        = "idle"       # Sin input > N segundos


class SuggestedMood(StrEnum):
    STAY_QUIET   = "stay_quiet"   # No interrumpir
    AMBIENT      = "ambient"      # Comentario muy breve ok
    COMMENT      = "comment"      # Contexto justifica un comentario
    OFFER_HELP   = "offer_help"   # Contexto invita a ofrecer ayuda
    PROACTIVE    = "proactive"    # CAINE puede tomar iniciativa


# ---------------------------------------------------------------------------
# Snapshot unificado del estado del mundo
# ---------------------------------------------------------------------------

@dataclass
class PerceptionSnapshot:
    """Vista completa del estado del entorno en un instante."""

    # Aplicación y ventana
    active_app: str = ""
    window_title: str = ""
    process_name: str = ""

    # Clasificación de alto nivel
    context_type: ContextType = ContextType.UNKNOWN
    user_energy: UserEnergy = UserEnergy.ACTIVE
    suggested_mood: SuggestedMood = SuggestedMood.STAY_QUIET

    # Datos de actividad
    focus_duration_seconds: float = 0.0
    idle_seconds: float = 0.0
    running_app_count: int = 0
    recent_app_switches: int = 0   # En los últimos 5 minutos

    # Contenido visible
    screen_text: str = ""          # OCR reciente (puede estar vacío)
    has_meaningful_text: bool = False

    # Señales de cambio
    ui_changed: bool = False
    change_score: float = 0.0
    new_window: bool = False

    # Metadatos
    timestamp: float = field(default_factory=time.monotonic)
    source_apps: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen compacto para incluir en prompts del brain."""
        parts = [
            f"app={self.active_app or 'escritorio'}",
            f"contexto={self.context_type}",
            f"energia={self.user_energy}",
            f"foco={self.focus_duration_seconds:.0f}s",
        ]
        if self.idle_seconds > 30:
            parts.append(f"inactivo={self.idle_seconds:.0f}s")
        if self.has_meaningful_text:
            parts.append(f"texto='{self.screen_text[:80]}'")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Clasificadores estáticos
# ---------------------------------------------------------------------------

_GAMING_KEYWORDS = {
    "minecraft", "roblox", "steam", "epicgames", "battlenet", "genshin",
    "valorant", "fortnite", "leagueoflegends", "javaw", "csgo", "dota",
    "origin", "ubisoft", "bethesda", "rpg", "fps", "mmorpg", "vrchat",
}

_WORK_KEYWORDS = {
    "code", "vscode", "pycharm", "intellij", "sublime", "notepad++",
    "terminal", "powershell", "cmd", "git", "python", "node", "docker",
    "excel", "word", "powerpoint", "notion", "obsidian", "onenote",
    "postman", "insomnia", "figma",
}

_SOCIAL_KEYWORDS = {
    "discord", "whatsapp", "telegram", "slack", "teams", "zoom",
    "skype", "instagram", "twitter", "tiktok", "facebook", "reddit",
    "messenger",
}

_MEDIA_KEYWORDS = {
    "spotify", "youtube", "netflix", "twitch", "vlc", "winamp",
    "plex", "jellyfin", "crunchyroll", "prime", "disneyplus",
    "musicbee", "foobar",
}

_CREATIVE_KEYWORDS = {
    "photoshop", "illustrator", "premiere", "aftereffects", "davinci",
    "audacity", "reaper", "ableton", "fl studio", "blender", "unity",
    "unreal", "krita", "gimp", "inkscape",
}


def classify_context(app: str, title: str) -> ContextType:
    """Clasifica el contexto a partir del nombre de la app y título de ventana."""
    combined = f"{app} {title}".lower()

    if any(k in combined for k in _GAMING_KEYWORDS):
        return ContextType.GAMING
    if any(k in combined for k in _CREATIVE_KEYWORDS):
        return ContextType.CREATIVE
    if any(k in combined for k in _WORK_KEYWORDS):
        return ContextType.WORK
    if any(k in combined for k in _SOCIAL_KEYWORDS):
        return ContextType.SOCIAL
    if any(k in combined for k in _MEDIA_KEYWORDS):
        return ContextType.MEDIA
    if any(k in combined for k in ("chrome", "firefox", "brave", "edge", "opera", "browser")):
        return ContextType.BROWSING
    return ContextType.UNKNOWN


def compute_suggested_mood(
    context: ContextType,
    energy: UserEnergy,
    focus_duration: float,
    idle_seconds: float,
    recent_switches: int,
) -> SuggestedMood:
    """Calcula el humor sugerido de CAINE según el estado del usuario."""

    # Usuario inactivo → CAINE puede considerar intervención
    if energy == UserEnergy.IDLE or idle_seconds > 300:
        return SuggestedMood.PROACTIVE

    # Gaming: solo comentario ambiental muy de vez en cuando
    if context == ContextType.GAMING:
        if focus_duration > 600:
            return SuggestedMood.AMBIENT
        return SuggestedMood.STAY_QUIET

    # Trabajo concentrado: no interrumpir
    if context == ContextType.WORK and energy == UserEnergy.FOCUSED:
        return SuggestedMood.STAY_QUIET

    # Social activo: podría ofrecer ayuda puntual
    if context == ContextType.SOCIAL and energy == UserEnergy.ACTIVE:
        return SuggestedMood.AMBIENT

    # Mucho foco sostenido en cualquier app → check-in
    if focus_duration > 1800 and energy == UserEnergy.FOCUSED:
        return SuggestedMood.OFFER_HELP

    # Mucho cambio de apps = distraído → silencio
    if recent_switches > 6:
        return SuggestedMood.STAY_QUIET

    # Media: presencia muy ligera
    if context == ContextType.MEDIA:
        return SuggestedMood.AMBIENT

    return SuggestedMood.COMMENT


# ---------------------------------------------------------------------------
# PerceptionLayer principal
# ---------------------------------------------------------------------------

class PerceptionLayer:
    """API unificada de percepción. Consolida todas las señales del entorno.

    Esta capa es el único punto de contacto entre el mundo físico del
    escritorio y los módulos de inteligencia de CAINE.
    """

    def __init__(self, config: "CaineConfig") -> None:
        self.config = config
        self._logger = logging.getLogger("caine.perception")
        self._last_snapshot: PerceptionSnapshot | None = None
        self._app_switch_times: list[float] = []  # timestamps de cambios de app
        self._last_app: str = ""

        # Lazy imports de módulos pesados
        self._context_engine = None
        self._screen_watcher = None

    def _get_context_engine(self):
        if self._context_engine is None:
            from world.context_engine import ContextEngine
            self._context_engine = ContextEngine(self.config)
        return self._context_engine

    def get_snapshot(self) -> PerceptionSnapshot:
        """Produce un PerceptionSnapshot sincrónico con el estado actual."""
        try:
            engine = self._get_context_engine()
            world_state, _ = engine.sample()
        except Exception as exc:
            self._logger.debug("ContextEngine falló: %s", exc)
            return self._snapshot_from_defaults()

        # Registrar cambio de app para calcular switches recientes
        active = world_state.active_app or ""
        if active and active != self._last_app:
            self._app_switch_times.append(time.monotonic())
            self._last_app = active

        # Purgar switches > 5 minutos
        now = time.monotonic()
        self._app_switch_times = [t for t in self._app_switch_times if now - t <= 300]
        recent_switches = len(self._app_switch_times)

        # Clasificar
        context_type = classify_context(world_state.active_app, world_state.window_title)
        idle_seconds = self._estimate_idle(world_state)
        user_energy = self._compute_energy(
            world_state.focus_duration, idle_seconds, recent_switches
        )
        mood = compute_suggested_mood(
            context_type, user_energy, world_state.focus_duration,
            idle_seconds, recent_switches
        )

        screen_text = (world_state.ocr_text or "").strip()
        has_meaningful_text = bool(screen_text) and len(screen_text) > 15

        snapshot = PerceptionSnapshot(
            active_app=world_state.active_app,
            window_title=world_state.window_title,
            process_name=world_state.active_app,
            context_type=context_type,
            user_energy=user_energy,
            suggested_mood=mood,
            focus_duration_seconds=world_state.focus_duration,
            idle_seconds=idle_seconds,
            running_app_count=len(world_state.running_apps),
            recent_app_switches=recent_switches,
            screen_text=screen_text[:400] if screen_text else "",
            has_meaningful_text=has_meaningful_text,
            ui_changed=world_state.changed,
            change_score=0.0,
            new_window=world_state.changed,
            source_apps=world_state.running_apps[:20],
        )
        self._last_snapshot = snapshot
        return snapshot

    async def get_snapshot_async(self) -> PerceptionSnapshot:
        """Versión async (no bloquea el event loop)."""
        return await asyncio.to_thread(self.get_snapshot)

    @property
    def last_snapshot(self) -> PerceptionSnapshot | None:
        return self._last_snapshot

    def _compute_energy(
        self, focus_duration: float, idle_seconds: float, recent_switches: int
    ) -> UserEnergy:
        if idle_seconds > 120:
            return UserEnergy.IDLE
        if recent_switches > 8:
            return UserEnergy.DISTRACTED
        if focus_duration > 600:
            return UserEnergy.FOCUSED
        return UserEnergy.ACTIVE

    def _estimate_idle(self, world_state) -> float:
        """Estima segundos de inactividad desde el world_state."""
        if world_state.user_activity == "idle":
            return float(getattr(self.config.world, "inactivity_seconds", 120))
        return 0.0

    def _snapshot_from_defaults(self) -> PerceptionSnapshot:
        """Snapshot mínimo cuando el ContextEngine falla."""
        return PerceptionSnapshot(
            context_type=ContextType.UNKNOWN,
            user_energy=UserEnergy.ACTIVE,
            suggested_mood=SuggestedMood.STAY_QUIET,
        )
