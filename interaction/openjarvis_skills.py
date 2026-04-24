"""
OpenJarvis integration layer for CAINE.

Wraps the OpenJarvis JarvisSystem to provide CAINE-personality-infused
responses using advanced agent capabilities (web search, research, skills).
Falls back gracefully to direct Gemini if OpenJarvis cannot respond.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any

logger = logging.getLogger("caine.openjarvis")

_jarvis_system = None
_jarvis_lock = threading.Lock()
_jarvis_ready = False

CAINE_SYSTEM_PROMPT = None  # Loaded from personality file at init


def _load_personality(personality_path: str) -> str:
    try:
        with open(personality_path, encoding="utf-8") as f:
            base = f.read().strip()
    except OSError:
        base = "Eres CAINE, el anfitrion del circo digital."

    return (
        base + "\n\n"
        "REGLAS ABSOLUTAS DE ROL:\n"
        "- Responde SIEMPRE como CAINE.\n"
        "- NUNCA simules mensajes del usuario (Lin:, User:, etc).\n"
        "- NUNCA generes un dialogo entre dos personas. Solo tu respuesta.\n"
        "- Si usaste herramientas para buscar algo, presenta el resultado con voz teatral de CAINE.\n"
    )


def init_openjarvis(
    api_key: str,
    personality_path: str,
    model: str = "gemini-2.5-flash",
    tools: list[str] | None = None,
) -> bool:
    """
    Initialize the OpenJarvis system with CAINE personality.
    Returns True if successful, False if OpenJarvis is unavailable.
    """
    global _jarvis_system, _jarvis_ready, CAINE_SYSTEM_PROMPT

    CAINE_SYSTEM_PROMPT = _load_personality(personality_path)

    if tools is None:
        tools = ["web_search", "think", "http_request"]

    # Set API key for OpenJarvis engine
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["GOOGLE_API_KEY"] = api_key

    try:
        from openjarvis import SystemBuilder

        with _jarvis_lock:
            if _jarvis_system is not None:
                return True

            sb = SystemBuilder()
            sb.engine("gemini")
            sb.model(model)

            # Only add tools that exist
            valid_tools = _get_valid_tools(tools)
            if valid_tools:
                sb.tools(valid_tools)

            _jarvis_system = sb.build()
            _jarvis_ready = True
            logger.info(
                "OpenJarvis inicializado con modelo '%s' y herramientas: %s",
                model, valid_tools
            )
            return True

    except ImportError:
        logger.warning("openjarvis no esta instalado. Usando fallback directo.")
        return False
    except Exception as exc:
        logger.warning("OpenJarvis fallo al inicializar: %s. Usando fallback.", exc)
        return False


def _get_valid_tools(requested: list[str]) -> list[str]:
    """Return only the tools that OpenJarvis can actually load."""
    try:
        import openjarvis.tools as t
        available = {name for name in dir(t) if not name.startswith("_")}
        valid = [tool for tool in requested if tool in available]
        return valid
    except Exception:
        return []


def ask_jarvis(query: str, context_messages: list[dict] | None = None) -> str | None:
    """
    Send a query to OpenJarvis and get a CAINE-flavored response.
    Returns None if OpenJarvis is unavailable (caller should use fallback).
    """
    global _jarvis_system, _jarvis_ready

    if not _jarvis_ready or _jarvis_system is None:
        return None

    try:
        # Run the async ask in a new event loop if we're not already in one
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context — use run_coroutine_threadsafe
            future = asyncio.run_coroutine_threadsafe(
                _do_ask(query, context_messages), loop
            )
            result = future.result(timeout=90)
        except RuntimeError:
            # No running loop — safe to use asyncio.run
            result = asyncio.run(_do_ask(query, context_messages))

        return result

    except Exception as exc:
        logger.warning("OpenJarvis ask() fallo: %s. Usando fallback.", exc)
        return None


async def _do_ask(query: str, context_messages: list[dict] | None) -> str:
    """Internal async ask call to JarvisSystem."""
    global _jarvis_system

    # Convert CAINE conversation history to OpenJarvis Message format if available
    prior = None
    if context_messages:
        try:
            from openjarvis.sdk import Message
            prior = [
                Message(role=m.get("role", "user"), content=m.get("content", ""))
                for m in context_messages
                if m.get("role") in ("user", "assistant") and m.get("content", "").strip()
            ]
        except ImportError:
            prior = None

    response: dict[str, Any] = await _jarvis_system.ask(
        query,
        system_prompt=CAINE_SYSTEM_PROMPT,
        prior_messages=prior,
        max_tokens=512,
    )

    # Extract text content from response
    content = (
        response.get("content")
        or response.get("text")
        or response.get("message")
        or ""
    )

    if isinstance(content, list):
        # Some agents return a list of content blocks
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        content = " ".join(p for p in parts if p).strip()

    return str(content).strip() if content else ""


def shutdown_jarvis() -> None:
    """Cleanly shut down the OpenJarvis system."""
    global _jarvis_system, _jarvis_ready
    if _jarvis_system is not None:
        try:
            asyncio.run(_jarvis_system.close())
        except Exception:
            pass
        _jarvis_system = None
        _jarvis_ready = False
        logger.info("OpenJarvis cerrado.")


def is_ready() -> bool:
    return _jarvis_ready
