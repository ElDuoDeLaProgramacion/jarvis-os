# HUD de JARVIS

Una sola pantalla oscura con todo lo que JARVIS debe saber. Sin pestañas.

| Zona | Qué muestra |
|---|---|
| Izquierda | Vitales (CPU con gráfica, memoria, disco), tareas resueltas por la cola, rutinas del día e informes recientes de la bóveda (clic para leerlos) |
| Centro | La bóveda como esfera 3D: cada punto grande es una nota y cada línea un enlace `[[...]]`. Gira más rápido cuando JARVIS está trabajando. Debajo, el total de notas y una caja para pedirle cualquier cosa |
| Derecha | Reloj, panel de comandos, agenda y prioridades del plan de hoy, pendientes (en rojo si están vencidos) y actividad de la cola con las últimas respuestas |

Los botones y la caja de texto **encolan** la intención y arrancan el corredor (fase 2), así que el resultado aparece en "Actividad" y en la bóveda cuando JARVIS termina.

## Abrir

Desde Windows: doble clic en `P:\jarvis-os\hud\abrir-hud.bat` (arranca el servidor en WSL y abre el navegador).
Si tu distribución no se llama `Ubuntu`: `abrir-hud.bat NombreExacto`.

Desde Ubuntu: `./scripts/hud.sh` y abre http://localhost:7777 en el navegador de Windows.

No hay que instalar nada: el servidor usa solo Python 3 de Ubuntu, y solo escucha en `localhost`.

## Cambiar los botones

Edita la lista `COMANDOS` al inicio de `hud/servidor.py`: cada entrada es `("Etiqueta", "pedido que se encola")`.
