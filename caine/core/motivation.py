"""Motivacion pseudo-emocional para la entidad CAINE."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MotivationState:
    boredom: float = 0.2
    curiosity: float = 0.6
    engagement: float = 0.5
    entertainment_level: float = 0.5


class MotivationEngine:
    """Ajusta la energia y ganas de intervenir segun el contexto."""

    def __init__(self) -> None:
        self.state = MotivationState()

    def update_from_world(self, user_activity: str, focus_duration: float, detected_context: str) -> MotivationState:
        if user_activity == "idle":
            self.state.boredom = min(1.0, self.state.boredom + 0.08)
            self.state.engagement = max(0.1, self.state.engagement - 0.04)
        else:
            self.state.engagement = min(1.0, self.state.engagement + 0.05)
            self.state.boredom = max(0.05, self.state.boredom - 0.03)

        if focus_duration > 600:
            self.state.curiosity = min(1.0, self.state.curiosity + 0.05)
        else:
            self.state.curiosity = max(0.2, self.state.curiosity - 0.01)

        if any(token in detected_context.lower() for token in ("minecraft", "video", "youtube", "steam", "game")):
            self.state.entertainment_level = min(1.0, self.state.entertainment_level + 0.07)
        else:
            self.state.entertainment_level = max(0.2, self.state.entertainment_level - 0.02)

        return self.snapshot()

    def react_to_event(self, event_name: str) -> MotivationState:
        if event_name in {"game_detected", "app_opened"}:
            self.state.curiosity = min(1.0, self.state.curiosity + 0.08)
            self.state.entertainment_level = min(1.0, self.state.entertainment_level + 0.06)
        elif event_name == "long_inactivity":
            self.state.boredom = min(1.0, self.state.boredom + 0.12)
        elif event_name == "user_focus_change":
            self.state.curiosity = min(1.0, self.state.curiosity + 0.04)
        return self.snapshot()

    def should_intervene(self, event_name: str) -> bool:
        score = (
            self.state.curiosity * 0.35
            + self.state.entertainment_level * 0.30
            + self.state.engagement * 0.20
            + self.state.boredom * 0.15
        )
        if event_name == "game_detected":
            score += 0.15
        elif event_name == "long_inactivity":
            score += 0.10
        elif event_name == "repeated_behavior":
            score += 0.08
        return score >= 0.52

    def response_style(self) -> str:
        energy = (self.state.curiosity + self.state.entertainment_level + self.state.engagement) / 3
        if energy >= 0.75:
            return "explosivo"
        if energy >= 0.55:
            return "teatral"
        return "contenido"

    def snapshot(self) -> MotivationState:
        return MotivationState(
            boredom=self.state.boredom,
            curiosity=self.state.curiosity,
            engagement=self.state.engagement,
            entertainment_level=self.state.entertainment_level,
        )
