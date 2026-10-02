# JARVIS OS

Asistente de trabajo por voz. Tú hablas, JARVIS ejecuta el trabajo: correos, archivos, programación, búsquedas, tareas, canales y más.

**Ciclo:** voz → JARVIS → Claude Code → habilidad → respuesta hablada.

| Parte | Rol | Dónde vive |
|---|---|---|
| Claude Code | El motor: enruta cada petición a la habilidad adecuada | `CLAUDE.md`, `.claude/skills/` |
| Obsidian | La memoria: todo aterriza como Markdown enlazado | `boveda/` |
| Voz local | Oídos y boca: STT entra, TTS sale, 100% privado | `voz/` |
| HUD | La cara: una pantalla con vitales, agenda y comandos | `hud/` |

Sin base de datos. Solo archivos Markdown que puedes leer y editar a mano.
Totalmente modular: cualquier pieza se puede intercambiar.

## Estructura

```
.claude/skills/   una carpeta por habilidad, cada una con su SKILL.md
CLAUDE.md         reglas del enrutador
boveda/           vault de Obsidian
  raw/            todo lo capturado (sin procesar)
  wiki/           conocimiento depurado
  outputs/        todo lo que JARVIS entrega (reportes, planes, resúmenes)
scripts/          jarvis.sh (petición directa), encolar.sh, corredor.sh, rutina.sh
cola/             intenciones pendientes, en curso, hechas y fallidas
rutinas/          horarios del día real para el Programador de tareas de Windows
hud/              la pantalla de JARVIS (servidor local + página)
```

## Requisitos (Windows + WSL)

1. WSL con Ubuntu: `wsl --install -d Ubuntu` en PowerShell si aún no lo tienes.
2. Dentro de Ubuntu, instala Claude Code con el instalador nativo (no necesita Node ni sudo):
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
   claude
   ```
   El último comando abre Claude Code para iniciar sesión. No uses `sudo npm install -g`: la versión de npm pide Node 22+ y con sudo deja permisos rotos.
3. Prepara la unidad P: en WSL para que git pueda trabajar ahí (sin esto `git clone` falla con `chmod ... Operation not permitted`):
   ```bash
   cat /etc/wsl.conf   # si ya tiene una sección [automount], añade metadata a sus options en vez de duplicarla
   printf '\n[automount]\noptions = "metadata,umask=22,fmask=11"\n' | sudo tee -a /etc/wsl.conf
   ```
   Luego en PowerShell: `wsl --shutdown`, y vuelve a abrir Ubuntu. Comprueba con `ls /mnt/p`.
   Si `/mnt/p` no existe (unidad mapeada o `subst`), móntala a mano:
   ```bash
   sudo mkdir -p /mnt/p && sudo mount -t drvfs P: /mnt/p -o metadata,uid=$(id -u),gid=$(id -g)
   ```
4. Clona el repo en P: (ahí viven todos los proyectos):
   ```bash
   cd /mnt/p && git clone https://github.com/ElDuoDeLaProgramacion/jarvis-os
   ```
5. Revisa `boveda/wiki/perfil.md`: ahí están tus carpetas, proyectos y correo.
6. Obsidian en Windows: "Open folder as vault" y elige `P:\jarvis-os\boveda`.

## Uso

```bash
cd /mnt/p/jarvis-os
./scripts/jarvis.sh "plan de hoy"
./scripts/jarvis.sh "resume mis correos de hoy"
./scripts/jarvis.sh "busca en Descargas el PDF de la factura de septiembre"
./scripts/jarvis.sh "investiga qué modelo de STT local funciona mejor en Windows"
./scripts/jarvis.sh "¿qué decidí la semana pasada sobre el HUD?"
```

O abre `claude` en la carpeta y habla con él normalmente: las habilidades se cargan solas.

## Hablar con JARVIS

Instala la voz siguiendo [voz/README.md](voz/README.md). Luego abre `P:\jarvis-os\voz\jarvis.bat`, mantén **F9**, habla y suelta.

No hay comandos fijos: le hablas normal. Ejemplos:

- "Ponme al día" / "resumen matutino"
- "Plan de hoy" / "¿qué tengo pendiente?"
- "Anota la tarea: terminar el bot de WhatsApp para el viernes"
- "Revisa el estado del proyecto Hands-Free Navigator"
- "Busca en Descargas el PDF de la factura de septiembre"
- "Investiga las mejores librerías de detección facial en Python"
- "¿Qué hay de nuevo en inversiones esta semana?"
- "¿Cómo van mis canales?"
- "Recuerda que la reunión con el cliente es el lunes" → "¿qué sé del cliente?"
- "Cierra el día"

## HUD

Doble clic en `P:\jarvis-os\hud\abrir-hud.bat` y se abre la pantalla de JARVIS en el navegador: vitales, panel de comandos, agenda, pendientes, actividad de la cola y la bóveda en vivo. Detalles en [hud/README.md](hud/README.md).

## Habilidades

| Habilidad | Qué hace | Escribe en |
|---|---|---|
| `correo` | Resume la bandeja, busca correos, redacta respuestas (nunca envía sin confirmar) | `outputs/correo/` |
| `archivos` | Busca, resume, ordena y convierte archivos en tus carpetas | `outputs/archivos/` |
| `programacion` | Explica y arregla código, crea scripts, corre pruebas (en ramas, sin push sin confirmar) | `outputs/programacion/` |
| `busqueda` | Investiga en la web y deja un informe con fuentes | `outputs/busquedas/` |
| `tareas` | Añade, lista y completa pendientes | `wiki/tareas.md` |
| `resumen-dia` | Resumen matutino: correo, agenda, pendientes y noticias | `outputs/resumenes/` |
| `plan` | Las 3 prioridades de hoy y la revisión semanal | `outputs/planes/` |
| `tendencias` | Lo que se mueve en tus temas | `outputs/tendencias/` |
| `canales` | Números de tus redes y canales | `outputs/canales/` |
| `boveda` | Lee y escribe memoria; mantiene el grafo enlazado | `raw/`, `wiki/` |
| `cierre-dia` | Reflexión del día y cola de mañana | `outputs/diario/` |

Regla: habilidades pequeñas de un solo propósito superan a un prompt gigante.

## Día real (rutinas automáticas)

| Hora | Rutina | Qué pasa |
|---|---|---|
| 7:00 | "Resumen matutino" | Correo, agenda, pendientes y noticias, en `outputs/resumenes/` |
| 9:00 | "Plan de hoy" | Las 3 prioridades aterrizan en la bóveda |
| 14:00 | "Revisa pendientes" | Tareas del día y correos que esperan respuesta |
| 19:00 | "Cierra el día" | Reflexión registrada, mañana en cola |
| Siempre | Cualquier pregunta | La bóveda recuerda todo |

Instálalas una vez en Windows siguiendo [rutinas/README.md](rutinas/README.md). Funcionan así: el Programador de tareas encola la intención en `cola/` y el corredor la ejecuta.

Para dejar algo en cola tú mismo: `./scripts/encolar.sh "investiga X"` y luego `./scripts/corredor.sh`.

## Hoja de ruta

1. **Cerebro + memoria** (hecha): habilidades, bóveda, enrutador.
2. **Corredor y rutinas** (hecha): cola de intenciones y horarios automáticos.
3. **HUD** (hecha): panel oscuro de una sola pantalla servido en local.
4. **Voz** (hecha): push-to-talk en Windows, STT local (faster-whisper) y TTS local (voces de Windows o Piper).
5. **Fuentes reales**: correo, calendario, almacenamiento en la nube, redes.
