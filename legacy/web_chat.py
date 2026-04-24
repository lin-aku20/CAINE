"""Servidor web local para chatear con CAINE desde PC o celular."""

from __future__ import annotations

import json
import mimetypes
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from caine.app import CaineApp
from caine.config import CaineConfig
from caine.logging_utils import configure_logging


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "webui"
STATIC_DIR = WEB_DIR / "static"


@dataclass(slots=True)
class WebChatContext:
    app: CaineApp
    lock: threading.Lock
    static_dir: Path
    index_file: Path


class CaineWebHandler(BaseHTTPRequestHandler):
    server_version = "CaineWeb/1.0"

    @property
    def context(self) -> WebChatContext:
        return self.server.context  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._serve_file(self.context.index_file)
            return

        if parsed.path == "/api/status":
            self._json_response(
                {
                    "ok": True,
                    "name": "CAINE",
                    "message": "Cabina web lista.",
                    "model": self.context.app.config.ollama.primary_model,
                }
            )
            return

        if parsed.path.startswith("/static/"):
            relative = parsed.path.removeprefix("/static/").strip("/")
            file_path = (self.context.static_dir / relative).resolve()
            if not str(file_path).startswith(str(self.context.static_dir.resolve())):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self._serve_file(file_path)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        payload = self._read_json_body()
        if payload is None:
            return

        message = str(payload.get("message", "")).strip()
        if not message:
            self._json_response({"ok": False, "error": "Mensaje vacio."}, status=HTTPStatus.BAD_REQUEST)
            return

        with self.context.lock:
            reply = self.context.app.runtime.handle_text(message)

        self._json_response({"ok": True, "reply": reply})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self._json_response({"ok": False, "error": "Body vacio."}, status=HTTPStatus.BAD_REQUEST)
            return None

        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response({"ok": False, "error": "JSON invalido."}, status=HTTPStatus.BAD_REQUEST)
            return None

    def _json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type, _ = mimetypes.guess_type(path.name)
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def build_app() -> CaineApp:
    config = CaineConfig.from_yaml()
    configure_logging(config.logging.log_file, config.logging.level)
    return CaineApp(config=config)


def run_server(host: str = "0.0.0.0", port: int = 8765) -> None:
    app = build_app()
    context = WebChatContext(
        app=app,
        lock=threading.Lock(),
        static_dir=STATIC_DIR,
        index_file=WEB_DIR / "index.html",
    )
    server = ThreadingHTTPServer((host, port), CaineWebHandler)
    server.context = context  # type: ignore[attr-defined]
    print(f"CAINE web activo en http://127.0.0.1:{port}")
    print(f"CAINE web activo en http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
