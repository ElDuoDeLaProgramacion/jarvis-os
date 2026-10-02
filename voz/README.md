# Voz y gestos de JARVIS (Windows)

Di **"Jarvis"** seguido de lo que necesitas ("Jarvis, plan de hoy"), o solo "Jarvis" y espera el "¿Sí?". JARVIS transcribe tu voz en local, ejecuta la petición en WSL y **siempre** te contesta en voz alta. Con la cámara, tu mano maneja el ratón: mover, clic, clic derecho, Tab y cambio de pestaña.

```
micrófono → faster-whisper (local) → "¿empieza por Jarvis?" → wsl: scripts/jarvis.sh → Claude Code + habilidades → voz de Windows
cámara    → MediaPipe (local) → gestos de Hands-Free Navigator → ratón y teclado
```

El audio y la imagen nunca salen de tu máquina: la transcripción, los gestos y la voz son locales. Solo el texto de la orden va a Claude.

## Instalar (una vez)

Necesitas Python **para Windows** (no el de WSL): https://www.python.org/downloads/ (marca "Add python.exe to PATH"). Para los gestos tiene que ser **3.9 a 3.12** (MediaPipe aún no funciona con 3.13); la 3.11 es la más segura.

1. Antes, comprueba que JARVIS ya funciona por texto en Ubuntu: `cd /mnt/p/jarvis-os && ./scripts/jarvis.sh "hola"`.
2. En el Explorador abre `P:\jarvis-os\voz` y haz doble clic en `instalar.bat`. Si al final sale el aviso de que los gestos no se instalaron, instala Python 3.11, borra la carpeta `voz\.venv` y vuelve a ejecutarlo.

## Usar

Doble clic en `jarvis.bat` (o se abre solo al iniciar sesión, ver [rutinas](../rutinas/README.md)). La primera vez descarga el modelo de voz (unos 500 MB para `small`). Cuando diga "JARVIS en línea":

- "Jarvis, plan de hoy" → dice "Enseguida", trabaja y te lee la respuesta.
- "Jarvis" a secas → "¿Sí?" → dices la orden en los 8 segundos siguientes.
- Lo que digas sin "Jarvis" al principio se ignora (aparece como "(oído)" en la ventana).
- **Si JARVIS te pregunta algo** ("¿Lo agendo?"), contesta sin decir "Jarvis" en los 20 segundos siguientes: sigue la misma conversación.
- **"Jarvis, lee mi pantalla"** (o cualquier pedido con la palabra "pantalla"): hace una captura, JARVIS la mira y te dice qué hacer. Las últimas 10 capturas quedan en `cola\pantalla\` y no se suben a git.
- **"Jarvis, analiza este archivo"** (o PDF, enlace, video...): se abre la ventana de análisis en el HUD. Agrega archivos, enlaces o texto, pulsa Analizar y JARVIS te responde en voz. El audio y el video se transcriben aquí mismo con Whisper.
- Mientras JARVIS piensa o habla no escucha, para no oírse a sí mismo.
- Si tienes el HUD abierto, "Audio E/S" muestra ESCUCHANDO, PENSANDO o HABLANDO, y cada conversación aparece en "Actividad".

## Gestos

Los gestos básicos de [Hands-Free Navigator](https://github.com/ElDuoDeLaProgramacion/Hands-Free-Navigator): la mano maneja el ratón y el teclado. Índice y medio son los dedos de trabajo; anular y meñique van cerrados.

| Gesto | Acción |
|---|---|
| Índice + medio arriba y **juntos** | Mover el cursor (como un touchpad) |
| ...bajar **ambos** dedos y subirlos | Clic izquierdo (dos veces seguidas: doble clic) |
| ...bajar **solo el medio** y subirlo | Clic derecho |
| Índice + medio **separados** (V), bajar el dedo **derecho** / **izquierdo** | Tab: siguiente / anterior aplicación (Alt+Tab). Se elige al dejar 2 s |
| Palma abierta deslizada a izquierda / derecha | Pestaña anterior / siguiente |
| Puño | Reposo, no hace nada |
| **Cuernos** (índice + meñique) 1 s | Activar / pausar los gestos (JARVIS te dice "Gestos activos" o "Gestos en pausa") |

Arrancan **en pausa** para no mover el ratón al encender el PC: haz los cuernos para activarlos. Scroll, arrastrar, zoom y grabar pantalla se quedan solo en Hands-Free Navigator. Los umbrales están en `voz\manos\config.py` (copia del de Hands-Free Navigator).

## Opciones

Se añaden al final, por ejemplo `jarvis.bat --modelo base`:

| Opción | Para qué |
|---|---|
| `--tecla f9` | Volver a hablar manteniendo una tecla en vez de decir "Jarvis" |
| `--sensibilidad 2` | Si no detecta tu voz (más bajo = más sensible; por defecto 3) |
| `--modelo base` | Modelo más rápido (menos preciso). `medium` es más preciso y más lento |
| `--dispositivo cuda` | Usar la tarjeta gráfica NVIDIA si tienes |
| `--sin-gestos` | No usar la cámara |
| `--ver-camara` | Ver la cámara con el gesto que detecta (para ajustar) |
| `--camara 1` | Otra cámara |
| `--distro Ubuntu-22.04` | Si tu distribución de WSL tiene otro nombre (míralo con `wsl -l`) |
| `--piper ruta\voz.onnx` | Voz más natural con Piper (ver abajo) |
| `--solo-texto` | Escribir en vez de hablar, para probar sin micrófono |

## Voz más natural (opcional)

Por defecto usa las voces de Windows. Si no suena en español, instala una voz española en Configuración → Hora e idioma → Voz.

Para una voz más natural con Piper:
1. `.venv\Scripts\pip install piper-tts`
2. Descarga una voz en español (archivos `.onnx` y `.onnx.json`) desde https://huggingface.co/rhasspy/piper-voices/tree/main/es, por ejemplo `es_MX-claude-high`.
3. `jarvis.bat --piper C:\ruta\es_MX-claude-high.onnx`

## Problemas comunes

- **No responde a "Jarvis"**: mira la ventana; si aparece "(oído) ..." con otra palabra, dilo más claro o usa `--modelo medium`. Si no aparece nada, prueba `--sensibilidad 2`.
- **Hace la acción pero no habla**: revisa `P:\jarvis-os\logs\voz.log`; ahí queda el motivo. Si la voz sale en inglés, instala una voz española en Configuración → Hora e idioma → Voz.
- **"Error de JARVIS"**: prueba `./scripts/jarvis.sh "hola"` en Ubuntu; si ahí falla, el problema es de Claude Code, no de la voz.
- **Los gestos no hacen nada**: arrancan en pausa, haz los cuernos 1 s. Abre con `--ver-camara` para ver qué detecta. Si dice que no están instalados, mira "Instalar".
- **Tarda en responder**: la mayor parte del tiempo es Claude trabajando. Para transcribir más rápido usa `--modelo base`.
