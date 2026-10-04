---
tipo: referencia
tags: [jarvis, ayuda]
---
# Qué sabe hacer JARVIS

> Todo empieza con "Jarvis, ...". También puedes escribirlo en la caja del HUD. Relacionado: [[inicio]], [[ideas-jarvis]].

## Al instante (sin pasar por Claude ni gastar uso)
- **Abrir programas:** "abre Chrome / Word / Excel / Spotify / WhatsApp / la calculadora / VS Code". Aguanta errores de la voz ("abri, Spotify", "abre spotifai") y funciona también al contestar sin "Jarvis".
- **Cerrar:**
  - "cierra esta pestaña"
  - "cierra la ventana"
  - "cierra Spotify"
  - "cierra las pestañas de búsqueda de Google"
  - "cierra las pestañas de YouTube"
- **Lienzo 3D:** "abre el lienzo 3D" para dibujar y construir en 3D con las manos frente a la cámara.
- **Propuestas:** "abre las propuestas" para ver el código, las maquetas, los diagramas y las presentaciones que propusieron los paneles de IAs.
- **Música:** "pausa", "play", "siguiente canción", "canción anterior", "sube el volumen", "baja el volumen".
- **Copiloto:** "activa el copiloto", "apaga el copiloto".

## Con Claude
- **Correo:** "resume mi bandeja", "responde a Ana que sí", "manda la captura de pantalla a Ana". Siempre pregunta "¿Lo envío?".
- **Agenda:** "agéndame reunión el lunes a las 3", "mueve la reunión al martes", "elimina la reunión del lunes" (pregunta "¿La borro?" y solo borra con tu "sí").
- **Noticias:** "dame las noticias", "qué pasó hoy en ciberseguridad".
- **Aprender:** "aprende de Rust", "ponte al día en agentes de IA". Lo guarda en `wiki/conocimiento/`. También aprende solo cada noche de las noticias y tendencias.
- **Recomendar:** "recomiéndame una herramienta para...", "¿qué debería aprender?".
- **Ideas:** "evalúa esta idea: ...", "hazle de abogado del diablo a...". Te da nota, riesgos y cómo probarla.
- **Pantalla:** "lee mi pantalla".
- **Analizar:** "analiza este archivo / PDF / enlace / video". Abre la ventana del HUD.
- **Música:** "pon Bad Bunny", "ponme algo para concentrarme", "qué está sonando".
- **Programación:** "hazme un proyecto de...", "revisa el error de...".
- **Memoria:** "recuerda que...", "¿qué decidí sobre...?", "limpieza de bóveda".
- **Día a día:** "plan de hoy", "resumen matutino", "cierra el día", "revisa mis suscripciones", "tendencias".

## Agentes especializados
- "pídele al auditor que revise el servidor", "que el revisor mire mi proyecto X", "que el diseñador proponga la pantalla de...", "junta al equipo para crear un programa que...".
- Agentes: programador, revisor de código, auditor de seguridad, diseñador, juez de ideas, investigador. Gastan más uso: JARVIS los llama solo cuando vale la pena.
- **IAs externas:** "pregúntale a Gemini...", "¿qué opina GPT de...?", "segunda opinión de otras IAs sobre...". Necesitan las claves `GEMINI_API_KEY` u `OPENROUTER_API_KEY` en `.env`.
- **Panel de IAs:** "audita y evalúa el proyecto X con todas las IAs", "que varias IAs propongan la landing de mi canal", "panel de marketing y diseño para...". De cualquier tema, varias IAs por especialidad más los agentes de Claude; JARVIS verifica y te da la conclusión en `outputs/panel/`. Lo que proponen lo ves en la ventana de propuestas (botón del HUD o de la app).
- En todo trabajo grande (crear o revisar código, diseñar, planes grandes, marketing, evaluar ideas) JARVIS arma el panel solo. Di "sin panel" o "solo tú" para que lo haga solo Claude. Todas las IAs ven la memoria de la bóveda, sin chats, correos, personas, dinero, diario ni seguridad.

## Seguridad (solo tus sistemas, sin cambiar nada)
- "prueba la seguridad del servidor" / "audita este equipo": SSH, puertos, cortafuegos, actualizaciones, usuarios, intentos de entrada y lynis.
- "qué puertos tiene abiertos el servidor": escaneo con nmap (solo localhost o lo que esté en `JARVIS_OBJETIVOS_SEGURIDAD` del `.env`).
- "revisa el certificado y las cabeceras de https://...": TLS y cabeceras de seguridad de una web tuya.
- "busca vulnerabilidades en el proyecto ...": `npm audit` y `pip-audit`.
- "audita el código de ...": bandit, semgrep y secretos olvidados en el código (gitleaks).
- "audita todos mis servidores": uno por uno lo que está en `JARVIS_OBJETIVOS_SEGURIDAD`, con un informe resumen.
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
