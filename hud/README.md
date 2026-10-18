# HUD de Orión

Una sola pantalla oscura con todo lo que Orión debe saber. Sin pestañas.

| Zona | Qué muestra |
|---|---|
| Izquierda | Vitales (CPU con gráfica, memoria, disco), tareas resueltas por la cola e informes recientes de la bóveda (clic para leerlos) |
| Centro | La bóveda como esfera 3D: cada punto grande es una nota y cada línea un enlace `[[...]]`. Gira más rápido cuando Orión está trabajando. Debajo, el total de notas y una caja para pedirle cualquier cosa |
| Derecha | Reloj, panel de comandos, agenda y prioridades del plan de hoy, pendientes (en rojo si están vencidos) y actividad de la cola con las últimas respuestas |

Los botones y la caja de texto **encolan** la intención y arrancan el corredor (fase 2), así que el resultado aparece en "Actividad" y en la bóveda cuando Orión termina.

## Abrir

El HUD es un programa aparte, con su propia ventana: no usa el navegador.

1. Una sola vez: doble clic en `P:\jarvis-os\hud\instalar.bat` (instala `pywebview` en `hud\.venv`).
2. Cada vez: doble clic en `P:\jarvis-os\hud\abrir-hud.bat`. Arranca el servidor en WSL sin consola, abre la ventana "Orión" maximizada y, al cerrarla, apaga el servidor.

Opciones: `abrir-hud.bat --pantalla-completa` y `abrir-hud.bat --distro NombreExacto` si tu distribución no se llama `Ubuntu`.

Para que se abra solo al iniciar sesión, mira [Arranque automático](../rutinas/README.md#arranque-automático-del-hud-y-la-voz).

La ventana usa el motor web que ya trae Windows 10 y 11 (WebView2). El servidor usa solo Python 3 de Ubuntu y solo escucha en `localhost`; si quieres, también puedes abrir http://localhost:7777 a mano tras `./scripts/hud.sh`.

## Analizar fuentes

El botón **＋ Analizar** (o decir "Orión, analiza este archivo") abre una ventana para agregar fuentes: subir o arrastrar archivos (PDF, imágenes, documentos, hojas de cálculo, audio, video), pegar enlaces web o de YouTube, pegar texto y escribir qué quieres saber. Las fuentes se guardan en `boveda/raw/analisis/<fecha-hora>/` (no se suben a git) y el informe queda en `boveda/outputs/analisis/`.

- Abierta por voz: Orión transcribe audio y video y te responde hablando.
- Abierta con el botón: el análisis va a la cola y aparece en "Actividad" (audio y video sin transcribir).

## Propuestas de las IAs

El botón **Propuestas** (o "Orión, abre las propuestas") abre `http://localhost:7777/propuestas`: lo que propusieron los paneles de IAs (habilidad `panel`), con la conclusión, una pestaña "Lo visual" (maquetas HTML en vivo, diagramas, presentaciones y código con botón de copiar) y una columna por IA. Lee `boveda/outputs/panel/` y además muestra los demás informes de `boveda/outputs/` (auditorías, programación, planes...) y las páginas `.html` que haya creado Orión, agrupados por tipo. **Eliminar** quita la que estás viendo y **Seleccionar** deja marcar varias; no se borran al momento: van a `boveda/.papelera/<fecha>/` y se vacían solas a los 30 días. Las maquetas corren en un marco aislado, sin acceso a la API del HUD. Las bibliotecas van en `hud/vendor/`; los diagramas cargan Mermaid de internet solo cuando hacen falta.

## Cambiar los botones

Edita la lista `COMANDOS` al inicio de `hud/servidor.py`: cada entrada es `("Etiqueta", "pedido que se encola")`.
