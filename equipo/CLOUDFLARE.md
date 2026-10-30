# Poner usuario y contraseña delante con Cloudflare

La sala ya pide usuario y contraseña (cada persona tiene la suya, `./equipo/persona.sh`). Si además
quieres un candado antes de que la petición llegue a tu servidor —que Cloudflare pida identificarse
primero—, usa **Cloudflare Access** (parte de Zero Trust, gratis hasta 50 personas). Quedan dos capas:
Cloudflare valida quién eres en la entrada, y la sala valida tu usuario adentro.

Tu dominio ya está en Cloudflare, así que es rápido.

## 1. Activa Zero Trust (una vez)
En el panel de Cloudflare entra a **Zero Trust** (menú de la izquierda). Si es la primera vez te pide
elegir un nombre de equipo (`tuequipo.cloudflareaccess.com`) y el plan Free.

## 2. Un login de correo (una vez)
En **Settings → Authentication → Login methods** deja activado **One-time PIN** (envía un código al
correo; no hay que configurar nada). Si quieres entrar con Google/GitHub, añádelos ahí.

## 3. Protege la sala
En **Access → Applications → Add an application → Self-hosted**:
- **Application name:** Orión Equipo
- **Session duration:** 24 horas (o lo que prefieras)
- **Application domain:** `equipo.tudominio.com` (el subdominio que te dio `./equipo/instalar.sh`)
- Guarda y crea una **policy**:
  - **Name:** Equipo
  - **Action:** Allow
  - **Include → Emails:** los correos de tus amigos, uno por uno (o **Emails ending in** si son del
    mismo dominio). Solo esos correos reciben el PIN y pueden pasar.

Desde ahora, al abrir `https://equipo.tudominio.com` Cloudflare pide el correo, manda un código y solo
entonces aparece la sala (que pedirá su usuario y contraseña). Quitar a alguien: bórralo de la policy
y de `./equipo/persona.sh quitar`.

**Deja tu panel fuera de esa policy o con una aparte solo para tu correo.** Añade otra application para
`equipo.tudominio.com/panel` (Path = `panel`) con una policy que incluya **solo tu correo**. Así nadie
del equipo llega ni a la pantalla del panel.

## 4. (Opcional) Esconder el servidor con un túnel (cloudflared)
Hoy la sala sale por Caddy y la IP pública. Si prefieres que el servidor no exponga la IP ni los
puertos 80/443, usa un **túnel**:
1. **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**. Te da un comando
   `cloudflared service install <token>`: córrelo en el servidor (instala el servicio del túnel).
2. En el túnel, **Public hostname**: `equipo.tudominio.com` → Service `http://localhost` (o el socket
   de Caddy). Cloudflare crea el registro DNS solo.
3. Con el túnel puedes cerrar 80/443 en el firewall del proveedor; Cloudflare llega por el túnel.
   El certificado lo pone Cloudflare, así que en ese caso Caddy ya no necesita Let's Encrypt para este
   subdominio.

Para solo poner el login delante, con el paso 3 basta; el túnel es un extra de seguridad.

> Los menús de Cloudflare cambian de nombre de vez en cuando. Si algo no está donde dice aquí, búscalo
> como "Cloudflare Access self-hosted application" en su documentación.

## 5. Un solo login para los dos paneles (Hallazgos y Equipo)

Los dos paneles ya viven en un mismo dominio: Hallazgos en `https://api.ubuntulabs.co/panel` y Orión
Equipo en `https://api.ubuntulabs.co/equipo`, con el botón de arriba para saltar de uno a otro. Para
entrar **una sola vez** (y no con la clave de cada panel), pon Cloudflare Access como la puerta de
`api.ubuntulabs.co` y deja que los paneles confíen en ese login.

1. **Encierra el origen en Cloudflare (imprescindible).** Esto es lo que hace seguro confiar en Access.
   Elige una:
   - **Nube naranja** en el registro `api` + en el firewall del proveedor deja el 443 **solo** para los
     [rangos de IP de Cloudflare](https://www.cloudflare.com/ips/); o
   - un **túnel** (sección 4) para `api.ubuntulabs.co`, y cierra el 443 público.
   Si cualquiera puede llegar al servidor saltándose Cloudflare, no actives el login único.
2. **Access en `api.ubuntulabs.co`.** En **Access → Applications → Add → Self-hosted**: dominio
   `api.ubuntulabs.co` (cubre `/panel` y `/equipo`), y una **policy** que incluya **solo tu correo**.
3. **Diles a los paneles que confíen en Access** (así no vuelven a pedir clave):
   - Orión Equipo: en `~equipo/.env` pon `ORION_EQUIPO_ACCESS_EMAIL=tucorreo@dominio` y
     `sudo systemctl restart orion-equipo`.
   - Hallazgos: en su `.env` pon `PANEL_ACCESS_EMAIL=tucorreo@dominio` y `./hv reiniciar`.
   Con eso, Cloudflare te identifica una vez y entras a los dos paneles. La clave+código de cada panel
   siguen sirviendo como respaldo (p. ej. desde la red local). Si prefieres quitarlos del todo, dímelo.

El chat del equipo va aparte, en `https://equipos.ubuntulabs.co`, con su propia policy de Access para los
correos del equipo (sección 3) y, adentro, el usuario y contraseña de cada quien.
