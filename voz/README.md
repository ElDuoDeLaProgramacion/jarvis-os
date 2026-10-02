# Voz de JARVIS (Windows)

Mantén pulsada **F9**, habla, suelta. JARVIS transcribe tu voz en local, ejecuta la petición en WSL y te responde en voz alta.

```
micrófono → faster-whisper (local) → wsl: scripts/jarvis.sh → Claude Code + habilidades → voz de Windows
```

El audio nunca sale de tu máquina: la transcripción y la voz son locales. Solo el texto transcrito va a Claude.

## Instalar (una vez)

Necesitas Python 3.10+ **para Windows** (no el de WSL): https://www.python.org/downloads/ (marca "Add python.exe to PATH").

1. Antes, comprueba que JARVIS ya funciona por texto en Ubuntu: `cd /mnt/p/jarvis-os && ./scripts/jarvis.sh "hola"`.
2. En el Explorador abre `P:\jarvis-os\voz` y haz doble clic en `instalar.bat`.

## Usar

Doble clic en `jarvis.bat`. La primera vez descarga el modelo de voz (unos 500 MB para `small`). Luego:

- Mantén **F9**, di "plan de hoy", suelta.
- Verás la transcripción y la respuesta en la ventana, y la oirás.
- Si tienes el HUD abierto, "Audio E/S" muestra ESCUCHANDO, PENSANDO o HABLANDO, y cada conversación aparece en "Actividad".

Opciones (se añaden al final, por ejemplo `jarvis.bat --tecla f8`):

| Opción | Para qué |
|---|---|
| `--tecla f8` | Cambiar la tecla para hablar |
| `--modelo base` | Modelo más rápido (menos preciso). `medium` es más preciso y más lento |
| `--dispositivo cuda` | Usar la tarjeta gráfica NVIDIA si tienes |
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

- **No pasa nada al pulsar F9**: ejecuta `jarvis.bat` como administrador (algunas apps bloquean la captura de teclas).
- **"Error de JARVIS"**: prueba `./scripts/jarvis.sh "hola"` en Ubuntu; si ahí falla, el problema es de Claude Code, no de la voz.
- **Tarda en responder**: la mayor parte del tiempo es Claude trabajando. Para transcribir más rápido usa `--modelo base`.
