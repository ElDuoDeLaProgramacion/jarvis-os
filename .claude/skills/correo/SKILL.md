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

## Imágenes y adjuntos
Si David pide meter una imagen o un archivo ("con la captura de pantalla", "adjunta el logo", una ruta):
1. Ubica el archivo. "La captura" es la última de `cola/pantalla/`; también sirven rutas de `perfil.md`, de la bóveda o las que David dé.
2. Revisa el tamaño (`ls -l`). Si pasa de 5 MB, dile a David que es grande y pregunta si va igual.
3. Sácale el base64 con `python3 -c "import base64,sys; print(base64.b64encode(open(sys.argv[1],'rb').read()).decode())" RUTA`.
4. Ponlo en `attachments` de `create_draft` con `filename`, `mimeType` (`image/png`, `image/jpeg`, `application/pdf`...) y el `content`.
   - Imagen dentro del texto: `inline: true` y en `htmlBody` pon `<img src="cid:NOMBRE-DEL-ARCHIVO">`. Escribe también `body` en texto plano.
   - Si no se ve dentro del texto, déjala como adjunto normal (`inline` en false).
   - Una imagen de internet va en `htmlBody` con `<img src="https://...">`, sin adjuntarla.
5. En el resumen, di qué adjuntaste: "Va con la captura adjunta. ¿Lo envío? Sí o no." Al enviar, manda el mismo borrador con sus adjuntos.

## Enviar
- Solo puedes enviar en la respuesta a ese "¿Lo envío?", cuando David dijo que sí: en ese momento (y solo entonces) tienes las herramientas `send_message` y `reply` del conector. Si no las tienes, es que no hubo un "sí": deja el borrador y díselo.
- Envía exactamente el borrador que le resumiste (mismo destinatario, asunto y texto; `reply` si era una respuesta a un hilo). No borres nada: el borrador enviado sale solo de Borradores.
- Confirma en una frase: "Enviado a <quién>." Si dijo que no, deja el borrador y di que queda en Borradores.

**Nunca envíes un correo que David no confirmó con un "sí", ni reenvíes, borres o archives correos.**
