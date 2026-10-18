---
name: noticias
description: Noticias del día en los temas de David (tecnología, IA, programación, ciberseguridad y los de su perfil), con fuentes. Úsala para "noticias", "qué pasó hoy en...", "dame las noticias de tecnología".
---
# Noticias

1. Lee "Temas" en `boveda/wiki/perfil.md`. Siempre incluye IA, programación y ciberseguridad (vulnerabilidades graves, parches urgentes).
2. Busca lo de las últimas 24 h (WebSearch; un lunes, desde el viernes). Prefiere la fuente original. Descarta rumores sin fuente y lo que ya salió en `boveda/outputs/noticias/` de días anteriores.
3. Elige máximo 8 noticias. Cada una: titular propio, dos frases de qué pasó, una de por qué le importa a David y el enlace.
4. Marca con **⚠** lo que le toca actuar: una vulnerabilidad en algo que usa (mira `boveda/wiki/perfil.md` y `boveda/wiki/proyectos/`), un cambio de precio o de API de un servicio suyo.
5. Escribe `boveda/outputs/noticias/AAAA-MM-DD.md` (frontmatter `fecha`, `tipo: noticias`, `tags`).

`resumen-dia` puede usar esta nota si ya existe para hoy en vez de buscar otra vez.

## Respuesta hablada
Las dos más importantes en una frase cada una, y las ⚠ si hay.
