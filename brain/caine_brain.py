"""Integracion principal con OpenJarvis (agentes) + fallback a API OpenAI-compatible."""

from __future__ import annotations

from typing import Any
import logging

import requests

from memory.conversation_memory import ConversationMemory
from personality.loader import PersonalityLoader


class CaineBrain:
    """
    Capa de decision de CAINE.

    Intenta usar OpenJarvis (agentes avanzados + skills) como capa primaria.
    Si OpenJarvis no esta disponible, hace fallback a la API OpenAI-compatible
    directa (Google Gemini, OpenRouter, etc.).
    """

    def __init__(
        self,
        base_url: str,
        primary_model: str,
        fallback_model: str,
        api_key: str,
        timeout_seconds: int,
        personality_loader: PersonalityLoader,
        conversation_memory: ConversationMemory,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.personality_loader = personality_loader
        self.conversation_memory = conversation_memory
        self.logger = logging.getLogger("caine.brain")
        self._openjarvis_ready = False
        self._init_openjarvis()

    def _init_openjarvis(self) -> None:
        """Try to initialize OpenJarvis. Degrades gracefully if unavailable."""
        try:
            from interaction.openjarvis_skills import init_openjarvis
            personality_path = str(self.personality_loader.personality_file)
            ok = init_openjarvis(
                api_key=self.api_key,
                personality_path=personality_path,
                model="gemini-2.5-flash",
                tools=["web_search", "think"],
            )
            self._openjarvis_ready = ok
            if ok:
                self.logger.info("OpenJarvis inicializado. CAINE usara agentes avanzados.")
            else:
                self.logger.info("OpenJarvis no disponible. Usando API directa.")
        except Exception as exc:
            self.logger.warning("OpenJarvis no pudo inicializarse: %s", exc)
            self._openjarvis_ready = False

    def send_message(self, user_message: str, extra_context: str = "") -> str:
        # Intentar OpenJarvis primero
        if self._openjarvis_ready:
            response = self._ask_openjarvis(user_message)
            if response:
                self.conversation_memory.add(role="user", content=user_message)
                self.conversation_memory.add(role="assistant", content=response)
                return response
            self.logger.warning("OpenJarvis no respondio. Usando fallback API directo.")

        # Fallback: API OpenAI-compatible directa
        messages = self._build_messages(user_message, extra_context=extra_context)
        assistant_message = self._chat_with_fallback(messages)
        self.conversation_memory.add(role="user", content=user_message)
        self.conversation_memory.add(role="assistant", content=assistant_message)
        return assistant_message

    def _ask_openjarvis(self, user_message: str) -> str | None:
        """Delegate to OpenJarvis and return CAINE-flavored response."""
        try:
            from interaction.openjarvis_skills import ask_jarvis
            history = self.conversation_memory.get_messages()
            raw = ask_jarvis(user_message, context_messages=history)
            if raw and raw.strip():
                return self._cleanup_message(raw)
        except Exception as exc:
            self.logger.warning("Error en OpenJarvis ask: %s", exc)
        return None

    def connection_test(self) -> tuple[bool, str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            models_response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=self.timeout_seconds,
            )
            models_response.raise_for_status()
            
            data = models_response.json()
            models = {
                model_info.get("id", "")
                for model_info in data.get("data", [])
            }
            
            if self.primary_model in models:
                return True, f"Gateway activo. Modelo principal disponible: {self.primary_model}"

            if self.fallback_model in models:
                return True, f"Gateway activo. Falta el principal, pero existe el fallback: {self.fallback_model}"

            return True, "Gateway activo. (No pude validar los nombres de modelos exactos, asumiendo OK)"
            
        except requests.RequestException as error:
            return False, f"No se pudo conectar con el gateway (OpenClaw/OpenAI): {error}"
        except Exception as error:
            # Si responde HTML (como OpenClaw a veces) no crasheamos
            return True, "Gateway responde, pero no expone formato JSON estandar. Asumiendo OK."

    def _chat_with_fallback(self, messages: list[dict[str, Any]]) -> str:
        for model_name in (self.primary_model, self.fallback_model):
            ok, content = self._chat(model_name=model_name, messages=messages)
            if ok:
                return content

            self.logger.warning("Fallo al usar el modelo %s: %s", model_name, content)

        return (
            "El gran circo se ha quedado sin voz: no pude obtener respuesta ni "
            f"de '{self.primary_model}' ni de '{self.fallback_model}'."
        )

    def _chat(self, model_name: str, messages: list[dict[str, Any]]) -> tuple[bool, str]:
        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "stop": ["Lin:", "User:", "Usuario:", "\nLin:"]
            }
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
                
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            return False, str(error)

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return False, f"La API respondio sin choices. Response: {data}"
        
        assistant_message = choices[0].get("message", {}).get("content", "")
        if assistant_message is None:
            assistant_message = ""
        assistant_message = assistant_message.strip()
        
        if not assistant_message:
            return False, f"La API respondio sin contenido. Response: {data}"

        assistant_message = self._cleanup_message(assistant_message)
        return True, assistant_message

    def _build_messages(self, user_message: str, extra_context: str = "") -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.personality_loader.load_text()},
            {
                "role": "system",
                "content": (
                    "Reglas operativas de estilo ABSOLUTAS:\n"
                    "- Responde SIEMPRE como CAINE.\n"
                    "- REGLA CRITICA: NUNCA asumas el rol del usuario (Lin). NUNCA generes respuestas del tipo 'Lin: ...'.\n"
                    "- REGLA CRITICA: NUNCA simules un dialogo entre dos personas. Solo genera TU propia respuesta (CAINE) y espera input.\n"
                    "- No suenes como asistente generico.\n"
                    "- Si la peticion del usuario es concreta, responde primero a eso.\n"
                    "- Mantente breve salvo que el usuario pida mas detalle.\n"
                    "- Usa teatralidad, carisma y rareza, pero no relleno.\n"
                    "- Si algo no se puede hacer, dilo con estilo de anfitrion, no con tono plano.\n"
                    "- Evita saludos genericos y frases vacias.\n"
                    "- No uses tono motivacional ni de coach.\n"
                    "- Si presentas tu identidad, hazlo en una sola frase memorable.\n"
                    "- Si acompanias al usuario mientras juega, suena presente pero no pesado."
                ),
            },
        ]
        if extra_context.strip():
            messages.append(
                {
                    "role": "system",
                    "content": f"Contexto local adicional del sistema:\n{extra_context.strip()}",
                }
            )

        messages.extend(self.conversation_memory.get_messages())
        messages.append({"role": "user", "content": user_message})
        return messages

    def _cleanup_message(self, text: str) -> str:
        cleaned = text.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1].strip()
        replacements = {
            "Â¡": "¡",
            "Â¿": "¿",
            "Ã¡": "á",
            "Ã©": "é",
            "Ã­": "í",
            "Ã³": "ó",
            "Ãº": "ú",
            "Ã±": "ñ",
            "â€™": "'",
            "â€œ": '"',
            "â€": '"',
            "â€¦": "...",
            "acompa?ame": "acompañame",
            "‧x": "¡Ex",
        }
        for broken, fixed in replacements.items():
            cleaned = cleaned.replace(broken, fixed)
        return cleaned
