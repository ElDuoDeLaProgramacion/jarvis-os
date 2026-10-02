---
name: correo
description: Trabaja con el correo de David. Leer y resumir la bandeja, buscar un correo, redactar respuestas o correos nuevos. Úsala para cualquier petición sobre correos, bandeja de entrada o "responde a...".
---
# Correo

## Fuente
- Si hay un conector de correo (Gmail, Outlook) disponible, úsalo.
- Si no, trabaja con correos guardados en `boveda/raw/correo/` y di que el correo no está conectado.

## Resumir la bandeja
1. No leídos de las últimas 24 h (o el rango que pida).
2. Agrupa: requiere respuesta, informativo, ruido.
3. Escribe `boveda/outputs/correo/AAAA-MM-DD-bandeja.md` con una línea por correo (remitente, asunto, qué pide).

## Buscar
Busca por remitente, asunto o tema y responde con lo que dice el correo, citando remitente y fecha.

## Redactar
1. Lee el hilo completo antes de escribir.
2. Usa el tono de David: directo y cordial, en el idioma del hilo.
3. Deja el texto como borrador (en el conector si lo permite, si no en `boveda/outputs/correo/AAAA-MM-DD-borrador-<tema>.md`).
4. Lee el borrador en voz alta y pregunta si lo envía.

**Nunca envíes, borres ni archives correos sin un "sí, envíalo" explícito de David.**
