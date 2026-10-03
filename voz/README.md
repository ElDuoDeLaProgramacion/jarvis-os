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

- "Jarvis, plan de hoy" → suena un pitido corto, trabaja y te lee la respuesta. Por voz usa un modelo más rápido (Sonnet); para cambiarlo pon `JARVIS_MODELO_VOZ=opus` (o `haiku`) en `.env`.
- "Jarvis" a secas → "¿Sí?" → dices la orden en los 8 segundos siguientes.
- Lo que digas sin "Jarvis" al principio se ignora (aparece como "(oído)" en la ventana).
- **Si JARVIS te pregunta algo** ("¿Lo agendo?"), contesta sin decir "Jarvis" en los 20 segundos siguientes: sigue la misma conversación.
- **Cerrar pestañas por nombre** (al instante): "Jarvis, cierra las pestañas de búsqueda de Google", "cierra las pestañas de YouTube". Recorre las pestañas del navegador que está al frente y cierra las que tienen eso en el título.
- **Copiloto** (sin que lo pidas): si estás jugando ajedrez (chess.com, lichess) o programando (VS Code, Cursor, PyCharm...), JARVIS mira la pantalla de vez en cuando (ajedrez cada 45 s, código cada 3 min, y solo si cambió) y habla solo si ve algo útil. En partidas en vivo contra personas no sugiere jugadas: va contra las reglas de esas páginas; te da un consejo al terminar. Cada mirada usa tu cuenta de Claude. "Jarvis, apaga el copiloto" / "activa el copiloto"; para arrancar apagado usa `--sin-copiloto`.
- **Abrir programas** (al instante): "Jarvis, abre Chrome / Word / Excel / Spotify / WhatsApp / la calculadora / VS Code...". La lista está en `ABRIBLES` en `jarvis_voz.py`.
- **Escribir en el HUD**: mientras la voz está encendida, lo que escribes en la caja del HUD lo atiende la voz igual que si lo dijeras (comandos al instante, música y respuesta hablada). Si la voz está apagada, va a la cola como antes.
- **Lienzo 3D** (al instante): "Jarvis, abre el lienzo 3D" abre una ventana con tu cámara. Con la mano derecha, pellizca (pulgar con índice) para dibujar en el aire; acerca o aleja la mano para ir en profundidad. Haz ✌️ un segundo para pasar a construir con bloques. Con la mano izquierda, pellizca y mueve para girar la escena. "Guardar" deja la imagen y la escena en `boveda/outputs/lienzo/`. Necesita el HUD (si está cerrado, lo abre) e internet la primera vez, para bajar el detector de manos.
- **Música** (al instante, sin pasar por Claude ni gastar uso): "Jarvis, abre Spotify", "pausa", "play", "siguiente canción", "canción anterior", "pasa 3 canciones", "retrocede dos canciones", "sube el volumen", "baja el volumen".
- **"Jarvis, pon ..."** (una canción, un artista, "algo para concentrarme"): JARVIS lo busca con el conector de Spotify y lo pone en tu Spotify. "Jarvis, cambia de playlist" pone otra lista parecida. Para que las listas y los álbumes empiecen a sonar solos, conecta la API de Spotify (abajo); sin ella solo se abre su página.
- **Enviar un correo**: JARVIS redacta, te lo resume y pregunta "¿Lo envío? Sí o no." Si contestas "sí" (o "dale", "envíalo") en esos 20 segundos, lo envía; con "no", "espera" o "mejor no" queda como borrador. Solo envía en esa respuesta tuya, nunca desde rutinas ni botones del HUD. Las cancelaciones de suscripciones por correo funcionan igual.
- **Cerrar al navegar** (lo hace al instante, sin pasar por Claude): "Jarvis, cierra esta pestaña" (Ctrl+W), "Jarvis, cierra la ventana" o "cierra esto" (Alt+F4 en la ventana activa) y "Jarvis, cierra Spotify / Chrome / Word..." (le pide al programa que se cierre, así que si hay algo sin guardar te pregunta). Nunca cierra el propio JARVIS, la consola ni el escritorio de Windows.
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
| Puño con el pulgar **arriba** / **abajo** (mantener) | Scroll arriba / abajo |
| Puño | Reposo, no hace nada |
| **Cuernos** (índice + meñique) 1 s | Activar / pausar los gestos (JARVIS te dice "Gestos activos" o "Gestos en pausa") |

Arrancan **en pausa** para no mover el ratón al encender el PC: haz los cuernos para activarlos. Arrastrar, zoom y grabar pantalla se quedan solo en Hands-Free Navigator. Los umbrales están en `voz\manos\config.py` (copia del de Hands-Free Navigator).

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

## Spotify que obedece de verdad (opcional, requiere Premium)
Sin esto, JARVIS abre la página de la lista y sigue sonando lo de antes. Con esto, la lista, el álbum o el artista empieza a sonar, y "pasa 3 canciones" va más rápido.
1. Entra a https://developer.spotify.com/dashboard y pulsa **Create app**. Pon cualquier nombre. En **Redirect URI** escribe `http://127.0.0.1:8888/callback` y en **APIs** marca **Web API**.
2. Copia el **Client ID** en `.env`: `SPOTIFY_CLIENT_ID=...`
3. Con la app de Spotify abierta, ejecuta en PowerShell, dentro de `P:\jarvis-os`:
   ```
   voz\.venv\Scripts\python voz\spotify.py --login
   ```
   Acepta en el navegador con la misma cuenta de la app de Spotify. El permiso queda en `voz\.spotify-token.json`, que no se sube a git.
4. Reinicia la voz.

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
