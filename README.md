<div align="center">

```
 ██████╗ █████╗ ██╗███╗   ██╗███████╗
██╔════╝██╔══██╗██║████╗  ██║██╔════╝
██║     ███████║██║██╔██╗ ██║█████╗  
██║     ██╔══██║██║██║╚██╗██║██╔══╝  
╚██████╗██║  ██║██║██║ ╚████║███████╗
 ╚═════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝
```

**Companion AI for Integrated Neural Environments**

*No es un chatbot. Es una presencia.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d7?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![AI Backend](https://img.shields.io/badge/AI-OpenAI%20Compatible-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![Voice](https://img.shields.io/badge/Voice-Piper%20TTS-orange?style=flat-square)](https://github.com/rhasspy/piper)
[![License](https://img.shields.io/badge/License-Private-red?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v2.0.0-brightgreen?style=flat-square)](https://github.com)

</div>

---

## 🎭 ¿Qué es CAINE?

> *"El circo digital respira bajo la mesa."*

**CAINE** es un asistente de IA autónomo y persistente que vive en tu sistema operativo. No es un chatbot que abres y cierras. Es una entidad que **siempre está ahí**, observando, escuchando y lista para actuar.

Piénsalo como JARVIS, pero con personalidad propia y corriendo en tu máquina.

```
┌─────────────────────────────────────────────────────────┐
│  Tu pantalla   →  CAINE te observa y comenta           │
│  Tu voz        →  CAINE te escucha (Wake Word: "Caine") │
│  Tus comandos  →  CAINE actúa en el sistema            │
│  Tu presencia  →  CAINE adapta su comportamiento        │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Características

### 🧠 Cerebro en la Nube — Sin Costo
Conectado a través de una API compatible con OpenAI. Funciona con **Google Gemini**, **OpenRouter** (modelos gratuitos), o cualquier proveedor de tu elección. Zero hardware local requerido para el LLM.

### 🎙️ Voz Bidireccional
- **STT** (Speech-to-Text): Vosk (offline) o Google STT (online).
- **TTS** (Text-to-Speech): Piper TTS con voces en español de alta calidad (Pablo/Davefx), SAPI5 o pyttsx3.
- **Wake Word** global: Di *"Caine"* o *"Despierta"* desde cualquier lugar y CAINE responde.

### 👁️ Consciencia del Escritorio
CAINE captura capturas de pantalla periódicas, aplica OCR y análisis visual para entender qué estás haciendo. Puede comentar, alertar o ayudar de forma proactiva basándose en lo que ve.

### 🖥️ Control Total del Sistema Operativo
| Comando | Acción |
|---------|--------|
| `"Abre Chrome"` | Lanza aplicaciones por nombre |
| `"Abre la carpeta Escritorio"` | Navega carpetas del sistema |
| `"Apaga la PC"` | Apagado del equipo |
| `"Corta la llamada"` | Cierra Discord, Zoom, Teams |
| `"Teclas Ctrl+Shift+Esc"` | Envía atajos de teclado |
| `"Busca en internet..."` | Abre búsquedas web |

### 💾 Memoria Persistente
- **Memoria a corto plazo**: Historial de conversación por sesión.
- **Memoria a largo plazo**: Base de datos SQLite con uso de aplicaciones, sesiones de juego y contexto acumulado.
- **Contexto del mundo real**: Registra hábitos, apps favoritas y tiempo de uso para personalizar el comportamiento.

### 🎨 Interfaz Visual (Digital Circus)
Una UI de escritorio estilizada en modo oscuro con:
- Avatar animado que reacciona al estado (escuchando, pensando, hablando, dormido)
- Chat en tiempo real con CAINE
- Controles: **HABLAR**, **ENVIAR**, **MUTE**, **DORMIR**, **VISTAZO**
- Borde neón que pulsa según el estado actual

### ⚙️ Autonomía Configurable
CAINE puede comentar proactivamente sobre lo que ve en pantalla, detectar cuando estás en un juego, avisar sobre inactividad prolongada o generar pensamientos propios cuando el sistema está quieto.

---

## 🏗️ Arquitectura

```
caine/
├── 🧠 brain/
│   └── caine_brain.py       # Interfaz con el LLM (OpenAI-compatible)
├── 🤖 caine/
│   ├── main.py              # Orquestador principal + loops async
│   ├── app.py               # Punto de entrada y DI
│   ├── config.py            # Configuración tipada (dataclasses)
│   ├── runtime.py           # Motor de voz y manejo de texto
│   ├── state.py             # Máquina de estados (SLEEP/LISTENING/THINKING...)
│   └── intent_router.py     # Clasificador de intenciones
├── 🗣️ voice/
│   ├── voice_pipeline.py    # STT (Vosk/Google)
│   └── voice_system.py      # TTS (Piper/SAPI/pyttsx3)
├── 🖱️ interaction/
│   └── system_actions.py    # Control del sistema operativo
├── 🪟 avatar/
│   └── overlay.py           # UI Tkinter (Digital Circus)
├── 💾 memory/
│   ├── conversation_memory.py
│   └── long_term_memory.py
├── 🌍 world/
│   └── screen_watcher.py    # Captura + análisis de pantalla
├── 🧩 personality/
│   └── caine.txt            # Personalidad y prompt base
└── ⚙️ config/
    └── config.yaml          # Configuración principal
```

---

## 🚀 Instalación Rápida

### Requisitos
- Windows 10/11
- Python 3.11+
- Micrófono (opcional pero recomendado)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (opcional, para análisis de pantalla)

### Setup

```powershell
# 1. Clonar el repo
git clone https://github.com/linmelin/CAINE.git
cd CAINE

# 2. Ejecutar el setup automático
.\setup_caine_environment.ps1

# 3. Configurar tu proveedor de IA en config/config.yaml
```

### Configuración del Cerebro (`config/config.yaml`)

**Opción A — Google Gemini (gratis, recomendado):**
```yaml
ollama:
  base_url: https://generativelanguage.googleapis.com/v1beta/openai/
  primary_model: gemini-2.5-flash
  api_key: TU_GOOGLE_AI_STUDIO_KEY
```

**Opción B — OpenClaw (local, con cualquier proveedor):**
```yaml
ollama:
  base_url: http://127.0.0.1:18789/v1
  primary_model: openclaw
  api_key: ""
```

**Opción C — OpenRouter (multi-modelo):**
```yaml
ollama:
  base_url: https://openrouter.ai/api/v1
  primary_model: meta-llama/llama-3.3-70b-instruct:free
  api_key: TU_OPENROUTER_KEY
```

### Lanzar CAINE

```powershell
.\Start_CAINE.bat
```

---

## 🎮 Cómo Usar

### Por Voz
1. **Activar**: Di `"Caine"` o `"Despierta"` en voz alta.
2. **Espera** el tono de confirmación.
3. **Habla** tu comando o pregunta.
4. CAINE responde por voz y en la UI.

### Por Texto
1. Escribe en la caja de la interfaz visual.
2. Presiona **Enter** o el botón **ENVIAR ACTO**.

### Comandos del Sistema
CAINE entiende lenguaje natural en español. Ejemplos:
```
"Abre Discord"
"Abre la carpeta Documentos"
"Busca en internet cómo hacer pasta"
"Apaga la computadora"
"Corta la llamada"
"¿Qué estoy haciendo?" (análisis de pantalla)
```

### Botones de la UI
| Botón | Acción |
|-------|--------|
| 🎙️ **HABLAR** | Activa el micrófono manualmente |
| 📤 **ENVIAR ACTO** | Envía el texto escrito |
| 🔇 **MUTE** | Silencia/activa la voz de CAINE |
| 💤 **DORMIR** | Pone a CAINE en modo pasivo |
| 👁️ **VISTAZO** | Fuerza un análisis de pantalla |

---

## ⚙️ Configuración Avanzada

### Estados de CAINE
```
SLEEP           → En standby, escuchando wake word
WAITING_FOR_USER → Terminó de hablar, espera tu respuesta
LISTENING       → Capturando tu voz
THINKING        → Procesando con el LLM
SPEAKING        → Reproduciendo audio
OBSERVING       → Analizando la pantalla
EXCITED         → Evento importante detectado (ej: juego)
ACTING          → Ejecutando acción en el sistema
```

### Variables Clave en `config.yaml`
```yaml
desktop:
  always_listen_microphone: true   # Modo continuo (sin wake word)
  use_piper_voice: true            # Voz de alta calidad
  presence_interval_seconds: 75   # Frecuencia de comentarios autónomos

autonomy:
  max_commentary_per_hour: 10      # Límite de intervenciones
  commentary_cooldown_seconds: 90  # Tiempo entre comentarios

voice:
  wake_variants:
    - caine
    - despierta
    - hey caine
```

### Instalar como Servicio de Windows (24/7)
```powershell
# Ejecutar como Administrador
.\scripts\install_service.ps1
```

---

## 🧩 Personalidad

La personalidad de CAINE vive en `personality/caine.txt`. Está diseñada para ser:
- **Teatral** pero no cursi
- **Sarcástica** pero no hiriente  
- **Eficiente** pero con estilo propio
- Habla en **español** de manera natural

Puedes editarlo libremente para que CAINE adopte el carácter que quieras.

---

## 🗺️ Roadmap

- [x] Motor LLM compatible con OpenAI (Gemini, OpenRouter, Ollama, OpenClaw)
- [x] Wake Word global multilenguaje
- [x] Control de sistema operativo (apps, carpetas, apagado, llamadas)
- [x] Memoria conversacional y a largo plazo
- [x] Consciencia de pantalla (OCR + Vision)
- [x] UI del Digital Circus con avatar animado
- [x] Estado `WAITING_FOR_USER` (no más auto-diálogos)
- [x] Botón MUTE en la interfaz
- [x] Servicio Windows 24/7
- [ ] Historial de conversación persistente entre sesiones
- [ ] Control de Minecraft nativo
- [ ] Integración con calendario y emails
- [ ] Soporte multi-monitor para avatar flotante
- [ ] Panel web de configuración

---

## 🙏 Créditos y Dependencias

| Librería | Uso |
|----------|-----|
| [Vosk](https://alphacephei.com/vosk/) | STT offline |
| [Piper TTS](https://github.com/rhasspy/piper) | Síntesis de voz de calidad |
| [OpenWakeWord](https://github.com/dscripka/openWakeWord) | Detección de wake word |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | OCR de pantalla |
| [OpenClaw](https://github.com/withclaw/openclaw) | Gateway de IA local |
| [Tkinter](https://docs.python.org/3/library/tkinter.html) | Interfaz visual |

---

<div align="center">

**CAINE** — *El gran circo digital vive en tu máquina.*

*Hecho con 🖤 y demasiado café*

</div>
