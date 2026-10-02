# JARVIS OS

Asistente personal por voz. Tú hablas, JARVIS ejecuta el trabajo.

**Ciclo:** voz → JARVIS → Claude Code → habilidad → respuesta hablada.

| Parte | Rol | Dónde vive |
|---|---|---|
| Claude Code | El motor: enruta cada petición a la habilidad adecuada | `CLAUDE.md`, `.claude/skills/` |
| Obsidian | La memoria: todo aterriza como Markdown enlazado | `boveda/` |
| Voz local | Oídos y boca: STT entra, TTS sale, 100% privado | `voz/` (fase 4) |
| HUD | La cara: una pantalla con vitales, agenda y comandos | `hud/` (fase 3) |

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
scripts/jarvis.sh punto de entrada por texto (la voz lo usará después)
```

## Requisitos (Windows + WSL)

1. WSL con Ubuntu: `wsl --install -d Ubuntu` en PowerShell si aún no lo tienes.
2. Dentro de Ubuntu: Node 18+ y Claude Code (`npm install -g @anthropic-ai/claude-code`), luego `claude` una vez para iniciar sesión.
3. Obsidian en Windows: "Open folder as vault" y elige `\\wsl$\Ubuntu\home\<tu-usuario>\jarvis-os\boveda`.

## Uso

```bash
cd ~/jarvis-os
./scripts/jarvis.sh "plan de hoy"
./scripts/jarvis.sh "resumen de la bandeja"
./scripts/jarvis.sh "¿qué decidí la semana pasada sobre el HUD?"
```

O abre `claude` en la carpeta y habla con él normalmente: las habilidades se cargan solas.

## Habilidades

| Habilidad | Qué hace | Escribe en |
|---|---|---|
| `metricas` | Extrae tus números (suscriptores, vistas, seguidores) | `outputs/metricas/` |
| `bandeja` | Resumen de la mañana: correo, calendario, noticias de IA | `outputs/resumenes/` |
| `tendencias` | Escanea lo que se mueve en tus temas | `outputs/tendencias/` |
| `plan` | Escribe las 3 prioridades de hoy | `outputs/planes/` |
| `boveda` | Lee y escribe memoria; mantiene el grafo enlazado | `raw/`, `wiki/` |
| `cierre-dia` | Reflexión del día y cola de mañana | `outputs/diario/` |

Regla: habilidades pequeñas de un solo propósito superan a un prompt gigante.

## Día real

| Hora | Comando | Qué pasa |
|---|---|---|
| 7:00 | "Resumen matutino" | Bandeja, calendario y noticias de IA, leído en voz alta |
| 9:00 | "Plan de hoy" | Las 3 prioridades aterrizan en la bóveda |
| 14:00 | "Métricas" | Suscripciones, vistas, seguidores rastreados |
| 19:00 | "Cierra el día" | Reflexión registrada, mañana en cola |
| Siempre | Cualquier pregunta | La bóveda recuerda todo |

## Hoja de ruta

1. **Cerebro + memoria** (este repo hoy): habilidades, bóveda, enrutador.
2. **Corredor y rutinas**: cola de intenciones y horarios automáticos.
3. **HUD**: panel oscuro de una sola pantalla servido en local.
4. **Voz**: push-to-talk, STT local (faster-whisper) y TTS local (Piper).
5. **Fuentes reales**: correo, calendario, YouTube/redes, GitHub trending.
