---
name: analizar
description: Analiza fuentes que David agrega en la ventana de análisis del HUD (archivos, PDFs, imágenes, documentos, hojas de cálculo, audio, video, enlaces web o de YouTube y texto copiado) y responde lo que quiere saber. Úsala para "analiza las fuentes de ...", "analiza este archivo/PDF/enlace/video" o "resume este documento".
---
# Analizar fuentes

El pedido llega como `analiza las fuentes de boveda/raw/analisis/<fecha-hora>/fuentes.md`, a veces con "Lo que quiero saber: ...". Si David dice "analiza este archivo" sin más, la voz ya le abrió la ventana para agregar fuentes; no hace falta pedirlas.

## Leer cada fuente
1. Lee `fuentes.md`: lista los archivos guardados en esa carpeta, los enlaces y el texto copiado.
2. Según el tipo:
   - **PDF, imágenes, Markdown, texto, CSV**: ábrelos con Read (lee PDFs e imágenes directamente; en PDFs largos, por páginas).
   - **Word (.docx), PowerPoint (.pptx), Excel (.xlsx)**: extrae el texto con `python3` (son zip con XML: `word/document.xml`, `ppt/slides/*.xml`, `xl/sharedStrings.xml` y `xl/worksheets/*.xml`). Si `pdftotext` o `pandoc` están, también sirven.
   - **Audio y video**: usa la transcripción `<archivo>.txt` que deja la voz al lado. Si no existe (vino por la cola, sin voz), dilo y analiza lo demás.
   - **Enlaces web**: WebFetch. **YouTube**: WebFetch del enlace para título, canal y descripción; si hace falta el contenido del video y no hay transcripción, dilo en una frase.
3. No inventes lo que una fuente no dice. Si una fuente no se pudo leer, dilo.

## Responder
1. Escribe `boveda/outputs/analisis/AAAA-MM-DD-<tema>.md` con frontmatter (`fecha`, `tipo: analisis`, `tags`), la respuesta a lo que David quería saber (o un resumen con las ideas clave si no preguntó nada), los puntos importantes por fuente y enlace a `[[fuentes]]` de la carpeta en `raw/analisis/`.
2. Si sale algo que hacer, propónlo como tarea, pero solo añádelo a `boveda/wiki/tareas.md` si David lo pide.
3. Responde en voz, 3 o 4 frases: lo más importante primero.
