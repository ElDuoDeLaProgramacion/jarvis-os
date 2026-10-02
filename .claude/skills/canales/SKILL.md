---
name: canales
description: Revisa los canales y redes de David (YouTube, TikTok, GitHub, etc.) y registra sus números. Úsala cuando pida métricas, seguidores, vistas o "cómo van los canales".
---
# Canales

1. Lee la sección "Canales" de `boveda/wiki/perfil.md`. Si está vacía, dilo y pide cuáles revisar.
2. Para cada canal obtén el valor actual de su métrica:
   - Conector o herramienta de esa plataforma si existe.
   - Si no, la página pública del perfil con WebFetch/WebSearch.
   - Si no se puede, `sin dato`. Nunca inventes cifras.
3. Compara con la nota anterior más reciente en `boveda/outputs/canales/`.
4. Escribe `boveda/outputs/canales/AAAA-MM-DD.md` con frontmatter (`fecha`, `tipo: canales`, `tags`), una tabla Canal | Métrica | Valor | Cambio, y enlace a la nota anterior.
5. Responde en voz con el dato principal y el mayor cambio.
