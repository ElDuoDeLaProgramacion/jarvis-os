---
name: metricas
description: Extrae y registra los números de David (suscriptores, vistas, seguidores, estrellas). Úsala cuando pida métricas, números, "cómo van los canales" o el reporte de las 14:00.
---
# Métricas

1. Lee la tabla "Canales y métricas" de `boveda/wiki/perfil.md`.
2. Para cada plataforma obtén el valor actual:
   - Si hay un conector o herramienta para esa plataforma, úsala.
   - Si no, busca la página pública del perfil con WebFetch/WebSearch.
   - Si no se puede obtener, márcala como `sin dato` (nunca inventes cifras).
3. Busca la nota de métricas anterior más reciente en `boveda/outputs/metricas/` y calcula la variación.
4. Escribe `boveda/outputs/metricas/AAAA-MM-DD.md`:
   ```
   ---
   fecha: AAAA-MM-DD
   tipo: metricas
   tags: [metricas]
   ---
   | Plataforma | Métrica | Valor | Cambio |
   ...
   Anterior: [[AAAA-MM-DD]]
   ```
5. Responde en voz: la cifra principal y el mayor cambio, en una o dos frases.
