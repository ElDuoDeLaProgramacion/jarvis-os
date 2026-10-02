# HUD de JARVIS

Una sola pantalla oscura con todo lo que JARVIS debe saber. Sin pestañas.

| Zona | Qué muestra |
|---|---|
| Izquierda | Vitales (CPU con gráfica, memoria, disco), tareas resueltas por la cola, rutinas del día e informes recientes de la bóveda (clic para leerlos) |
| Centro | La bóveda como esfera 3D: cada punto grande es una nota y cada línea un enlace `[[...]]`. Gira más rápido cuando JARVIS está trabajando. Debajo, el total de notas y una caja para pedirle cualquier cosa |
| Derecha | Reloj, panel de comandos, agenda y prioridades del plan de hoy, pendientes (en rojo si están vencidos) y actividad de la cola con las últimas respuestas |

Los botones y la caja de texto **encolan** la intención y arrancan el corredor (fase 2), así que el resultado aparece en "Actividad" y en la bóveda cuando JARVIS termina.

## Abrir

El HUD es un programa aparte, con su propia ventana: no usa el navegador.

1. Una sola vez: doble clic en `P:\jarvis-os\hud\instalar.bat` (instala `pywebview` en `hud\.venv`).
2. Cada vez: doble clic en `P:\jarvis-os\hud\abrir-hud.bat`. Arranca el servidor en WSL sin consola, abre la ventana "JARVIS" maximizada y, al cerrarla, apaga el servidor.

Opciones: `abrir-hud.bat --pantalla-completa` y `abrir-hud.bat --distro NombreExacto` si tu distribución no se llama `Ubuntu`.

Para que se abra solo al iniciar sesión, mira [Arranque automático](../rutinas/README.md#arranque-automático-del-hud-y-la-voz).

La ventana usa el motor web que ya trae Windows 10 y 11 (WebView2). El servidor usa solo Python 3 de Ubuntu y solo escucha en `localhost`; si quieres, también puedes abrir http://localhost:7777 a mano tras `./scripts/hud.sh`.

## Cambiar los botones

Edita la lista `COMANDOS` al inicio de `hud/servidor.py`: cada entrada es `("Etiqueta", "pedido que se encola")`.
