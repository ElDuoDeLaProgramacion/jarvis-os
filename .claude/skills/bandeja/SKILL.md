---
name: bandeja
description: Resumen matutino de David. Correo, calendario y noticias de IA en un resumen corto para leer en voz alta. Úsala para "resumen matutino", "resumen de la bandeja", "reporte AM" o "qué tengo hoy".
---
# Bandeja (resumen matutino)

1. **Correo**: si hay conector de correo, lee los no leídos de las últimas 24 h. Agrupa en: requiere respuesta, informativo, ruido. Si no hay conector, usa lo que haya en `boveda/raw/bandeja/` y di que el correo no está conectado.
2. **Calendario**: si hay conector, eventos de hoy. Si no, busca la agenda en el plan de hoy (`boveda/outputs/planes/`).
3. **Noticias de IA**: 3 titulares de las últimas 24 h con WebSearch, cada uno en una línea con su enlace.
4. Escribe `boveda/outputs/resumenes/AAAA-MM-DD-matutino.md` con frontmatter (`fecha`, `tipo: resumen`, `tags`) y las tres secciones. Enlaza el plan del día si existe.
5. Responde en voz, máximo 4 frases: cuántos correos piden respuesta, el primer evento y la noticia más relevante.

Nunca respondas ni archives correos sin confirmación.
