"""GracefulFailureLayer — Capa de fallos naturales para CAINE.

El usuario NUNCA debe ver errores técnicos crudos.
Este módulo convierte excepciones, timeouts y fallos de API
en respuestas naturales con la voz de CAINE.

Uso (decorator):
    @graceful_caine_response
    def my_function(...) -> str: ...

Uso (context manager / inline):
    with GracefulContext("caine.brain") as ctx:
        result = brain.send_message(text)
    if ctx.failed:
        result = ctx.fallback
"""

from __future__ import annotations

import functools
import logging
import random
import time
from contextlib import contextmanager
from typing import Callable, Generator, TypeVar

logger = logging.getLogger("caine.graceful_failure")

T = TypeVar("T")

# Respuestas naturales para diferentes tipos de fallo
_TIMEOUT_RESPONSES = [
    "Perdí el hilo un segundo. ¿Lo repetimos?",
    "Algo crujió en la tramoya. Dame un momento.",
    "El telón tembló. Vuelve a intentarlo.",
    "Eso se fue al vacío. Prueba de nuevo.",
    "El circo tuvo un tropiezo técnico, pero sigo aquí.",
]

_API_ERROR_RESPONSES = [
    "La señal se cortó. No me llega nada del otro lado.",
    "El backstage está en silencio ahora mismo. Intenta en un momento.",
    "Perdí la conexión con mis cables. Un segundo.",
    "El sistema de voz del circo está tomando un descanso forzado.",
]

_GENERAL_ERROR_RESPONSES = [
    "Algo falló detrás del telón, pero mantengo la compostura.",
    "Tropecé, pero sigo de pie. ¿Qué necesitas?",
    "Pequeño colapso interno. Ya lo resolví. ¿Continuamos?",
    "El mecanismo se trabó un momento. Dame otro intento.",
]

_MODEL_EMPTY_RESPONSES = [
    "Me quedé sin palabras, literalmente. Pregunta de otra forma.",
    "El modelo me devolvió silencio. Raro. ¿Lo reformulas?",
    "Nada útil vino del otro lado. Prueba con otra pregunta.",
]


def _pick(pool: list[str]) -> str:
    return random.choice(pool)


def graceful_caine_response(func: Callable[..., str]) -> Callable[..., str]:
    """Decorator: envuelve funciones que retornan str y captura cualquier excepción."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> str:
        try:
            result = func(*args, **kwargs)
            if not result or not result.strip():
                logger.warning("graceful: función '%s' retornó vacío.", func.__name__)
                return _pick(_MODEL_EMPTY_RESPONSES)
            return result
        except TimeoutError:
            logger.error("graceful: timeout en '%s'.", func.__name__)
            return _pick(_TIMEOUT_RESPONSES)
        except Exception as exc:
            exc_name = type(exc).__name__
            # Clasificar por tipo de error
            exc_lower = str(exc).lower()
            if any(k in exc_lower for k in ("timeout", "timed out", "read timeout")):
                logger.error("graceful: timeout detectado en '%s': %s", func.__name__, exc)
                return _pick(_TIMEOUT_RESPONSES)
            if any(k in exc_lower for k in ("connection", "network", "api", "401", "403", "502", "503")):
                logger.error("graceful: error de API en '%s': %s", func.__name__, exc)
                return _pick(_API_ERROR_RESPONSES)
            logger.exception("graceful: error inesperado en '%s' (%s): %s", func.__name__, exc_name, exc)
            return _pick(_GENERAL_ERROR_RESPONSES)
    return wrapper


class GracefulContext:
    """Context manager para envolver bloques de código críticos.

    Ejemplo:
        ctx = GracefulContext("brain.send_message")
        with ctx:
            result = risky_call()
        final = ctx.result if not ctx.failed else ctx.fallback
    """

    def __init__(self, label: str = "unknown") -> None:
        self.label = label
        self.failed = False
        self.error: Exception | None = None
        self.result: str = ""
        self.fallback: str = _pick(_GENERAL_ERROR_RESPONSES)

    def __enter__(self) -> "GracefulContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            return False
        self.failed = True
        self.error = exc_val

        exc_lower = str(exc_val).lower() if exc_val else ""
        if any(k in exc_lower for k in ("timeout", "timed out")):
            self.fallback = _pick(_TIMEOUT_RESPONSES)
        elif any(k in exc_lower for k in ("connection", "api", "401", "503")):
            self.fallback = _pick(_API_ERROR_RESPONSES)
        else:
            self.fallback = _pick(_GENERAL_ERROR_RESPONSES)

        logger.error(
            "GracefulContext[%s]: excepción capturada (%s): %s",
            self.label, exc_type.__name__ if exc_type else "?", exc_val
        )
        # Suprimir la excepción (retornar True la silencia)
        return True
