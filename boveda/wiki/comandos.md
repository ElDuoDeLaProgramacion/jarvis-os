---
tipo: referencia
tags: [jarvis, ayuda]
---
# Qué sabe hacer JARVIS

> Todo empieza con "Jarvis, ...". También puedes escribirlo en la caja del HUD. Relacionado: [[inicio]], [[ideas-jarvis]].

## Al instante (sin pasar por Claude ni gastar uso)
- **Abrir programas:** "abre Chrome / Word / Excel / Spotify / WhatsApp / la calculadora / VS Code".
- **Cerrar:**
  - "cierra esta pestaña"
  - "cierra la ventana"
  - "cierra Spotify"
  - "cierra las pestañas de búsqueda de Google"
  - "cierra las pestañas de YouTube"
- **Lienzo 3D:** "abre el lienzo 3D" para dibujar y construir en 3D con las manos frente a la cámara.
- **Música:** "pausa", "play", "siguiente canción", "canción anterior", "sube el volumen", "baja el volumen".
- **Copiloto:** "activa el copiloto", "apaga el copiloto".

## Con Claude
- **Correo:** "resume mi bandeja", "responde a Ana que sí", "manda la captura de pantalla a Ana". Siempre pregunta "¿Lo envío?".
- **Agenda:** "agéndame reunión el lunes a las 3".
- **Pantalla:** "lee mi pantalla".
- **Analizar:** "analiza este archivo / PDF / enlace / video". Abre la ventana del HUD.
- **Música:** "pon Bad Bunny", "ponme algo para concentrarme", "qué está sonando".
- **Programación:** "hazme un proyecto de...", "revisa el error de...".
- **Memoria:** "recuerda que...", "¿qué decidí sobre...?", "limpieza de bóveda".
- **Día a día:** "plan de hoy", "resumen matutino", "cierra el día", "revisa mis suscripciones", "tendencias".

## Seguridad (solo tus sistemas, sin cambiar nada)
- "prueba la seguridad del servidor" / "audita este equipo": SSH, puertos, cortafuegos, actualizaciones, usuarios, intentos de entrada y lynis.
- "qué puertos tiene abiertos el servidor": escaneo con nmap (solo localhost o lo que esté en `JARVIS_OBJETIVOS_SEGURIDAD` del `.env`).
- "revisa el certificado y las cabeceras de https://...": TLS y cabeceras de seguridad de una web tuya.
- "busca vulnerabilidades en el proyecto ...": `npm audit` y `pip-audit`.
- El informe queda en `outputs/seguridad/` con los comandos para arreglar; JARVIS no aplica nada solo.

## Desde la app de Android
- Di "Jarvis", espera el pitido y di el pedido. Funciona con la pantalla apagada. Si JARVIS pregunta algo, contestas tras el segundo pitido sin decir "Jarvis".
- "pon música de Queen", "pausa", "siguiente": suena en el Spotify del celular.
- Todo lo de "Con Claude" funciona igual, salvo lo que necesita el PC (archivos de `P:\`, pantalla, gestos, volumen).

## Desde el celular (WhatsApp)
- Escríbete a ti mismo (el chat "Tú") lo mismo que le dirías por voz: "plan de hoy", "agéndame...", "resume mis correos". JARVIS contesta en ese chat. Ver `whatsapp/README.md`.
- **Tus chats:** "¿qué me escribieron hoy?", "¿qué dijo Ana?", "respóndele a Ana que llego a las 8" (te muestra el mensaje y lo envía solo si dices "sí").

## Sin que se lo pidas
- **Copiloto:** cuando juegas ajedrez o programas, mira la pantalla de vez en cuando y habla solo si ve algo útil.
- **Rutinas:** 7:00 resumen, 9:00 plan, 14:00 pendientes, 19:00 cierre.
