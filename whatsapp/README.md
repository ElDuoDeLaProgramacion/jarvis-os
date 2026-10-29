# WhatsApp de Orión (vinculado por QR)

Orión se vincula a tu WhatsApp como un dispositivo más, igual que WhatsApp Web. No hace falta ninguna clave ni cuenta aparte.

- **Órdenes:** escríbete a ti mismo (el chat "Tú" o "Mensaje a ti mismo") lo mismo que le dirías por voz: "plan de hoy", "agéndame dentista el viernes a las 3", "resume mis correos". Orión contesta en ese chat con mensajes que empiezan por *Orión:*.
- **Tus chats:** los mensajes que te llegan quedan anotados en `boveda/raw/whatsapp/chats/AAAA-MM-DD.md`. Puedes preguntar "¿qué me escribieron hoy?" o "¿qué dijo Ana?".
- **Responder:** "respóndele a Ana que llego a las 8". Orión te muestra el mensaje y solo lo envía si contestas "sí". Si contestas "no", no sale nada. Esto también funciona si lo pides por voz: el borrador te llega al chat contigo mismo.
- **Avisos:** cada vez que alguien te escribe, Orión te avisa en tu chat contigo mismo ("Te escribió Ana: ..."), sin proponer nada. Si quieres respuestas, dile "opciones" o "qué le respondo" y te propone 3: contestas 1, 2 o 3 ("sí" envía la 1) o "no". También puedes decirle qué contestar ("dile que llego a las 8") y te muestra el mensaje antes de enviarlo. Si la persona manda varios mensajes seguidos, llega un solo aviso, y si le contestas tú desde el celular, se cancela. Para que proponga respuestas en cada aviso, como antes, pon `WHATSAPP_OPCIONES=1` (cada aviso pasa a ser una consulta a Claude); para no recibir avisos, `WHATSAPP_AVISAR=0`.
- **Archivos:** mándale una foto o un documento (PDF, Excel, Word...) con lo que quieres en el pie ("sácame una tabla con estos datos"), o mándalo sin pie y te pregunta qué hacer. Si le pides un archivo ("hazme un Excel con...", "pásamelo en PDF"), te lo manda por el chat; si pides una tabla sin decir formato, te llega un Excel. Los archivos que le mandas se borran al día siguiente. Para Excel, Word, PowerPoint y PDF bonitos, corre una vez `./scripts/instalar-skills.sh` donde corre el puente.
- **Notas de voz:** puedes darle órdenes con notas de voz en tu chat contigo mismo. Las notas de voz que te mandan quedan escritas en el registro y en los avisos. Se transcriben en tu equipo con faster-whisper, el audio no se guarda y no gasta uso de Claude.
- **Música:** "pon música de..." la abre en el Spotify del PC, y "play", "pausa", "siguiente" o "sube el volumen" funcionan al instante. Las dos cosas necesitan que la voz de Orión esté encendida en el PC.

Nada de lo que escriben otras personas se ejecuta como orden: solo se anota.

## Instalar (una vez)

En Ubuntu (WSL):
```
cd /mnt/p/jarvis-os
git pull
./whatsapp/instalar.sh
./whatsapp/iniciar.sh
```
1. `instalar.sh` instala Node.js, si no lo tienes, y las librerías del puente.
2. `iniciar.sh` muestra un QR en la terminal. En el celular, ve a *WhatsApp → Dispositivos vinculados → Vincular dispositivo* y escanéalo.
3. Cuando diga "WhatsApp de Orión en línea", escríbete "hola" en tu chat contigo mismo.

Si el QR se ve mal en la terminal, usa un código: `./whatsapp/iniciar.sh --codigo 57300XXXXXXX` (tu número con código de país). En el celular elige *Vincular con número de teléfono* y escribe el código que aparece.

**Arranque automático:** después de vincular, vuelve a ejecutar `rutinas\instalar-inicio.ps1` en PowerShell. Se añade la tarea "WhatsApp".

## Darle a Orión su propio número

Si no quieres que Orión use tu chat contigo mismo, dale un número aparte. Tú le escribes desde tu WhatsApp, como a cualquier contacto, y él sigue leyendo tus chats con la vinculación que ya tienes.

- **Qué necesitas:** un número que pueda recibir un SMS o una llamada una vez, por ejemplo una SIM prepago o una eSIM. Instala ahí *WhatsApp Business* (o WhatsApp normal en otro celular) y regístralo. Si tu celular es dual SIM, WhatsApp Business convive con tu WhatsApp de siempre.
- **Vincular:** donde corre el puente (en el servidor, `cd ~/jarvis-os`), ejecuta `./whatsapp/vincular-orion.sh 57300XXXXXXX` con el número de Orión. En el celular de ese número ve a *Dispositivos vinculados → Vincular dispositivo → Vincular con número de teléfono* y escribe el código que aparece. Al terminar, el script reinicia el puente y Orión te saluda desde su número.
- **Cómo queda:**
  - Las órdenes, avisos, borradores, archivos y avisos del centinela llegan al chat con Orión.
  - Tu chat contigo mismo vuelve a ser solo tuyo.
  - Cuando apruebas un mensaje con "sí", sale de tu número, porque es tuyo para tu contacto.
  - Si alguien más le escribe al número de Orión, no lo atiende. Solo obedece a tu número y a `WHATSAPP_PERMITIDOS`.
- **Volver a como antes:** `rm -rf whatsapp/sesion-orion` y reinicia el puente. Si WhatsApp desvincula el número de Orión, el puente vuelve solo a tu chat contigo mismo y te lo dice.
- El celular con el número de Orión debe conectarse al menos una vez cada 14 días, o WhatsApp desvincula el puente. Un número nuevo que solo habla con un bot puede levantar sospechas, así que úsalo un par de días como un WhatsApp normal antes de vincularlo.

## Opciones en `.env`
- `WHATSAPP_GUARDAR_GRUPOS=1` también anota los grupos. Por defecto solo se anotan los chats individuales.
- `WHATSAPP_NO_GUARDAR=57300...,57311...` son números que nunca se anotan.
- `WHATSAPP_PERMITIDOS=57300...` son otros números a los que Orión obedece. Con número propio (ver arriba) ya te obedece a ti sin ponerlo.

## Cómo funciona
- `puente.mjs` usa [Baileys](https://github.com/WhiskeySockets/Baileys), la librería que habla con WhatsApp Web. La vinculación se guarda en `whatsapp/sesion/`, que no se sube a git. Si la borras, toca escanear el QR otra vez.
- Los contactos que va viendo quedan en `cola/whatsapp/contactos.json`, para saber a quién responder.
- Para responder a alguien, Orión escribe `cola/whatsapp/borrador.json`. El puente lo muestra y solo lo envía si tu siguiente mensaje es "sí". Esa regla está en el código, no depende del modelo.
- Los mensajes seguidos en 30 minutos continúan la misma conversación. Si Orión pregunta "¿Lo envío?" por un correo y contestas "sí", lo envía, igual que por voz.
- Las órdenes que escribas con el PC apagado no se ejecutan después, para que no te sorprenda nada viejo. Los mensajes de tus chats que llegaron mientras tanto sí se anotan cuando vuelve.
- Lo que pasa queda en `logs/whatsapp.log` y en la actividad del HUD.

## Límites y riesgos
- **No es la API oficial.** WhatsApp puede cerrar la vinculación o bloquear el número si detecta abuso, como envíos masivos o spam. Orión solo envía mensajes uno por uno y con tu "sí". Si quieres cero riesgo para tu número principal, vincula un número secundario y usa `WHATSAPP_PERMITIDOS`.
- Las fotos, los videos y los documentos de tus chats se anotan como "(foto)" o "(documento: ...)", sin su contenido. Las notas de voz sí se transcriben.
- Si `instalar.sh` no pudo instalar faster-whisper, las notas de voz se anotan como "(nota de voz)" sin texto. En ese caso corre `sudo apt install -y python3-venv` y vuelve a ejecutar `./whatsapp/instalar.sh`.
- El PC tiene que estar encendido. Orión trabaja en tu PC y el celular solo es el control remoto.
- Si el celular pasa unos 14 días sin conexión, WhatsApp desvincula los dispositivos. En ese caso vuelve a escanear el QR.
- Tus chats quedan en `boveda/raw/whatsapp/`, que no se sube a git porque tu repositorio es público.
