---
name: evaluar-idea
description: Juzga una idea de David (negocio, app, proyecto, video) con el agente juez-ideas y la guarda con su nota. Úsala para "evalúa esta idea", "¿vale la pena...?", "hazle de abogado del diablo a..." o "¿qué tan buena es la idea de...?".
---
# Evaluar una idea

1. Busca en `boveda/outputs/ideas/` si David ya evaluó algo parecido; si sí, pásale esa nota al juez para que diga qué cambió.
2. Lanza el agente `juez-ideas` con la idea tal como la dijo David y lo que sepas de contexto. Si la idea es técnica (una app, una herramienta), lanza en paralelo al `investigador` para buscar alternativas existentes.
3. Escribe `boveda/outputs/ideas/AAAA-MM-DD-<idea>.md` (frontmatter `fecha`, `tipo: idea`, `nota`, `tags`): la idea en una frase, la tabla de criterios con su nota, riesgos, cómo probarla en una semana y fuentes.
4. Si David decide seguir o descartarla, anótalo en `boveda/wiki/decisiones.md` con el porqué.

## Respuesta hablada
La nota global, el punto más fuerte y el riesgo más serio, en tres frases. Pregunta si la sigue solo si la nota es 7 o más.
