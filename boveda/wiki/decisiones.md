---
tipo: decisiones
tags: [jarvis, memoria]
---
# Decisiones

> Qué se decidió, cuándo y por qué. La más reciente va arriba. Relacionado: [[aprendizajes]], [[proyectos/jarvis-os]].

- 2026-10-04 · El servidor y el PC se actualizan solos desde GitHub (servidor cada 15 min, PC al iniciar sesión y cada 2 h) en vez de hacer git pull a mano. Se descartó una app de escritorio conectada al servidor porque el PC perdería archivos, programación, copiloto y gestos.
- 2026-10-04 · JARVIS hace pruebas de seguridad solo de los sistemas de David (este equipo, el servidor y lo que esté en `JARVIS_OBJETIVOS_SEGURIDAD`), sin fuerza bruta, exploits ni cambios: da los comandos para arreglar.
- 2026-10-04 · La app de Android solo se activa con un "Jarvis" claro (confianza alta en el resultado final), para no crear mensajes por ruido.
- 2026-10-03 · App de Android propia con la palabra "Jarvis" detectada por Vosk en el celular. Picovoice se descartó porque pide correo de empresa.
- 2026-10-03 · El servidor es Clouding (Ubuntu 24.04, usuario david) porque Oracle no dejó crear la máquina.
- 2026-10-03 · JARVIS vive en un servidor gratis de Oracle Cloud, con la bóveda dentro (sincronizada con el PC por Syncthing), para usar WhatsApp y una app del celular con el PC apagado. La app llega al celular por Tailscale, no por internet abierto.
- 2026-10-03 · WhatsApp por QR (Baileys) en lugar de Kapso: Kapso rechazaba la clave, y el QR no necesita claves y además deja leer los chats personales. Riesgo aceptado: no es oficial.
- 2026-10-02 · JARVIS es un asistente de trabajo general: correo, archivos, programación, búsqueda, tareas y canales. No es solo para creadores de contenido.
- 2026-10-02 · El HUD es un programa propio, no una pestaña del navegador.
- 2026-10-02 · La voz se activa diciendo "Jarvis", no con F9.
- 2026-10-02 · Los gestos son solo los básicos de Hands-Free Navigator: mover, clic izquierdo y derecho, Tab, cambio de pestaña y scroll.
- 2026-10-02 · Los correos se envían solo con un "sí" de David, nunca desde rutinas.
- 2026-10-02 · Copiloto: no sugiere jugadas en partidas de ajedrez en vivo contra personas, porque va contra las reglas de chess.com y lichess.
