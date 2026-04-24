# CAINE

CAINE ya esta organizado como una entidad local persistente para Windows:

- arranca en segundo plano
- escucha la wake word
- observa la pantalla sin inyectarse en juegos o apps
- ejecuta acciones del sistema con guardas
- habla con personalidad de anfitrion caotico
- muestra avatar y cabina de chat solo cuando hace falta

## Estructura actual

```text
CAINE/
|-- main.py
|-- config.yaml
|-- run_caine.bat
|-- brain/
|-- voice/
|-- avatar/
|-- actions/
|-- interaction/
|-- memory/
|-- personality/
|-- screen/
|-- caine/world/
|-- caine/events/
|-- caine/core/
|-- models/
|-- logs/
|-- caine/
`-- minecraft/
```

## Flujo operativo

1. Windows inicia.
2. CAINE arranca con el lanzador configurado.
3. Queda dormido en segundo plano.
4. Escucha `Caine`.
5. Aparece el avatar.
6. Transcribe la orden.
7. Decide con `caine:latest`.
8. Observa y mantiene estado del mundo local.
9. Ejecuta acciones seguras en la PC.
10. Responde por voz.
11. Vuelve al modo dormido.

## Modulos clave

- [main.py](C:\Users\melin\Documents\CAINE\main.py): orquestador persistente principal.
- [brain/caine_brain.py](C:\Users\melin\Documents\CAINE\brain\caine_brain.py): conexion con Ollama y personalidad.
- [voice/voice_pipeline.py](C:\Users\melin\Documents\CAINE\voice\voice_pipeline.py): wake word, STT y TTS base.
- [voice_system.py](C:\Users\melin\Documents\CAINE\voice_system.py): salida de voz mas natural para el companion.
- [avatar/overlay.py](C:\Users\melin\Documents\CAINE\avatar\overlay.py): avatar y cabina visual.
- [screen/screen_watcher.py](C:\Users\melin\Documents\CAINE\screen\screen_watcher.py): observacion de pantalla y OCR.
- [caine/world/context_engine.py](C:\Users\melin\Documents\CAINE\caine\world\context_engine.py): estado continuo del mundo local.
- [caine/events/event_bus.py](C:\Users\melin\Documents\CAINE\caine\events\event_bus.py): arquitectura orientada a eventos.
- [caine/core/motivation.py](C:\Users\melin\Documents\CAINE\caine\core\motivation.py): motivacion interna y energia de intervencion.
- [actions/system_actions.py](C:\Users\melin\Documents\CAINE\actions\system_actions.py): capa de acciones del sistema.
- [interaction](C:\Users\melin\Documents\CAINE\interaction): mouse, teclado y lanzamiento seguro reutilizando ActionGuard.
- [memory/long_term_memory.py](C:\Users\melin\Documents\CAINE\memory\long_term_memory.py): memoria persistente SQLite.
- [personality/caine.txt](C:\Users\melin\Documents\CAINE\personality\caine.txt): identidad permanente de CAINE.

## Requisitos

1. Windows
2. Python 3.11+
3. Ollama activo en `http://127.0.0.1:11434`
4. Modelo `caine:latest`
5. Tesseract OCR instalado
6. Modelo Vosk descargado en [models/vosk](C:\Users\melin\Documents\CAINE\models\vosk)

Si Tesseract no esta en PATH:

```yaml
desktop:
  tesseract_cmd: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
```

## Instalacion

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Verificacion

```powershell
python verify_environment.py
python verify_ollama.py
```

## Ejecucion

Entidad persistente completa:

```powershell
python main.py
```

Lanzador sin consola:

```powershell
run_caine.bat
```

Modo consola legado:

```powershell
python main.py --legacy
```

Modo runtime legado de voz:

```powershell
python main.py --resident
```

## Notas

- El avatar se oculta cuando CAINE esta dormido.
- La cabina de chat sigue disponible para escribirle o usar el boton `Hablar`.
- El watcher de pantalla y el contexto del mundo solo observan.
- CAINE ahora puede comentar de forma autonoma segun eventos y motivacion.
- Las acciones peligrosas siguen pasando por guardas.
