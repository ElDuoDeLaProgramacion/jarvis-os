# Centinela de Orión

Vigila el servidor cada minuto, se defiende solo con cosas que se pueden deshacer y te avisa por WhatsApp
(en tu chat contigo mismo, como el resto de Orión).

## Activarlo (una vez, en el servidor)
```bash
cd ~/jarvis-os
./scripts/actualizar.sh
./centinela/instalar.sh            # bloquea solo y avisa
# o, para probar unos días sin que bloquee nada:
./centinela/instalar.sh avisar
```
Hazlo **por SSH desde tu casa**: tu IP de ese momento queda permitida para siempre. En un minuto te llega
"Centinela encendido" por WhatsApp.

## Qué vigila y qué hace
| Qué ve | Qué hace solo | Aviso |
|---|---|---|
| 8 claves SSH malas en 10 min desde una IP | Bloquea la IP 1 h (24 h si reincide en la semana) | ⚠️ |
| Entrada SSH buena desde una IP nueva | La marca de confianza 3 días (para no bloquearte nunca) | ⚠️ (🚨 si es root) |
| Más de 10 conexiones SSH nuevas por minuto o 50 por segundo a cualquier otro puerto TCP desde una IP (flood SYN tipo hping3) | El kernel tira el exceso al instante y en menos de 1 min bloquea la IP 1 h | ⚠️ |
| 150 conexiones abiertas o 60 a medio abrir desde una IP (DoS) | Bloquea 15 min / 1 h | ⚠️ |
| Ola de conexiones a medio abrir desde muchas IPs (DDoS SYN) | Cookies SYN del kernel + frena a las peores | 🚨 |
| Tráfico de entrada o salida muy por encima de lo normal (aprende lo normal solo, el primer día es prudente) | — | 🚨 |
| Un programa desconocido manda 300 MB a una sola IP en 10 min (fuga) | Bloquea esa IP en ambos sentidos 1 h | 🚨 |
| Lo mismo con un programa conocido (Syncthing, Caddy, node…) o alguien que descarga mucho de tu web | — | ⚠️ |
| Cambian usuarios, sudoers, llaves SSH, cron, servicios, Caddy, PAM, `ld.so.preload` | Guarda la versión anterior | ⚠️/🚨 con lo que cambió |
| Usuario con UID 0 que no es root | — | 🚨 |
| Puerto nuevo escuchando hacia internet | — | ⚠️ |
| Minero de cripto, o un programa de `/tmp` o `/dev/shm` comiéndose la CPU | Lo **congela** (SIGSTOP, no lo mata) | 🚨 |

### Las webs del dominio (ubuntulabs.co y las demás que sirve Caddy)
`instalar.sh` hace que Caddy anote cada visita en `/var/log/caddy/acceso.log` (`caddy-registro.sh`; Cookie y
Authorization salen tapadas). El centinela lee lo nuevo cada minuto, con la **IP real** del visitante
(detrás de Cloudflare viene en `Cf-Connecting-Ip`; esa cabecera solo se cree si la visita llega desde
Cloudflare), y bloquea 1 h a quien:

| Qué ve (por IP, en 10 min) | Umbral |
|---|---|
| Recorrido de rutas (`../`, `/etc/passwd`), ejecución de comandos (`;wget`, `${jndi:`), escáner (sqlmap, nikto, nuclei…) | a la primera |
| Inyección SQL, XSS, inclusión de archivos | 3 |
| Pide archivos sensibles (`.env`, `.git`, `wp-login`, respaldos `.sql`…) | 5 |
| Logins rechazados (POST con 401/403) | 20 |
| Páginas inexistentes (buscando rutas a ciegas) | 100 |
| Flood HTTP | 600 peticiones en 1 min |
| Se lleva más de 500 MB | solo avisa |

**Dónde lo bloquea:** si llegó directo, en nftables como siempre. Si llegó **a través de Cloudflare**, aquí no
se puede (sería cortar a Cloudflare entero): con `CENTINELA_CF_TOKEN` y `CENTINELA_CF_ZONA` en
`/etc/orion-centinela.conf` lo bloquea en Cloudflare (IP Access Rules, nota `orion-centinela`, se quita
sola); sin token te avisa con los pasos para hacerlo a mano. Y si todas las webs juntas reciben muchísimas
más peticiones de lo normal (DDoS), sube Cloudflare a **Under Attack** y lo baja tras 30 min de calma.

Token: Cloudflare → Mi perfil → API Tokens → Crear, solo para la zona del dominio, permisos *Zone →
Firewall Services: Edit*, *Zone → Zone Settings: Edit* y *Zone → Analytics: Read*. El ID de zona está en la
portada del dominio. Ponlos con `sudo nano /etc/orion-centinela.conf` (el archivo es solo de root).

Lo que hace Cloudflare solo y gratis (actívalo en su panel, no depende de Orión): nube naranja en cada
subdominio, *Security → Bots → Bot Fight Mode*, *Security → WAF → Managed rules* y una regla de rate limiting.

**Nunca bloquea:** tus IPs de `CENTINELA_PERMITIDOS`, la IP pública del propio servidor, IPs desde las que
entraste por SSH en los últimos 3 días, redes privadas, Tailscale y Cloudflare (si tus dominios pasan por
Cloudflare, bloquear una de sus IPs tumbaría la web para todos).

**Lo que no puede hacer desde aquí:** un DDoS que llena el cable no se para dentro del servidor; para eso
está Cloudflare (Security → *Under Attack*) o el proveedor. Los archivos cambiados no los revierte solo,
porque pudiste ser tú: te dice el comando para deshacerlo.

## Comandos
```bash
sudo orion-centinela estado                 # modo, IPs bloqueadas y últimos eventos
sudo orion-centinela lista                  # solo las bloqueadas
sudo orion-centinela bloquear 1.2.3.4 120   # a mano (minutos opcional)
sudo orion-centinela desbloquear 1.2.3.4
sudo orion-centinela confiar 1.2.3.4 30     # nunca bloquear esa IP en 30 días
sudo orion-centinela aceptar                # "ese cambio lo hice yo": lo de ahora queda como normal
sudo orion-centinela restaurar /etc/ssh/sshd_config
sudo orion-centinela soltar 4242            # descongela un proceso
sudo orion-centinela apagar                 # quita TODOS los bloqueos y límites (sigue avisando)
sudo orion-centinela encender
```
Por WhatsApp también: "¿me están atacando?", "qué IPs bloqueaste", "bloquea 1.2.3.4", "desbloquea 1.2.3.4".
Orión solo puede esas cuatro cosas (sudoers); apagar, aceptar y restaurar son solo tuyos, a propósito.

## Si te bloquea a ti
No debería (ver arriba), pero si pasa: el bloqueo caduca solo en 1 h. Si no puedes esperar, entra por la
consola web del proveedor (Clouding → tu servidor → Consola) y corre `sudo orion-centinela apagar`.

## Dónde vive
- Lo que corre: `/opt/orion-centinela/` (copia que solo root cambia; `instalar.sh` la actualiza). El
  actualizador automático de Orión NO toca esta copia: vuelve a correr `./centinela/instalar.sh` tras
  cambios en `centinela/`.
- Ajustes: `/etc/orion-centinela.conf` (umbrales en `AJUSTES` de `centinela.py`; solo root lo lee).
- Registro de visitas: `/var/log/caddy/acceso.log` (lo activa `caddy-registro.sh` en cada sitio de Caddy).
- Registro: `/var/log/orion-centinela.jsonl`. Estado: `/var/lib/orion-centinela/`.
- Reglas: tabla propia `inet orion_centinela` de nftables; no toca ufw.
- Pruebas: `python3 -m unittest centinela/test_centinela.py` (con `CENTINELA_PROBAR_NFT=1` y root, prueba
  nftables de verdad).
