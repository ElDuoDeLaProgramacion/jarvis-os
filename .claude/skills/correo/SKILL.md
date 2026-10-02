---
name: correo
description: Trabaja con el correo de David. Leer y resumir la bandeja, buscar un correo, redactar respuestas o correos nuevos. Úsala para cualquier petición sobre correos, bandeja de entrada o "responde a...".
---
# Correo

## Fuente
- El conector **claude.ai Gmail** (cuenta elduodelaprogramacion@gmail.com). Sus herramientas aparecen como `mcp__claude_ai_Gmail__...`.
- Úsalo solo para leer, buscar y crear borradores. Aunque el conector tenga herramientas para reenviar, etiquetar, filtrar o borrar, no las uses sin un "sí" explícito de David en esta conversación.
- Si el conector no está disponible, trabaja con correos guardados en `boveda/raw/correo/` y di que Gmail no está conectado.

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
4. Di en una frase a quién va y qué dice, y termina con: "¿Lo envío? Sí o no." David contesta sin decir "Jarvis".

## Enviar
- Solo puedes enviar en la respuesta a ese "¿Lo envío?", cuando David dijo que sí: en ese momento (y solo entonces) tienes las herramientas `send_message` y `reply` del conector. Si no las tienes, es que no hubo un "sí": deja el borrador y díselo.
- Envía exactamente el borrador que le resumiste (mismo destinatario, asunto y texto; `reply` si era una respuesta a un hilo). No borres nada: el borrador enviado sale solo de Borradores.
- Confirma en una frase: "Enviado a <quién>." Si dijo que no, deja el borrador y di que queda en Borradores.

**Nunca envíes un correo que David no confirmó con un "sí", ni reenvíes, borres o archives correos.**
