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
4. **Evolución:**
   - Revisa `logs/jarvis.log` de hoy y las líneas nuevas de `boveda/wiki/aprendizajes.md`.
   - Une los aprendizajes repetidos en uno y quita los que ya no apliquen. Muévelos a `raw/archivo/`, no los borres.
   - Si hoy algo salió mal o hiciste lo mismo varias veces a mano, añade una idea concreta a `boveda/wiki/ideas-jarvis.md`, como una habilidad nueva, un comando de voz o una rutina.
5. Responde en voz: cuántas prioridades se cumplieron, la primera cosa en cola para mañana y, si la hay, la idea de mejora del día en una frase.
