# WhatsApp de JARVIS (Kapso)

JARVIS tiene su propio número de WhatsApp. Le escribes desde el celular, como a cualquier contacto, y te contesta por ahí: "plan de hoy", "agéndame dentista el viernes a las 3", "resume mis correos"... Es la API oficial de WhatsApp (Cloud API) a través de [Kapso](https://kapso.ai), así que no hay riesgo de bloqueo.

Solo obedece a tu número. Si otra persona le escribe, el mensaje se guarda en `boveda/raw/whatsapp/` y no se ejecuta nada.

## Instalar (una vez)

1. **Kapso:**
   - Crea una cuenta en kapso.ai y un proyecto.
   - En *WhatsApp → Numbers*, conecta un número para JARVIS. Puedes elegir un número de Colombia que te dan ellos o uno tuyo. Para probar, también sirve el número sandbox.
   - Copia el **Phone number ID** de ese número.
   - En *API keys*, crea una clave.
2. **En Ubuntu (WSL):**
   ```
   cd /mnt/p/jarvis-os
   ./whatsapp/instalar.sh
   ```
   Esto instala `cloudflared` (el túnel gratis de Cloudflare) y añade las variables a `.env`.
3. **Completa `.env`:**
   ```
   KAPSO_API_KEY=la clave de Kapso
   KAPSO_PHONE_NUMBER_ID=el Phone number ID
   WHATSAPP_PERMITIDOS=57XXXXXXXXXX     <- tu celular con código de país, sin + ni espacios
   ```
   `KAPSO_WEBHOOK_SECRET` ya viene generado. No lo compartas.
4. **Prueba:** ejecuta `./whatsapp/iniciar.sh`. Cuando diga "WhatsApp de JARVIS en línea", escríbele desde tu celular.
5. **Arranque automático:** vuelve a ejecutar `rutinas\instalar-inicio.ps1` en PowerShell. Se añade la tarea "WhatsApp".

## Cómo funciona
- `puente.py` abre un túnel `https://...trycloudflare.com` hacia el puerto 7778 del PC. Cada vez que arranca, apunta el webhook de Kapso a esa dirección, que cambia en cada arranque.
- Comprueba la firma de cada aviso (`X-Webhook-Signature`, HMAC SHA256) y que venga de `WHATSAPP_PERMITIDOS`.
- Pasa el texto a `scripts/jarvis.sh` y responde por WhatsApp. Los mensajes seguidos en 30 min continúan la misma conversación.
- Si JARVIS pregunta "¿Lo envío? Sí o no." y contestas "sí", envía el correo, igual que por voz.
- Lo que pasa queda en `logs/whatsapp.log` y en la actividad del HUD.

## Límites
- Por ahora solo entiende mensajes de texto, no notas de voz ni fotos.
- **Ventana de 24 horas de WhatsApp:** JARVIS solo puede escribirte dentro de las 24 h siguientes a tu último mensaje. Para avisos por su cuenta (por ejemplo, el resumen de las 7:00) hacen falta plantillas aprobadas por Meta.
- **Costo:** Kapso tiene plan gratis para probar. Desde octubre de 2026 las respuestas dentro de la ventana también se cobran: revisa los precios en kapso.ai.
- El PC tiene que estar encendido. JARVIS trabaja en tu PC; el celular solo es el control remoto.
