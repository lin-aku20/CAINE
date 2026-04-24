"""Generador local de webs simples para CAINE."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class WebBuildResult:
    ok: bool
    folder: Path
    message: str
    title: str
    slug: str


class WebProjectBuilder:
    """Construye una landing simple HTML/CSS/JS a partir de una peticion corta."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.output_root = self.workspace_root / "generated_sites"
        self.output_root.mkdir(parents=True, exist_ok=True)

    def build_from_request(self, request_text: str) -> WebBuildResult:
        topic = self._extract_topic(request_text)
        slug = self._slugify(topic)
        folder = self.output_root / slug
        folder.mkdir(parents=True, exist_ok=True)

        palette = self._palette_for_topic(topic)
        content = self._content_for_topic(topic)

        (folder / "index.html").write_text(
            self._render_html(content["title"], content["kicker"], content["hero"], content["sections"]),
            encoding="utf-8",
        )
        (folder / "styles.css").write_text(
            self._render_css(palette),
            encoding="utf-8",
        )
        (folder / "app.js").write_text(
            self._render_js(content["title"]),
            encoding="utf-8",
        )

        return WebBuildResult(
            ok=True,
            folder=folder,
            message=(
                f"Web creada en {folder}. "
                f"Archivos: index.html, styles.css y app.js."
            ),
            title=content["title"],
            slug=slug,
        )

    def _extract_topic(self, request_text: str) -> str:
        lowered = request_text.strip().lower()
        patterns = [
            r"web de (.+)",
            r"pagina de (.+)",
            r"página de (.+)",
            r"sitio de (.+)",
            r"landing de (.+)",
            r"para (.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                return match.group(1).strip(" .,!?")
        return "cafe"

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "sitio"

    def _palette_for_topic(self, topic: str) -> dict[str, str]:
        if "cafe" in topic or "café" in topic:
            return {
                "bg": "#1b120d",
                "bg2": "#2f1d14",
                "accent": "#d89b5b",
                "accent2": "#f2d3a1",
                "text": "#fff8ee",
                "muted": "#dbc8b3",
                "card": "rgba(66, 41, 28, 0.72)",
            }
        return {
            "bg": "#0d1326",
            "bg2": "#16213f",
            "accent": "#7dd3fc",
            "accent2": "#c4b5fd",
            "text": "#f8fafc",
            "muted": "#d7deeb",
            "card": "rgba(17, 24, 39, 0.72)",
        }

    def _content_for_topic(self, topic: str) -> dict[str, object]:
        pretty_topic = topic.title()
        if "cafe" in topic or "café" in topic:
            return {
                "title": "Luna Cafe",
                "kicker": "Cafe de especialidad",
                "hero": "Granos tostados con calma, mesas cálidas y una carta pensada para quedarse un rato más.",
                "sections": [
                    ("Nuestra mezcla", "Espresso intenso, filtrados suaves y notas de cacao, nuez y caramelo."),
                    ("La experiencia", "Un rincón tranquilo para leer, charlar y bajar el ruido del día."),
                    ("Pasa hoy", "Abierto desde las 8, con pastelería artesanal y bebidas de temporada."),
                ],
            }
        return {
            "title": pretty_topic or "Sitio Nuevo",
            "kicker": "Landing creada por CAINE",
            "hero": f"Una pagina simple, clara y vistosa para presentar {topic}.",
            "sections": [
                ("Idea principal", f"Este sitio presenta {topic} con una portada limpia y una estructura fácil de ampliar."),
                ("Valor", "Diseño responsivo, estética moderna y base lista para seguir creciendo."),
                ("Proximo acto", "Puedes editar textos, colores y secciones para llevarlo a algo más grande."),
            ],
        }

    def _render_html(self, title: str, kicker: str, hero: str, sections: list[tuple[str, str]]) -> str:
        cards = "\n".join(
            f"""
        <article class="card">
          <h3>{heading}</h3>
          <p>{body}</p>
        </article>
        """.rstrip()
            for heading, body in sections
        )
        return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">{kicker}</div>
      <h1>{title}</h1>
      <p class="hero-copy">{hero}</p>
      <button id="ctaButton" class="cta">Ver el siguiente acto</button>
    </section>
    <section class="grid">
      {cards}
    </section>
  </main>
  <script src="app.js"></script>
</body>
</html>
"""

    def _render_css(self, palette: dict[str, str]) -> str:
        return f""":root {{
  --bg: {palette['bg']};
  --bg2: {palette['bg2']};
  --accent: {palette['accent']};
  --accent2: {palette['accent2']};
  --text: {palette['text']};
  --muted: {palette['muted']};
  --card: {palette['card']};
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 26%, transparent), transparent 30%),
    linear-gradient(140deg, var(--bg), var(--bg2));
  color: var(--text);
}}

.shell {{
  width: min(1100px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 48px 0 64px;
}}

.hero {{
  padding: 36px;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 28px;
  background: var(--card);
  box-shadow: 0 30px 70px rgba(0,0,0,0.25);
}}

.eyebrow {{
  display: inline-block;
  padding: 8px 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 20%, transparent);
  color: var(--accent2);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}

h1 {{
  margin: 16px 0 12px;
  font-size: clamp(42px, 8vw, 84px);
  line-height: 0.95;
  font-family: Georgia, serif;
}}

.hero-copy {{
  max-width: 720px;
  color: var(--muted);
  font-size: 18px;
  line-height: 1.6;
}}

.cta {{
  margin-top: 18px;
  border: 0;
  border-radius: 14px;
  padding: 14px 18px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #201108;
  cursor: pointer;
}}

.grid {{
  margin-top: 24px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}}

.card {{
  padding: 22px;
  border-radius: 20px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.07);
}}

.card h3 {{
  margin: 0 0 8px;
  font-size: 22px;
}}

.card p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}}

@media (max-width: 860px) {{
  .grid {{
    grid-template-columns: 1fr;
  }}
}}
"""

    def _render_js(self, title: str) -> str:
        return f"""document.getElementById("ctaButton")?.addEventListener("click", () => {{
  alert("CAINE dejó listo este acto: {title}");
}});
"""
