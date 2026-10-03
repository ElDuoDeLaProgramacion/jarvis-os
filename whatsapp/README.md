# WhatsApp de JARVIS (vinculado por QR)

JARVIS se vincula a tu WhatsApp como un dispositivo más, igual que WhatsApp Web. No hace falta ninguna clave ni cuenta aparte.

- **Órdenes:** escríbete a ti mismo (el chat "Tú" o "Mensaje a ti mismo") lo mismo que le dirías por voz: "plan de hoy", "agéndame dentista el viernes a las 3", "resume mis correos". JARVIS contesta en ese chat con mensajes que empiezan por *JARVIS:*.
- **Tus chats:** los mensajes que te llegan quedan anotados en `boveda/raw/whatsapp/chats/AAAA-MM-DD.md`. Puedes preguntar "¿qué me escribieron hoy?" o "¿qué dijo Ana?".
- **Responder:** "respóndele a Ana que llego a las 8". JARVIS te muestra el mensaje y solo lo envía si contestas "sí". Si contestas "no", no sale nada. Esto también funciona si lo pides por voz: el borrador te llega al chat contigo mismo.

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
3. Cuando diga "WhatsApp de JARVIS en línea", escríbete "hola" en tu chat contigo mismo.

Si el QR se ve mal en la terminal, usa un código: `./whatsapp/iniciar.sh --codigo 57300XXXXXXX` (tu número con código de país). En el celular elige *Vincular con número de teléfono* y escribe el código que aparece.

**Arranque automático:** después de vincular, vuelve a ejecutar `rutinas\instalar-inicio.ps1` en PowerShell. Se añade la tarea "WhatsApp".

## Opciones en `.env`
- `WHATSAPP_GUARDAR_GRUPOS=1` también anota los grupos. Por defecto solo se anotan los chats individuales.
- `WHATSAPP_NO_GUARDAR=57300...,57311...` son números que nunca se anotan.
- `WHATSAPP_PERMITIDOS=57300...` solo hace falta si vinculas un número aparte, solo para JARVIS. En ese caso le escribes desde tu celular y obedece únicamente a esos números.

## Cómo funciona
- `puente.mjs` usa [Baileys](https://github.com/WhiskeySockets/Baileys), la librería que habla con WhatsApp Web. La vinculación se guarda en `whatsapp/sesion/`, que no se sube a git. Si la borras, toca escanear el QR otra vez.
- Los contactos que va viendo quedan en `cola/whatsapp/contactos.json`, para saber a quién responder.
- Para responder a alguien, JARVIS escribe `cola/whatsapp/borrador.json`. El puente lo muestra y solo lo envía si tu siguiente mensaje es "sí". Esa regla está en el código, no depende del modelo.
- Los mensajes seguidos en 30 minutos continúan la misma conversación. Si JARVIS pregunta "¿Lo envío?" por un correo y contestas "sí", lo envía, igual que por voz.
- Las órdenes que escribas con el PC apagado no se ejecutan después, para que no te sorprenda nada viejo. Los mensajes de tus chats que llegaron mientras tanto sí se anotan cuando vuelve.
- Lo que pasa queda en `logs/whatsapp.log` y en la actividad del HUD.

## Límites y riesgos
- **No es la API oficial.** WhatsApp puede cerrar la vinculación o bloquear el número si detecta abuso, como envíos masivos o spam. JARVIS solo envía mensajes uno por uno y con tu "sí". Si quieres cero riesgo para tu número principal, vincula un número secundario y usa `WHATSAPP_PERMITIDOS`.
- Por ahora las órdenes solo pueden ser de texto, no notas de voz. Las fotos y los audios de tus chats se anotan como "(foto)" o "(nota de voz)", sin su contenido.
- El PC tiene que estar encendido. JARVIS trabaja en tu PC y el celular solo es el control remoto.
- Si el celular pasa unos 14 días sin conexión, WhatsApp desvincula los dispositivos. En ese caso vuelve a escanear el QR.
- Tus chats quedan en `boveda/raw/whatsapp/`, que no se sube a git porque tu repositorio es público.
