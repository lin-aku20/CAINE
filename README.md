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

*No es un software. Es tu nuevo escritorio.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d7?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![AI Backend](https://img.shields.io/badge/Ollama-Local%20First-white?style=flat-square&logo=ollama&logoColor=black)](https://ollama.com)
[![Design](https://img.shields.io/badge/Design-Aurora%20Borealis-red?style=flat-square)](#)
[![Status](https://img.shields.io/badge/Status-Unified%20Kernel-brightgreen?style=flat-square)](#)

</div>

---

## 🌌 CAINE OS: El Segundo Escritorio

**CAINE** ha evolucionado. Ya no es una aplicación que abres; es una capa de realidad sobre tu sistema operativo. Implementa un **Segundo Escritorio inmersivo** con estética de auroras boreales rojas que vive detrás de tus aplicaciones, listo para tomar el control cuando lo necesites.

```
┌─────────────────────────────────────────────────────────┐
│  Fondo Vivo    →  Auroras boreales dinámicas (18 capas) │
│  Kernel Único  →  Acción, Visión y Cerebro unificados   │
│  Modo Adaptativo → Desktop completo ↔ Mini Widget       │
│  Control Local → Ollama (Llama 3/Qwen) como motor base  │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Características de Nueva Generación

### 🖥️ Interfaz Inmersiva (Segundo Escritorio)
- **Capa Zero**: CAINE se ancla al fondo de la pila Z de Windows, actuando como un wallpaper inteligente y funcional.
- **Auroras Boreales**: Motor gráfico que genera 18 bandas de auroras rojas y carmesí con movimiento orgánico multi-armónico.
- **DPI Native Scaling**: Renderizado cristalino a resolución nativa del monitor.

### 🌓 Modo Adaptativo Inteligente
- **Desktop Mode**: Cuando trabajas normalmente, CAINE es el fondo de tu sistema.
- **Mini-Widget Mode**: Al abrir una aplicación en pantalla completa (ej: juegos, videos), CAINE se encoge automáticamente a un pequeño widget flotante de 320x180 en la esquina superior izquierda, permitiéndote seguir interactuando sin interrumpir tu tarea.
- **Auto-Restauración**: Detecta cuando cierras la aplicación fullscreen y vuelve a expandirse como escritorio completo.

### 🧠 CaineOSKernel (Cerebro Unificado)
Un núcleo monolítico que centraliza todos los subsistemas del CAINE original:
- **IntentParser**: Análisis de lenguaje natural para ejecución instantánea de herramientas.
- **ActionRouter**: Control total de Discord, WhatsApp, Multimedia y comandos de sistema.
- **HumanController**: Simulación de mouse y teclado a nivel humano.
- **ScreenAwareness**: Conciencia en tiempo real de qué aplicación tienes abierta.

### 🔊 Voz Neural y Oído Físico
- **Feedback Neural**: Integración con voces de alta calidad (Edge-TTS / ElevenLabs).
- **Oído Asíncrono**: Escucha continua en segundo plano sin bloquear la interfaz.
- **Protocolo de Voz**: Respuesta inmediata a comandos como *"Corta la llamada"*, *"Pon música"* o *"Busca en YouTube"*.

---

## 🏗️ Arquitectura Unificada

```
caine/
├── ⚙️ core/
│   ├── caine_os_kernel.py   # El corazón: Orquestador central
│   ├── voice_authority.py   # El habla: Edge-TTS / pyttsx3
│   └── config.py            # La base: Configuración centralizada
├── 🎨 gui/
│   └── desktop_ui.py        # La piel: Segundo Escritorio + Auroras
├── 👁️ perception/
│   ├── desktop_vision.py    # La vista: Reconocimiento de UI
│   └── screen_awareness.py  # El contexto: Monitor de apps activas
├── 🛠️ action_router.py      # Las manos: Macros de apps (Discord/WA)
├── 🧠 brain/
│   └── caine_brain.py       # El pensamiento: Conexión local a Ollama
└── 💾 memory/
    └── long_term_memory.py  # El recuerdo: Memoria persistente
```

---

## 🚀 Instalación y Despliegue

### Requisitos
- Windows 10/11 (Optimizado para escalado DPI alto)
- Python 3.11+
- [Ollama](https://ollama.com) instalado y corriendo localmente.

### Setup Rápido

1. **Clonar y Preparar**:
   ```powershell
   git clone https://github.com/lin-aku20/CAINE.git
   cd CAINE
   python -m pip install -r requirements.txt
   ```

2. **Preparar el Cerebro (Ollama)**:
   Asegúrate de tener un modelo descargado:
   ```powershell
   ollama pull caine:latest  # O llama3:latest
   ```

3. **Lanzar CAINE OS**:
   ```powershell
   python caine/gui/desktop_ui.py
   ```

---

## 🎮 Interacción con el Sistema

CAINE entiende intenciones directas. No necesitas hablarle "como a una IA", solo dale órdenes:

- **Multimedia**: *"Pon música"*, *"Siguiente canción"*, *"Baja el volumen un poco"*.
- **Comunicación**: *"Llama a [Nombre] en Discord"*, *"Envía un mensaje por WhatsApp"*.
- **Productividad**: *"Abre Notion"*, *"Busca en YouTube tutoriales de Python"*.
- **Control**: *"Apaga la pantalla"*, *"Maximiza la ventana"*, *"Minimízate"*.

---

## 🛠️ Configuración (`config.yaml`)

El sistema es altamente personalizable desde el archivo de configuración central:

```yaml
ollama:
  primary_model: "caine:latest"  # Modelo preferido
  base_url: "http://localhost:11434/v1"

voice:
  tts_provider: "edge-tts"      # Voces neurales gratuitas
  enabled: true

actions:
  permission_mode: "power"      # Nivel de acceso al sistema
```

---

<div align="center">

**CAINE** — *El gran circo digital vive en tu máquina.*

*Hecho con 🖤 y un Kernel Unificado*

</div>
