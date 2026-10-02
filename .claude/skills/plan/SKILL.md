---
name: plan
description: Escribe las 3 prioridades del día (o de mañana, o la revisión semanal) en la bóveda. Úsala para "plan de hoy", "plan de mañana", "prioridades" o "revisión semanal".
---
# Plan

## Plan de hoy / mañana
1. Lee: `boveda/wiki/perfil.md` (metas), el último cierre en `boveda/outputs/diario/` (lo que quedó en cola) y el plan anterior en `boveda/outputs/planes/`.
2. Elige exactamente 3 prioridades. Cada una concreta y terminable en el día, ligada a una meta.
3. Si hay calendario disponible, añade la agenda por horas.
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
Lee los planes y cierres de los últimos 7 días, cuenta prioridades cumplidas vs. totales, y escribe `boveda/outputs/planes/AAAA-Wnn-revision.md` con logros, pendientes recurrentes y una propuesta para la semana siguiente.
