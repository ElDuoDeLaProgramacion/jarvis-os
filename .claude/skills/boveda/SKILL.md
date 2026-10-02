---
name: boveda
description: Lee y escribe la memoria de JARVIS en la bóveda de Obsidian. Úsala para recordar, guardar, anotar, responder "¿qué sé de...?" o "¿qué decidí...?", y para la limpieza de bóveda.
---
# Bóveda

La bóveda (`boveda/`) es la única memoria. Son archivos Markdown enlazados con `[[...]]`.

## Guardar ("recuerda que...", "anota...")
1. Escribe la captura tal cual en `boveda/raw/AAAA-MM-DD-tema.md` con frontmatter (`fecha`, `tipo: captura`, `tags`).
2. Si es un hecho estable (una decisión, una preferencia, un dato de un proyecto), actualiza o crea la nota correspondiente en `wiki/` y enlaza la captura.
3. Confirma en voz en una frase.

## Consultar ("¿qué sé de X?")
1. Grep en `boveda/` por X y sinónimos. Prioriza `wiki/`, luego `outputs/`, luego `raw/`.
2. Sigue los enlaces `[[...]]` de las notas encontradas un nivel.
3. Responde citando de qué nota sale cada dato. Si no hay nada, dilo: no inventes.

## Limpieza de bóveda
1. Busca en `raw/` capturas de más de 7 días que no estén enlazadas desde `wiki/`.
2. Propón a qué nota de `wiki/` va cada una; aplica solo lo que David confirme.
3. Detecta enlaces rotos y notas huérfanas en `wiki/` y lístalos en `boveda/outputs/AAAA-MM-DD-limpieza.md`.

Nunca borres archivos; mueve lo obsoleto a `raw/archivo/`.
