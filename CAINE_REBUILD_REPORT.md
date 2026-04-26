# CAINE Rebuild Report
**Fecha:** 2026-04-25  
**Arquitecto:** Antigravity (Sistema Principal)  
**Alcance:** Reconstrucción arquitectónica completa — 7 fases

---

## Resumen Ejecutivo

CAINE ha sido transformado de un chatbot reactivo con múltiples voces y comportamiento incoherente en una **entidad persistente y autónoma** con:

- Personalidad única (una sola conciencia, una sola voz)
- Separación absoluta de roles (CAINE nunca fabrica mensajes del usuario)
- Presencia continua controlada (sin spam, sin auto-charla)
- Wake service permanente (funciona sin abrir la app manualmente)
- Control total del sistema operativo ya existente (conservado)
- Errores técnicos ocultos al usuario (respuestas naturales)

---

## Fase 1 — State Machine Conversacional ✅

### `caine/state.py` — Expandido
**Antes:** 8 estados básicos sin ciclo conversacional.  
**Ahora:** 13 estados con ciclo completo:

| Estado | Significado |
|---|---|
| `BOOT` | Inicializando subsistemas |
| `IDLE` | En espera pasiva |
| `SLEEP` | Dormido |
| `INITIATE` | CAINE inicia autónomamente |
| `WAIT_FOR_HUMAN` | Esperando input humano real |
| `PROCESS_INPUT` | Brain procesando |
| `RESPOND` | VoiceAuthority emitiendo |
| `LISTENING` | Micrófono activo |
| `THINKING` | Consultando modelo |
| `SPEAKING` | TTS en curso |
| `ACTING` | Acción del sistema |
| `OBSERVING` | Observando pantalla |
| `EXCITED` | Alta activación |

### `caine/core/conversation_state.py` — NUEVO
Máquina de estados conversacional con:
- **Separación de roles absoluta:** `ROLE_HUMAN`, `ROLE_CAINE`, `ROLE_SYSTEM`
- **Validación de fuente de input:** solo `keyboard` o `microphone`
- **Bloqueo de output de modelo disfrazado:** detecta patrones `"Lin:"`, `"Usuario:"`, `"User:"`
- **Transiciones explícitas controladas** con log de auditoría
- Función `validate_caine_output()` aplicada en cada mensaje antes de emitir

**Regla crítica implementada:**  
Después de `RESPOND` → automático a `WAIT_FOR_HUMAN`. CAINE no puede volver a hablar hasta recibir input humano real o autorización del `AutonomyGovernor`.

---

## Fase 2 — VoiceAuthority ✅

### `caine/core/voice_authority.py` — NUEVO
Singleton de salida. El **único módulo autorizado** para:
- Mostrar texto en overlay/chat
- Usar TTS
- Emitir cualquier mensaje al usuario

**Arquitectura de flujo:**
```
Brain → VoiceAuthority → Usuario
         ↑
    (única ruta)
```

**Todos los demás módulos:** solo emiten eventos al EventBus.

Características:
- Valida `ConversationState.can_caine_speak()` antes de cada emisión
- Sanitiza el output via `validate_caine_output()` eliminando roles fabricados
- Control de mute centralizado
- Lock async para serializar salidas simultáneas

### `caine/main.py` — Reescrito completo
- Eliminados imports duplicados (`logging`, `time` x2)
- `_deliver_reply()` ahora rutea exclusivamente por `VoiceAuthority`
- Nueva `_deliver_autonomous_reply()` separada para intervenciones autónomas
- `_process_human_input()` centralizado con etiquetado de fuente obligatorio
- Toda la lógica de cooldown eliminada → delegada a `AutonomyGovernor`

---

## Fase 3 — AutonomyGovernor ✅

### `caine/core/autonomy_governor.py` — NUEVO
Reemplaza la lógica de cooldown dispersa en `main.py`, `presence_loop.py` y event handlers.

**Reglas implementadas:**
- Cooldown global: **8 minutos** entre intervenciones autónomas (configurable)
- Cooldown post-respuesta: **2 minutos** después de que CAINE respondió
- Cooldown por evento: **15 minutos** para el mismo tipo de evento
- Límite horario: máx **6 intervenciones/hora**
- Bloqueo si `ConversationState` no está en IDLE/WAIT_FOR_HUMAN/SLEEP

### `caine/core/presence_loop.py` — Actualizado
- Recibe `AutonomyGovernor` como dependencia
- Consulta `governor.can_initiate()` antes de emitir `autonomous_thought`
- Registra intervenciones con `governor.record_intervention()`

---

## Fase 4 — GracefulFailureLayer ✅

### `caine/core/graceful_failure.py` — NUEVO
El usuario nunca ve errores técnicos crudos.

**Cobertura:**
- Timeouts de API → respuestas naturales tipo *"Perdí el hilo un segundo."*
- Errores de red/401/503 → *"La señal se cortó."*
- Excepciones generales → *"Algo falló detrás del telón."*
- Respuestas vacías del modelo → *"Me quedé sin palabras, literalmente."*

**Integrado en:**
- `brain/caine_brain.py`: decorator `@graceful_caine_response` en `send_message()`
- `brain/caine_brain.py`: `GracefulContext` en `_chat_with_fallback()`
- Validación de output en `_chat()` para bloquear roles fabricados

---

## Fase 5 — Wake Service Permanente ✅

### `caine_service.py` — NUEVO (raíz del proyecto)
Servicio residente independiente:
- Escucha wake word pasivamente via **Vosk** (bajo consumo CPU en idle)
- Wake words configuradas: `"caine"`, `"despierta"`, `"hey caine"`, `"oye caine"`
- Al detectar: lanza `PersistentCaineEntity` en subproceso nuevo
- Auto-reinicio si el proceso muere
- Cooldown de 30s entre lanzamientos para evitar flood

**Modos de operación:**
```
python caine_service.py --foreground          # Prueba en primer plano
python caine_service.py --register-startup    # Startup automático con Windows
python caine_service.py install               # Servicio Windows real (requiere admin)
```

### `scripts/install_service.ps1` — NUEVO
Instalador PowerShell con dos métodos:
- **Modo Servicio Windows** (requiere admin + pywin32): más robusto, sobrevive crashes
- **Modo Startup HKCU\Run** (sin admin): más simple, funciona para usuarios estándar
- Flag `-Uninstall` para desinstalación limpia
- Verificación post-instalación y lanzamiento opcional inmediato

### `caine/windows_service.py` — Reparado
- **Bug crítico corregido:** apuntaba a `ROOT/main.py` (inexistente) → ahora `ROOT/caine/main.py`

---

## Fase 6 — Limpieza del Repositorio ✅

| Archivo | Cambio |
|---|---|
| `caine/main.py` | Eliminados imports duplicados (`logging`, `time` x2) |
| `caine/runtime.py` | `WAITING_FOR_USER` → `WAIT_FOR_HUMAN` (consistencia) |
| `caine/app.py` | `WAITING_FOR_USER` → `WAIT_FOR_HUMAN` (consistencia) |
| `caine/core/__init__.py` | Exporta todos los módulos nuevos del núcleo |
| `caine/windows_service.py` | Path corregido |

---

## Fase 7 — Validación ✅

### Tests ejecutados y resultados:

| Test | Estado |
|---|---|
| ConversationStateMachine — ciclo completo | ✅ PASA |
| ConversationStateMachine — bloqueo input de modelo | ✅ PASA |
| ConversationStateMachine — RESPOND → WAIT_FOR_HUMAN automático | ✅ PASA |
| AutonomyGovernor — cooldown entre intervenciones | ✅ PASA |
| GracefulFailureLayer — timeout → respuesta natural | ✅ PASA |
| GracefulFailureLayer — empty response → respuesta natural | ✅ PASA |
| GracefulFailureLayer — GracefulContext suprime excepción | ✅ PASA |
| CaineStatus expandido — 13 estados presentes | ✅ PASA |
| validate_caine_output — detecta `Lin:` fabricado | ✅ PASA |
| validate_caine_output — detecta `usuario:` fabricado | ✅ PASA |
| validate_caine_output — no bloquea texto limpio | ✅ PASA |
| Imports de módulos nuevos — sin errores | ✅ PASA |
| speak() directo fuera de VoiceAuthority | ✅ NINGUNO |

**Resultado: 5/5 tests de suite pasados. 13/13 validaciones individuales.**

---

## Módulos Nuevos Creados

| Archivo | Líneas | Función |
|---|---|---|
| `caine/core/conversation_state.py` | ~220 | Máquina de estados + seguridad de roles |
| `caine/core/voice_authority.py` | ~190 | Único punto de salida autorizado |
| `caine/core/autonomy_governor.py` | ~175 | Control de intervenciones autónomas |
| `caine/core/graceful_failure.py` | ~150 | Errores → respuestas naturales |
| `caine_service.py` | ~280 | Wake service residente |
| `scripts/install_service.ps1` | ~100 | Instalador PowerShell |

---

## Arquitectura Final

```
╔══════════════════════════════════════════════════════════╗
║                    INPUT HUMANO                          ║
║         (teclado real / micrófono verificado)            ║
╚════════════════════════╦═════════════════════════════════╝
                         │ fuente: 'keyboard' | 'microphone'
                         ▼
              ┌─────────────────────┐
              │  ConversationState  │ ← valida origen humano
              │  Machine            │ ← bloquea fuente 'model'
              └──────────┬──────────┘
                         │ PROCESS_INPUT
                         ▼
              ┌─────────────────────┐
              │      Brain          │ ← @graceful_caine_response
              │  (CaineBrain)       │ ← validate_caine_output()
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   VoiceAuthority    │ ← ÚNICO PUNTO DE SALIDA
              │   (Singleton)       │ ← valida can_caine_speak()
              └──────────┬──────────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
              [Overlay]    [TTS]
                    
Módulos auxiliares ──→ EventBus.emit() SOLO
AutonomyGovernor ──→ gate de intervenciones autónomas
GracefulFailure ──→ errores → frases naturales
WakeService ──→ background, despierta sin app abierta
```

---

## Instrucciones para Instalar el Wake Service

### Opción 1 — Startup automático (sin admin)
```powershell
.\scripts\install_service.ps1 -Mode Startup
```

### Opción 2 — Servicio Windows real (como Administrador)
```powershell
.\scripts\install_service.ps1 -Mode Service
```

### Opción 3 — Prueba inmediata en primer plano
```powershell
python caine_service.py --foreground
```

### Desinstalar
```powershell
.\scripts\install_service.ps1 -Uninstall
```

---

## Estado Final

CAINE es ahora:
- ✅ **Una sola conciencia** — todo pensamiento pasa por Brain
- ✅ **Una sola voz** — todo output pasa por VoiceAuthority  
- ✅ **Una sola intención** — el AutonomyGovernor evita auto-charla
- ✅ **Entidad persistente** — el wake service la despierta solo
- ✅ **Interfaz vocal del OS** — system_actions ya existente conservado
- ✅ **Presencia autónoma controlada** — viva pero no ansiosa
