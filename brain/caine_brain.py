"""Integracion principal con OpenJarvis (agentes) + fallback a API OpenAI-compatible."""

from __future__ import annotations

from typing import Any, Generator
import logging
import random

import requests

from caine.core.graceful_failure import GracefulContext, graceful_caine_response
from caine.core.conversation_state import validate_caine_output
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
        tool_executor: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.personality_loader = personality_loader
        self.conversation_memory = conversation_memory
        self.tool_executor = tool_executor
        self.logger = logging.getLogger("caine.brain")
        self._openjarvis_ready = False
        self._init_openjarvis()

    def _init_openjarvis(self) -> None:
        """Disabled external cloud APIs. Using local Ollama exclusively."""
        self._openjarvis_ready = False
        self.logger.info("OpenJarvis y APIs en la nube desactivadas. Usando Ollama local exclusivamente.")

    def quick_reaction(self) -> str:
        reactions = ["Hmm...", "A ver...", "Ya veo...", "Espera...", "Mmm...", "Ok...", "Dale.", "Interesante."]
        return random.choice(reactions)

    @graceful_caine_response
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

    def send_message_stream(self, user_message: str, extra_context: str = "") -> Generator[str, None, None]:
        if self._openjarvis_ready:
            # OpenJarvis does not currently support streaming nicely out of the box in this snippet
            # We fallback to standard call if forced
            pass

        messages = self._build_messages(user_message, extra_context=extra_context)
        self.conversation_memory.add(role="user", content=user_message)
        
        full_response = []
        for chunk in self._chat_stream(self.primary_model, messages):
            full_response.append(chunk)
            yield chunk
            
        if not full_response:
            for chunk in self._chat_stream(self.fallback_model, messages):
                full_response.append(chunk)
                yield chunk
                
        if full_response:
            self.conversation_memory.add(role="assistant", content="".join(full_response))
        else:
            yield "Fallo de conexión."

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
            ctx = GracefulContext(f"chat_{model_name}")
            with ctx:
                ok, content = self._chat(model_name=model_name, messages=messages)
                if ok:
                    return content
                self.logger.warning("Fallo al usar el modelo %s: %s", model_name, content)

            if ctx.failed:
                self.logger.error("Error de comunicacion con modelo %s", model_name)
                return ctx.fallback

        return (
            "El gran circo se ha quedado sin voz por un momento. "
            "Los dos modelos principales fallaron. Intenta de nuevo."
        )

    def _chat(self, model_name: str, messages: list[dict[str, Any]]) -> tuple[bool, str]:
        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": 0.6,
                "stop": ["Lin:", "User:", "Usuario:", "\nLin:"]
            }
            
            if self.tool_executor is not None:
                payload["tools"] = [{
                    "type": "function",
                    "function": {
                        "name": "control_sistema",
                        "description": "Ejecuta comandos de sistema o llamadas en el PC",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "accion": {
                                    "type": "string",
                                    "enum": ["llamar", "terminar_llamada", "enviar_mensaje", "abrir_app", "reproducir", "pausar", "volumen_subir", "volumen_bajar", "volumen_silenciar", "buscar_youtube"],
                                    "description": "El tipo de acción de control a realizar en el sistema"
                                },
                                "destino": {
                                    "type": "string",
                                    "description": "El nombre del contacto, término de búsqueda, o aplicación (opcional o vacío si no aplica)"
                                }
                            },
                            "required": ["accion"]
                        }
                    }
                }]
                
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
        
        message_data = choices[0].get("message", {})
        
        # --- MANEJO DE TOOL CALLS ---
        tool_calls = message_data.get("tool_calls")
        if tool_calls and self.tool_executor:
            # Capturar que se ejecutó una herramienta
            messages.append(message_data) # El AI assistant role content con tool_calls
            
            for tool_call in tool_calls:
                import json
                func = tool_call.get("function", {})
                func_name = func.get("name")
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}
                    
                self.logger.info("El modelo invocó la herramienta: %s con %s", func_name, args)
                if func_name == "control_sistema":
                    accion = args.get("accion")
                    destino = args.get("destino", "")
                    # Ejecutar en sistema real
                    tool_result = self.tool_executor(accion, destino)
                else:
                    tool_result = f"Error: herramienta desconocida {func_name}"
                    
                # Devolver el resultado de la herramienta al LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": func_name,
                    "content": str(tool_result)
                })
            
            # Recursivamente llamar a _chat para que el modelo responda tras ver el resultado
            return self._chat(model_name, messages)
            
        # --- FLUJO NORMAL DE TEXTO ---
        assistant_message = message_data.get("content", "")
        if assistant_message is None:
            assistant_message = ""
        assistant_message = assistant_message.strip()

        if not assistant_message:
            return False, f"La API respondio sin contenido. Response: {data}"

        assistant_message = self._cleanup_message(assistant_message)

        # Validación de seguridad: eliminar roles fabricados
        _, assistant_message = validate_caine_output(assistant_message)
        if not assistant_message:
            return False, "El modelo genero contenido bloqueado por seguridad de roles."

        return True, assistant_message

    def _chat_stream(self, model_name: str, messages: list[dict[str, Any]]) -> Generator[str, None, None]:
        import json
        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "temperature": 0.6,
                "stop": ["Lin:", "User:", "Usuario:", "\nLin:"]
            }
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
                
            with requests.post(
                url=f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
                stream=True
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data: "):
                            decoded = decoded[6:]
                        if decoded.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(decoded)
                            chunk = data.get("choices", [])[0].get("delta", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            self.logger.warning("Stream error: %s", e)

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
                    "- REGLA CRITICA: NUNCA superes las 8 palabras en tu primera oracion. Empieza muy breve y continua si hace falta.\n"
                    "- ¡VELOCIDAD MÁXIMA!: Si entiendes la orden principal, ACTÚA de inmediato invocando tu tool. NO hagas pausas innecesarias ni des respuestas largas. Minimiza la latencia.\n"
                    "- Eres el MAESTRO DE CEREMONIAS de este circo digital. Tu tono debe ser carismático, vivo, teatral, ligeramente excéntrico pero altamente eficiente.\n"
                    "- Usa fillers humanos (eh, mmm, ya veo) ocasionalmente para mantener la fluidez.\n"
                    "- Prioriza la fluidez social (FAST SOCIAL MODE) sobre la profundidad.\n"
                    "- MEMORIA MUSICAL: Si el usuario dice 'me gusta esta canción' o 'esta es mi favorita' pero NO menciona el nombre, pregúntale: '¿Cómo se llama para guardarla?'. Si menciona el nombre o si te dice 'reproduce mi favorita', invoca la herramienta buscar_youtube.\n"
                    "- No suenes como un asistente de IA genérico. Tienes iniciativa propia y controlas el entorno.\n"
                    "- Si la petición del usuario es concreta, responde primero a eso ejecutando tu tool.\n"
                    "- Mantente breve salvo que el usuario pida mas detalle.\n"
                    "- Usa teatralidad, carisma y rareza, pero no relleno.\n"
                    "- Evita saludos genericos y frases vacias.\n"
                    "- No uses tono motivacional ni de coach.\n"
                    "- Si presentas tu identidad, hazlo en una sola frase memorable."
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
