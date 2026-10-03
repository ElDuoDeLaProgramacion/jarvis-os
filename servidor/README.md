# JARVIS en un servidor (Oracle Cloud gratis) y la app del celular

Con esto JARVIS vive en un servidor que nunca se apaga, con la bóveda dentro. Aunque el PC esté apagado, puedes:
- usar WhatsApp con JARVIS (órdenes, avisos y respuestas con "sí"),
- hablarle o escribirle desde la **app del celular** (un chat con micrófono que se instala en la pantalla de inicio),
- y recibir las rutinas de cada día (resumen matutino, plan, pendientes, cierre).

El PC sigue funcionando igual: la voz, el HUD y el copiloto trabajan con la misma bóveda, que se sincroniza sola en los dos sentidos.

```
celular (app + WhatsApp) ──Tailscale──► servidor Oracle ◄──Syncthing──► PC (boveda/)
                                          ├─ servidor/api.py      app del celular
                                          ├─ whatsapp/puente.mjs  WhatsApp
                                          ├─ cron                 rutinas
                                          └─ boveda/              el cerebro
```

## Qué se necesita
- Una cuenta de Oracle Cloud (gratis; pide tarjeta para verificar identidad, pero el nivel "Always Free" no cobra).
- Una cuenta de Tailscale (gratis), con la app en el celular. Crea una red privada entre el celular y el servidor: la app de JARVIS **no queda abierta a internet**.
- Tu cuenta de Claude: en el servidor entras una vez, igual que en el PC. No hace falta ninguna API de Claude.

## 1. Crear el servidor en Oracle
1. Entra a [cloud.oracle.com](https://cloud.oracle.com) y crea la cuenta. Elige como región la más cercana; después no se puede cambiar.
2. Menú → *Compute* → *Instances* → *Create instance*.
3. *Image*: **Canonical Ubuntu 24.04**. *Shape*: **Ampere VM.Standard.A1.Flex** con 2 OCPU y 12 GB (el nivel gratis permite hasta 4 OCPU y 24 GB).
4. *Add SSH keys*: *Generate a key pair* y descarga la clave privada (guárdala en `C:\Users\Usuario\.ssh\oracle.key`).
5. *Create*. Si sale "Out of capacity", prueba otro *Availability domain* o vuelve a intentarlo más tarde: pasa seguido con las máquinas gratis.
6. Copia la *Public IP address* de la instancia.

No hay que abrir ningún puerto: solo se usa SSH (22), que ya viene abierto.

## 2. Conectarse e instalar
En PowerShell del PC:
```
ssh -i $HOME\.ssh\oracle.key ubuntu@IP_DEL_SERVIDOR
```
Ya dentro del servidor:
```
git clone https://github.com/ElDuoDeLaProgramacion/jarvis-os.git
cd jarvis-os
./servidor/instalar.sh
```
El instalador pone todo lo necesario: Node, Claude Code, la app como servicio, las rutinas en cron, Syncthing y Tailscale. También ajusta la hora del servidor a Colombia (para otra zona: `JARVIS_ZONA=America/Mexico_City ./servidor/instalar.sh`). Cuando Tailscale muestre un enlace, ábrelo y entra con tu cuenta. Si después pide activar HTTPS en tu red, abre ese enlace también y actívalo.

## 3. Entrar a Claude
```
claude
```
Elige tu cuenta y sigue el enlace. Luego escribe `/mcp` y revisa que aparezcan Gmail, Google Calendar y Spotify (son los conectores de tu cuenta de claude.ai). Sal con `/exit`.

Si usas la clave de YouTube u otras opciones, cópialas tú a mano en el `.env` del servidor (`nano .env`). No las pegues en ningún chat.

## 4. La app en el celular
1. Instala **Tailscale** en el celular y entra con la misma cuenta.
2. Abre en Chrome la dirección que mostró el instalador (`https://<servidor>.<tu-red>.ts.net/app/`).
3. Pega la clave de la app. Está en el `.env` del servidor: `grep JARVIS_API_TOKEN .env`.
4. Menú de Chrome → **Instalar app** (o *Agregar a la pantalla principal*). En iPhone: Safari → Compartir → *Agregar a inicio*.

En la app:
- Escribes o tocas 🎙 y hablas. El dictado usa el reconocimiento de voz del propio celular.
- **Voz** hace que JARVIS lea en voz alta cada respuesta.
- **Hoy** muestra las prioridades, la agenda y las tareas.
- Los botones de abajo son los mismos del HUD.
- Los pedidos seguidos (en 30 minutos) son una sola conversación. Si JARVIS pregunta "¿Lo envío?" por un correo y contestas "sí", lo envía, igual que por voz.

## 5. La bóveda sincronizada (Syncthing)
La bóveda vive en el servidor y en el PC a la vez. Syncthing copia los cambios en los dos sentidos.

1. En el PC, instala Syncthing para Windows ([syncthing.net/downloads](https://syncthing.net/downloads/), "Windows Setup"). Se abre en `http://127.0.0.1:8384`.
2. Para ver el Syncthing del servidor, abre otra PowerShell con un túnel y deja la ventana abierta:
   ```
   ssh -i $HOME\.ssh\oracle.key -L 8385:127.0.0.1:8384 ubuntu@IP_DEL_SERVIDOR
   ```
   y entra a `http://127.0.0.1:8385`. Pon un usuario y contraseña en la interfaz cuando lo pida.
3. En el PC: *Agregar dispositivo remoto* con el ID del servidor (Acciones → Mostrar ID). Acepta en el servidor.
4. En el PC: *Agregar carpeta* con la ruta `P:\jarvis-os\boveda` y compártela con el servidor.
5. En el servidor, al aceptar la carpeta, pon la ruta `/home/ubuntu/jarvis-os/boveda` y, en *Avanzado*, el tipo **Solo recibir**. Cuando termine, pulsa **Revertir cambios locales**: así la bóveda del servidor queda igual a la del PC, que es la más nueva. Después cambia el tipo a **Enviar y recibir**.

Si JARVIS escribe el mismo archivo en los dos lados a la vez, Syncthing guarda las dos versiones (`*.sync-conflict-*.md`) en vez de perder una.

## 6. Pasar WhatsApp al servidor
WhatsApp debe correr en un solo lugar.
1. En el PC, cierra la ventana "JARVIS WhatsApp" y desactiva su arranque (PowerShell):
   ```
   Disable-ScheduledTask -TaskPath "\JARVIS\Inicio\" -TaskName "WhatsApp"
   ```
2. En el servidor: `./whatsapp/iniciar.sh`, escanea el QR (o usa `--codigo 57300XXXXXXX`) y, cuando diga "en línea", ciérralo con Ctrl+C.
3. Vuelve a ejecutar `./servidor/instalar.sh`. Ahora deja WhatsApp como servicio.
4. En el celular, en *Dispositivos vinculados*, cierra la sesión del dispositivo viejo (el del PC).

## 7. Apagar las rutinas del PC
Ahora salen del servidor. Para que no lleguen dos veces (PowerShell):
```
Get-ScheduledTask -TaskPath "\JARVIS\" | Disable-ScheduledTask
```
Para volver atrás, cambia `Disable` por `Enable`. Si cambias `rutinas/rutinas.csv`, en el servidor ejecuta `./servidor/rutinas.sh`.

## Día a día
- **Actualizar:** `cd jarvis-os && git pull && sudo systemctl restart jarvis-app jarvis-whatsapp`
- **Ver si todo corre:** `systemctl status jarvis-app jarvis-whatsapp`
- **Registros:** `logs/jarvis.log`, `logs/whatsapp.log`, `logs/rutinas.log` y `journalctl -u jarvis-app`

## Lo que no se puede con el PC apagado
- Música: "pon...", "pasa la canción" y el volumen controlan el Spotify del PC.
- El copiloto, las capturas de pantalla, el lienzo 3D y los gestos, que miran tu pantalla o tu cámara.
- Los archivos y proyectos de `P:\` y `C:\Users\Usuario`, que solo están en el PC.

## Seguridad
- La app escucha solo dentro del servidor (`127.0.0.1:7788`). Al celular llega por Tailscale con HTTPS. Desde internet no se ve.
- Cada pedido exige la clave `JARVIS_API_TOKEN`. Si la pierdes o crees que alguien la vio, bórrala del `.env`, ejecuta `./servidor/instalar.sh` (crea otra) y pégala de nuevo en la app.
- Las mismas reglas que en el PC: los correos solo salen con tu "sí", WhatsApp solo envía con tu "sí", y las rutinas no envían ni agendan nada.

## Límites de Oracle gratis
- Oracle puede **recuperar** máquinas gratis que pasan 7 días casi sin uso. JARVIS usa poco, así que puede pasar. Para evitarlo, pasa la cuenta a *Pay As You Go*: lo que está dentro del nivel gratis sigue sin costar.
- Haz que Syncthing tenga siempre la bóveda también en el PC. Si el servidor desaparece, no pierdes nada.
