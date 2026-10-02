---
name: resumen-dia
description: Resumen matutino de David. Junta correo, agenda, tareas pendientes y noticias relevantes en un resumen corto para leer en voz alta. Úsala para "resumen matutino", "reporte AM", "qué tengo hoy" o "ponme al día".
---
# Resumen del día

Junta lo que otras habilidades saben hacer, sin repetir su trabajo en detalle:

1. **Correo**: sigue la habilidad `correo` en modo resumen (últimas 24 h): cuántos piden respuesta y de quién.
2. **Agenda**: eventos de hoy (zona horaria de Bogotá) con el conector **claude.ai Google Calendar**; si no está disponible, la agenda del plan de hoy en `boveda/outputs/planes/`.
3. **Pendientes**: lo abierto en `boveda/wiki/tareas.md` con fecha de hoy o vencido, y lo que quedó en cola en el último cierre (`boveda/outputs/diario/`).
4. **Noticias**: 3 titulares de las últimas 24 h sobre los "Temas" de `boveda/wiki/perfil.md` (WebSearch), con enlace.
5. Escribe `boveda/outputs/resumenes/AAAA-MM-DD-matutino.md` con las cuatro secciones y enlaces a las notas que usaste.
6. Responde en voz, máximo 4 frases: lo urgente primero.
