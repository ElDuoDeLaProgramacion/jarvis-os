---
name: archivos
description: Trabaja con archivos y carpetas de David. Buscar, abrir y resumir documentos, ordenar carpetas, renombrar, convertir formatos o extraer datos. Úsala para peticiones sobre archivos, documentos, PDFs, hojas de cálculo o carpetas.
---
# Archivos

## Dónde buscar
- Las carpetas de trabajo están en la sección "Carpetas" de `boveda/wiki/perfil.md`.
- En WSL, las carpetas de Windows están en `/mnt/c/Users/<usuario>/...`.
- No salgas de esas carpetas salvo que David dé una ruta concreta.

## Tareas
- **Buscar**: Glob por nombre y Grep por contenido. Responde con la ruta y una línea de qué es.
- **Resumir**: lee el archivo y guarda el resumen en `boveda/outputs/archivos/AAAA-MM-DD-<nombre>.md` con la ruta original.
- **Ordenar / renombrar / mover**: primero muestra el plan (origen → destino) y espera confirmación. Nunca borres: mueve a una carpeta `_papelera` dentro de la misma carpeta.
- **Convertir o extraer** (PDF a texto, CSV a tabla, etc.): usa las herramientas instaladas; si falta una, dilo y propone cuál instalar.

Responde en voz con el resultado en una o dos frases; el detalle va al archivo.
