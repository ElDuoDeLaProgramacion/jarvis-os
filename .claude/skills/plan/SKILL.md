---
name: plan
description: Escribe las 3 prioridades del día (o de mañana, o la revisión semanal) a partir de tareas, correo, proyectos y metas. Úsala para "plan de hoy", "plan de mañana", "prioridades" o "revisión semanal".
---
# Plan

## Plan de hoy / mañana
1. Lee: metas y proyectos en `boveda/wiki/perfil.md`, pendientes en `boveda/wiki/tareas.md`, la cola del último cierre en `boveda/outputs/diario/`, y el resumen matutino de hoy si existe.
2. Elige exactamente 3 prioridades, de cualquier área (correo, programación, archivos, canales...). Cada una concreta y terminable en el día.
3. Añade la agenda por horas con los eventos del día del conector **claude.ai Google Calendar** (zona horaria de Bogotá). Si no está disponible, deja solo las prioridades. Nunca crees, muevas ni borres eventos sin que David lo pida.
4. Escribe `boveda/outputs/planes/AAAA-MM-DD.md`:
   ```
   ---
   fecha: AAAA-MM-DD
   tipo: plan
   tags: [plan]
   ---
   ## Prioridades
   1. [ ] ...
   2. [ ] ...
   3. [ ] ...
   ## Agenda
   - 09:30 ...
   Viene de: [[cierre anterior]]
   ```
5. Responde en voz con las 3 prioridades, una frase cada una.

## Revisión semanal
Lee planes, cierres y tareas completadas de los últimos 7 días. Escribe `boveda/outputs/planes/AAAA-Wnn-revision.md` con logros por área, pendientes que se repiten y una propuesta para la semana siguiente.
