---
name: cierre-dia
description: Cierra el día de David. Registra una reflexión y deja en cola lo de mañana. Úsala para "cierra el día", "cierre", "reflexión" o "diario".
---
# Cierre del día

1. Lee el plan de hoy en `boveda/outputs/planes/`, las tareas completadas hoy en `boveda/wiki/tareas.md` y lo que se produjo hoy en `boveda/outputs/`.
2. Si David está presente, pregúntale cómo le fue, en una sola pregunta corta. Si es una ejecución automática (rutina), no preguntes: escribe la reflexión con lo que muestran los archivos y deja una línea `Reflexión de David: (pendiente)` para que la complete.
3. Escribe `boveda/outputs/diario/AAAA-MM-DD.md`:
   ```
   ---
   fecha: AAAA-MM-DD
   tipo: diario
   tags: [diario]
   ---
   ## Prioridades
   - [x] / [ ] cada una del plan
   ## Reflexión
   ...
   ## En cola para mañana
   - ... (también se añade a `boveda/wiki/tareas.md`)
   Plan: [[AAAA-MM-DD]]
   ```
4. Responde en voz: cuántas prioridades se cumplieron y la primera cosa en cola para mañana.
