# Voz y gestos de Orión (Windows)

Di **"Orión"** seguido de lo que necesitas ("Orión, plan de hoy"), o solo "Orión" y espera el "¿Sí?". Orión transcribe tu voz en local, ejecuta la petición en WSL y **siempre** te contesta en voz alta. Con la cámara, tu mano maneja el ratón: mover, clic, clic derecho, Tab y cambio de pestaña.

```
micrófono → faster-whisper (local) → "¿empieza por Orión?" → wsl: scripts/jarvis.sh → Claude Code + habilidades → voz de Windows
cámara    → MediaPipe (local) → gestos de Hands-Free Navigator → ratón y teclado
```

El audio y la imagen nunca salen de tu máquina: la transcripción, los gestos y la voz son locales. Solo el texto de la orden va a Claude.

## Instalar (una vez)

Necesitas Python **para Windows** (no el de WSL): https://www.python.org/downloads/ (marca "Add python.exe to PATH"). Para los gestos tiene que ser **3.9 a 3.12** (MediaPipe aún no funciona con 3.13); la 3.11 es la más segura.

1. Antes, comprueba que Orión ya funciona por texto en Ubuntu: `cd /mnt/p/jarvis-os && ./scripts/jarvis.sh "hola"`.
2. En el Explorador abre `P:\jarvis-os\voz` y haz doble clic en `instalar.bat`. Si al final sale el aviso de que los gestos no se instalaron, instala Python 3.11, borra la carpeta `voz\.venv` y vuelve a ejecutarlo.

## Usar

Doble clic en `jarvis.bat` (o se abre solo al iniciar sesión, ver [rutinas](../rutinas/README.md)). La primera vez descarga el modelo de voz (unos 500 MB para `small`). Cuando diga "Orión en línea":

- "Orión, plan de hoy" → suena un pitido corto, trabaja y te lee la respuesta. Por voz usa un modelo más rápido (Sonnet); para cambiarlo pon `JARVIS_MODELO_VOZ=opus` (o `haiku`) en `.env`.
- "Orión" a secas → "¿Sí?" → dices la orden en los 8 segundos siguientes.
- Lo que digas sin "Orión" al principio se ignora (aparece como "(oído)" en la ventana).
- **Conversación seguida:** después de cada respuesta tienes 8 segundos para seguir hablando sin decir "Orión" ("¿y mañana?", "hazlo más corto"), en la misma conversación. Si Orión te pregunta algo ("¿Lo agendo?"), tienes 20 segundos. Cambia los 8 con `--conversacion 5` (0 = siempre con "Orión"). Ahí también valen las órdenes al instante ("abre Spotify", "pausa", "cierra la pestaña"), así que si te entendió mal, repítela sin "Orión".
- **Cerrar pestañas por nombre** (al instante): "Orión, cierra las pestañas de búsqueda de Google", "cierra las pestañas de YouTube". Recorre las pestañas del navegador que está al frente y cierra las que tienen eso en el título.
- **Copiloto** (sin que lo pidas): si estás jugando ajedrez (chess.com, lichess) o programando (VS Code, Cursor, PyCharm...), Orión mira la pantalla de vez en cuando (ajedrez cada 45 s, código cada 3 min, y solo si cambió) y habla solo si ve algo útil. En partidas en vivo contra personas no sugiere jugadas: va contra las reglas de esas páginas; te da un consejo al terminar. Cada mirada usa tu cuenta de Claude. "Orión, apaga el copiloto" / "activa el copiloto"; para arrancar apagado usa `--sin-copiloto`.
- **Abrir programas** (al instante): "Orión, abre Chrome / Word / Excel / Spotify / WhatsApp / la calculadora / VS Code...". La lista está en `ABRIBLES` en `jarvis_voz.py`. Entiende también lo que la voz oye un poco mal ("abri, Spotify", "abre y Spotify", "abrace putify", "spotifai").
- **Escribir en el HUD**: mientras la voz está encendida, lo que escribes en la caja del HUD lo atiende la voz igual que si lo dijeras (comandos al instante, música y respuesta hablada). Si la voz está apagada, va a la cola como antes.
- **Lienzo 3D** (al instante): "Orión, abre el lienzo 3D" abre una ventana con tu cámara. Con la mano derecha, pellizca (pulgar con índice) para dibujar en el aire; acerca o aleja la mano para ir en profundidad. Haz ✌️ un segundo para pasar a construir con bloques. Con la mano izquierda, pellizca y mueve para girar la escena. "Guardar" deja la imagen y la escena en `boveda/outputs/lienzo/`. Necesita el HUD (si está cerrado, lo abre) e internet la primera vez, para bajar el detector de manos. Mientras el lienzo está abierto, los gestos sueltan la cámara (Windows solo deja usarla a un programa) y la retoman al cerrarlo.
- **Música** (al instante, sin pasar por Claude ni gastar uso): "Orión, abre Spotify", "pausa", "play", "siguiente canción", "canción anterior", "pasa 3 canciones", "retrocede dos canciones", "sube el volumen", "baja el volumen".
- **"Orión, pon ..."** (una canción, un artista, "algo para concentrarme"): Orión lo busca con el conector de Spotify y lo pone en tu Spotify. "Orión, cambia de playlist" pone otra lista parecida. Para que las listas y los álbumes empiecen a sonar solos, conecta la API de Spotify (abajo); sin ella solo se abre su página.
- **Enviar un correo**: Orión redacta, te lo resume y pregunta "¿Lo envío? Sí o no." Si contestas "sí" (o "dale", "envíalo") en esos 20 segundos, lo envía; con "no", "espera" o "mejor no" queda como borrador. Solo envía en esa respuesta tuya, nunca desde rutinas ni botones del HUD. Las cancelaciones de suscripciones por correo funcionan igual.
- **Cerrar al navegar** (lo hace al instante, sin pasar por Claude): "Orión, cierra esta pestaña" (Ctrl+W), "Orión, cierra la ventana" o "cierra esto" (Alt+F4 en la ventana activa) y "Orión, cierra Spotify / Chrome / Word..." (le pide al programa que se cierre, así que si hay algo sin guardar te pregunta). Nunca cierra el propio Orión, la consola ni el escritorio de Windows.
- **"Orión, lee mi pantalla"** (o cualquier pedido con la palabra "pantalla"): hace una captura, Orión la mira y te dice qué hacer. Las últimas 10 capturas quedan en `cola\pantalla\` y no se suben a git.
- **"Orión, analiza este archivo"** (o PDF, enlace, video...): se abre la ventana de análisis en el HUD. Agrega archivos, enlaces o texto, pulsa Analizar y Orión te responde en voz. El audio y el video se transcriben aquí mismo con Whisper.
- **Interrumpir:** mientras Orión piensa o habla sigue escuchando. "Orión, para" (o "ya", "cállate", "olvídalo") lo calla al instante, y si aún pensaba no te dice la respuesta. "Orión, <otra cosa>" lo calla y te atiende. Mientras habla solo hace caso a frases que empiezan por "Orión", para no confundirse con su propia voz.
- **Voz natural:** habla con una voz neural de Microsoft (`es-MX-JorgeNeural`), frase a frase: mientras dice una ya prepara la siguiente. Necesita internet; sin conexión usa Piper o la voz de Windows sola. Otras voces: `--voz-neural es-ES-AlvaroNeural` (España), `es-CO-GonzaloNeural` (Colombia), `es-MX-DaliaNeural` (mujer); `--voz-neural no` para no usarla. Solo el texto de la respuesta sale a ese servicio, nunca tu audio.
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
| **Cuernos** (índice + meñique) 1 s | Pausar / reanudar los gestos (Orión te dice "Gestos en pausa" o "Gestos activos") |

La cámara **solo se enciende cuando se lo pides**: "Orión, activa los gestos" (o "enciende la cámara") la abre y los gestos quedan activos; "Orión, apaga los gestos" la cierra y deja de gastar CPU. Al encender el PC la cámara queda apagada. Arrastrar, zoom y grabar pantalla se quedan solo en Hands-Free Navigator. Los umbrales están en `voz\manos\config.py` (copia del de Hands-Free Navigator).

## Opciones

Se añaden al final, por ejemplo `jarvis.bat --modelo base`:

| Opción | Para qué |
|---|---|
| `--tecla f9` | Volver a hablar manteniendo una tecla en vez de decir "Orión" |
| `--sensibilidad 2` | Si no detecta tu voz (más bajo = más sensible; por defecto 3) |
| `--modelo base` | Modelo más rápido (menos preciso). `medium` es más preciso y más lento |
| `--dispositivo cuda` | Usar la tarjeta gráfica NVIDIA si tienes |
| `--sin-gestos` | No usar la cámara nunca, ni aunque se pida por voz |
| `--ver-camara` | Ver la cámara con el gesto que detecta (para ajustar) |
| `--camara 1` | Otra cámara |
| `--distro Ubuntu-22.04` | Si tu distribución de WSL tiene otro nombre (míralo con `wsl -l`) |
| `--voz-neural es-ES-AlvaroNeural` | Otra voz neural (`no` para usar la de Windows o Piper) |
| `--conversacion 5` | Segundos para seguir hablando sin "Orión" tras cada respuesta (0 = nunca) |
| `--piper ruta\voz.onnx` | Voz local con Piper, sin internet (ver abajo) |
| `--solo-texto` | Escribir en vez de hablar, para probar sin micrófono |

## Spotify que obedece de verdad (opcional, requiere Premium)
Sin esto, Orión abre la página de la lista y sigue sonando lo de antes. Con esto, la lista, el álbum o el artista empieza a sonar, y "pasa 3 canciones" va más rápido.
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

- **No responde a "Orión"**: mira la ventana; si aparece "(oído) ..." con otra palabra, dilo más claro o usa `--modelo medium`. Si no aparece nada, prueba `--sensibilidad 2`.
- **Hace la acción pero no habla**: revisa `P:\jarvis-os\logs\voz.log`; ahí queda el motivo. Si la voz sale en inglés, instala una voz española en Configuración → Hora e idioma → Voz.
- **"Error de Orión"**: prueba `./scripts/jarvis.sh "hola"` en Ubuntu; si ahí falla, el problema es de Claude Code, no de la voz.
- **Los gestos no hacen nada**: la cámara está apagada hasta que digas "Orión, activa los gestos"; si los pausaste con los cuernos, repítelos 1 s. Abre con `--ver-camara` para ver qué detecta. Si dice que no están instalados, mira "Instalar".
- **Tarda en responder**: la mayor parte del tiempo es Claude trabajando. Para transcribir más rápido usa `--modelo base`.
